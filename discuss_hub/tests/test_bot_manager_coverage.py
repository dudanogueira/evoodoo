from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("discuss_hub", "bot_manager")
class TestBotManagerCoverage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Mock HTTP requests to prevent external calls during tests
        cls.patcher_requests_get = patch('requests.get')
        cls.patcher_requests_post = patch('requests.post')
        
        mock_get = cls.patcher_requests_get.start()
        mock_post = cls.patcher_requests_post.start()
        
        # Configure mocks to return empty/error responses
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.content = b''
        mock_response.json.return_value = {}
        mock_response.text = '{}'
        mock_get.return_value = mock_response
        mock_post.return_value = mock_response
        # Base channel and author
        cls.channel = cls.env["discuss.channel"].create(
            {
                "name": "Coverage Channel",
                "channel_type": "group",
            }
        )
        cls.author = cls.env["res.partner"].create({"name": "Visitor"})
        cls.channel.message_post(
            body="<p>hello</p>",
            author_id=cls.author.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        # Minimal connector attached to channel to satisfy outgo_message calls
        cls.connector = cls.env["discuss_hub.connector"].create(
            {
                "name": "Conn",
                "type": "evolution",  # any plugin that defines outgo_message
                "url": "http://example.com",
                "api_key": "x",
            }
        )
        cls.channel.write({"discuss_hub_connector": cls.connector.id})
        # Bot partner (author for bot replies)
        cls.bot_partner = cls.env["res.partner"].create({"name": "Bot Partner"})
        # Active bot manager record we can reuse
        cls.bot = cls.env["discuss_hub.bot_manager"].create(
            {
                "active": True,
                "bot_type": "generic",
                "bot_url": "http://localhost/bot",
                "bot_api_key": "dummy",
                "partner": [(4, cls.bot_partner.id)],
            }
        )

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        cls.patcher_requests_get.stop()
        cls.patcher_requests_post.stop()
        super().tearDownClass()

    def _patch_connector_plugin(self):
        # Return a stub plugin with a spy-able outgo_message
        dummy = SimpleNamespace()
        dummy.outgo_message = MagicMock(return_value=None)
        return patch.object(
            type(self.connector),
            "get_plugin",
            autospec=True,
            return_value=dummy,
        ), dummy

    def test_process_payload_validation_errors(self):
        # Missing action/channel_id
        res = self.bot.process_payload({})
        self.assertIn("error", res)
        # Unknown action
        res = self.bot.process_payload({"action": "x", "channel_id": self.channel.id})
        self.assertIn("error", res)
        # Channel not found
        res = self.bot.process_payload({"action": "forward", "channel_id": 999999})
        self.assertIn("error", res)
        # Team inactive or not found
        team = self.env["discuss_hub.routing_team"].create(
            {"name": "T", "active": False}
        )
        res = self.bot.process_payload(
            {"action": "forward", "channel_id": self.channel.id, "team_id": team.id}
        )
        self.assertIn("error", res)

    def test_process_payload_forward_agent_success(self):
        # Use current user as agent
        payload = {
            "action": "forward",
            "channel_id": self.channel.id,
            "agent_id": self.env.user.id,
            "note": "Please take it",
        }
        res = self.bot.process_payload(payload)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("action"), "forward")
        self.assertEqual(res.get("channel_id"), self.channel.id)
        # Ensure the agent got access (membership exists)
        member = self.env["discuss.channel.member"].search(
            [
                ("channel_id", "=", self.channel.id),
                ("partner_id", "=", self.env.user.partner_id.id),
            ],
            limit=1,
        )
        self.assertTrue(member, "Expected selected agent to be added as member")

    def test_generic_handle_error_posts_default_message(self):
        # Arrange: mock HTTP failure and plugin
        error_response = SimpleNamespace(status_code=500, content=b"boom", text="err")
        with patch("requests.post", return_value=error_response) as _post:
            patcher, dummy = self._patch_connector_plugin()
            with patcher:
                # Act
                last = self.channel.message_ids[0]
                self.bot.generic_handle(last, self.channel, self.bot_partner)
        # Assert: an error message was posted and sent out via connector
        created = self.channel.message_ids.filtered(
            lambda m: m.body == self.bot.on_error_message
        )
        self.assertTrue(created, "Expected default on_error_message to be posted")
        dummy.outgo_message.assert_called()  # connector invoked

    def test_generic_handle_success_with_mixed_attachments(self):
        # Valid base64 and one invalid chunk
        b64 = "aGVsbG8="  # "hello"
        payload = [
            {
                "text": "OK",
                "audio": b64,
                "video": b64,
                "pdf": b64,
                "image": "!invalid!",  # will be skipped
            }
        ]
        ok_response = SimpleNamespace(
            status_code=200, content=b"x", json=lambda: payload
        )
        with patch("requests.post", return_value=ok_response):
            patcher, dummy = self._patch_connector_plugin()
            with patcher:
                last = self.channel.message_ids[0]
                self.bot.generic_handle(last, self.channel, self.bot_partner)
        # New message posted by bot with 3 attachments (audio, video, pdf)
        bot_msgs = self.channel.message_ids.filtered(
            lambda m: m.author_id == self.bot_partner
        )
        # The most recent bot message
        new_msg = bot_msgs[0]
        self.assertIn("OK", (new_msg.body or ""))
        self.assertEqual(len(new_msg.attachment_ids), 3)
        dummy.outgo_message.assert_called()

    def test_typebot_continue_chat_builds_url_and_strips_prefilled(self):
        # Ensure URL is rebuilt to sessions/<id>/continueChat
        # and prefilledVariables removed
        self.bot.write(
            {"bot_type": "typebot", "bot_url": "http://host/api/v1/typebots/odoo/"}
        )
        payload = {
            "message": {"type": "text", "text": "hi"},
            "prefilledVariables": {"x": 1},
        }

        captured = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return SimpleNamespace(
                ok=True, status_code=200, json=lambda: {"messages": []}
            )

        with patch("requests.post", side_effect=fake_post):
            resp = self.bot.typebot_continue_chat(
                self.channel, "sess123", dict(payload)
            )
        self.assertTrue(resp.ok)
        self.assertTrue(
            captured["url"].endswith("/api/v1/sessions/sess123/continueChat")
        )
        self.assertNotIn("prefilledVariables", captured["json"])  # removed

    def test_outgo_typebot_new_session_posts_text(self):
        # Prepare a bot set to typebot
        self.bot.write(
            {"bot_type": "typebot", "bot_url": "http://host/api/v1/typebots/odoo/"}
        )

        # Mock session fetch to return no session
        with patch.object(
            type(self.bot),
            "typebot_get_latest_session",
            autospec=True,
            return_value=False,
        ):
            # Mock start_chat to return a new session with one text message
            new_session_payload = {
                "sessionId": "sess42",
                "messages": [
                    {"type": "text", "content": {"markdown": "Line1\nLine2"}},
                ],
            }
            start_resp = SimpleNamespace(
                status_code=200, content=b"x", json=lambda: new_session_payload
            )
            with patch.object(
                type(self.bot),
                "typebot_start_chat",
                autospec=True,
                return_value=start_resp,
            ):
                with patch.object(
                    type(self.bot), "typebot_register_new_session", autospec=True
                ):
                    # Avoid real connector sends
                    patcher, dummy = self._patch_connector_plugin()
                    with patcher:
                        ok = self.bot.outgo(self.channel, self.bot_partner)
        self.assertTrue(ok)
        # The bot should have posted the text with <br> replacing newlines
        created = self.channel.message_ids.filtered(
            lambda m: m.author_id == self.bot_partner
        )
        self.assertTrue(created)
        self.assertIn("Line1<br>Line2", str(created[0].body))
        dummy.outgo_message.assert_called()

    def test_typebot_register_new_session_expires_previous(self):
        # Ensure previous sessions are marked expired and a new one is created
        self.bot.write({"bot_type": "typebot"})
        # Two active sessions for this channel
        Session = self.env["discuss_hub.bot_manager.session"]
        s1 = Session.create(
            {
                "bot_manager_id": self.bot.id,
                "channel_id": self.channel.id,
                "session_id": "old1",
            }
        )
        s2 = Session.create(
            {
                "bot_manager_id": self.bot.id,
                "channel_id": self.channel.id,
                "session_id": "old2",
            }
        )
        # Act
        new_s = self.bot.typebot_register_new_session(self.channel, "new123")
        # Assert
        self.assertTrue(new_s)
        self.assertEqual(new_s.session_id, "new123")
        self.assertTrue(
            self.env["discuss_hub.bot_manager.session"].browse(s1.id).expired
        )
        self.assertTrue(
            self.env["discuss_hub.bot_manager.session"].browse(s2.id).expired
        )
