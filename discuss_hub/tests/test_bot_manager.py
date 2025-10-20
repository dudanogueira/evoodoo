"""
Comprehensive tests for discuss_hub.bot_manager model.

Tests cover:
- Generic bot type functionality
- Typebot bot type functionality
- Session management for typebot
- Error handling for both bot types
- Payload processing and routing
"""

import base64
from unittest.mock import Mock, patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("discuss_hub", "bot_manager")
class TestBotManagerBase(TransactionCase):
    """Base test class for bot manager with common setup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create connector for channels
        cls.connector = cls.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector",
                "type": "example",
                "enabled": True,
                "uuid": "test-connector-uuid",
                "url": "http://test.example.com",
            }
        )

        # Create test partner (will be used as bot partner)
        cls.bot_partner = cls.env["res.partner"].create(
            {
                "name": "Bot Partner",
                "phone": "+5511988887777",
            }
        )

        # Create test channel
        cls.channel = cls.env["discuss.channel"].create(
            {
                "name": "Test Channel",
                "discuss_hub_connector": cls.connector.id,
                "discuss_hub_outgoing_destination": "+5511999999999",
            }
        )

        # Add bot partner to channel
        cls.channel.channel_partner_ids = [(4, cls.bot_partner.id)]

        # Create test user for author
        cls.test_user = cls.env["res.partner"].create(
            {
                "name": "Test User",
                "phone": "+5511999999999",
            }
        )


@tagged("discuss_hub", "bot_manager", "generic")
class TestGenericBotManager(TestBotManagerBase):
    """Test cases for generic bot type."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create generic bot manager
        cls.generic_bot = cls.env["discuss_hub.bot_manager"].create(
            {
                "bot_type": "generic",
                "bot_url": "https://generic-bot.example.com/webhook",
                "bot_api_key": "test_generic_api_key",
                "bot_url_timeout": 30,
                "on_error_message": "Generic bot error occurred",
                "active": True,
            }
        )

        # Link bot to partner
        cls.bot_partner.bot = cls.generic_bot.id

    def test_generic_bot_creation(self):
        """Test generic bot manager is created with correct attributes."""
        self.assertEqual(self.generic_bot.bot_type, "generic")
        self.assertEqual(
            self.generic_bot.bot_url, "https://generic-bot.example.com/webhook"
        )
        self.assertTrue(self.generic_bot.active)
        self.assertEqual(self.generic_bot.bot_url_timeout, 30)

    @patch("requests.post")
    @patch(
        "odoo.addons.discuss_hub.models.discuss_channel.DiscussChannel._notify_thread"
    )
    def test_generic_bot_successful_text_response(self, mock_notify, mock_post):
        """Test generic bot handling successful text-only response."""
        # Mock _notify_thread to prevent automatic bot triggering
        mock_notify.return_value = None

        # Mock successful bot response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"text": "Hello! How can I help you?"},
            {"text": "I'm here to assist you."},
        ]
        mock_post.return_value = mock_response

        # Create message in channel (without triggering bot automatically)
        message = self.channel.with_context(tracking_disable=True).message_post(
            body="<p>Test message</p>",
            author_id=self.test_user.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Call generic_handle directly (not through automation)
        result = self.generic_bot.generic_handle(
            message, self.channel, self.bot_partner
        )

        # Assertions
        self.assertTrue(result)
        mock_post.assert_called_once()

        # Verify call payload
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs["json"]["message_body"], message.body)
        self.assertEqual(
            call_kwargs["json"]["message_author_name"], self.test_user.name
        )
        self.assertEqual(call_kwargs["json"]["channel_id"], self.channel.id)

        # Check bot posted 2 messages
        bot_messages = self.channel.message_ids.filtered(
            lambda m: m.author_id == self.bot_partner
        )
        self.assertEqual(len(bot_messages), 2)

    @patch("requests.post")
    @patch(
        "odoo.addons.discuss_hub.models.discuss_channel.DiscussChannel._notify_thread"
    )
    def test_generic_bot_with_audio_attachment(self, mock_notify, mock_post):
        """Test generic bot handling message with audio attachment."""
        # Mock _notify_thread to prevent automatic bot triggering
        mock_notify.return_value = None

        # Mock successful bot response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "text": "I received your audio message",
                "audio": base64.b64encode(b"fake audio data").decode("utf-8"),
            }
        ]
        mock_post.return_value = mock_response

        # Create audio attachment
        audio_data = base64.b64encode(b"fake audio data").decode("utf-8")
        attachment = self.env["ir.attachment"].create(
            {
                "name": "test_audio.mp3",
                "datas": audio_data,
                "mimetype": "audio/mpeg",
            }
        )

        # Create message with audio attachment
        message = self.channel.with_context(tracking_disable=True).message_post(
            body="<p>Audio message</p>",
            author_id=self.test_user.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            attachment_ids=[attachment.id],
        )

        # Call generic_handle directly
        result = self.generic_bot.generic_handle(
            message, self.channel, self.bot_partner
        )

        # Assertions
        self.assertTrue(result)

        # Verify audio was sent to bot
        call_kwargs = mock_post.call_args[1]
        self.assertIsNotNone(call_kwargs["json"]["message_audio_base64"])

    @patch("requests.post")
    @patch(
        "odoo.addons.discuss_hub.models.discuss_channel.DiscussChannel._notify_thread"
    )
    def test_generic_bot_timeout_handling(self, mock_notify, mock_post):
        """Test generic bot timeout handling."""
        # Mock _notify_thread to prevent automatic bot triggering
        mock_notify.return_value = None

        import requests

        # Mock timeout exception
        mock_post.side_effect = requests.Timeout("Connection timeout")

        # Create message
        message = self.channel.with_context(tracking_disable=True).message_post(
            body="<p>Test message</p>",
            author_id=self.test_user.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Call generic_handle directly
        result = self.generic_bot.generic_handle(
            message, self.channel, self.bot_partner
        )

        # Should return True but post error message
        self.assertTrue(result)

        # Check error message was posted
        error_messages = self.channel.message_ids.filtered(
            lambda m: m.author_id == self.bot_partner
            and "error occurred" in m.body.lower()
        )
        self.assertEqual(len(error_messages), 1)

    @patch("requests.post")
    @patch(
        "odoo.addons.discuss_hub.models.discuss_channel.DiscussChannel._notify_thread"
    )
    def test_generic_bot_non_200_response(self, mock_notify, mock_post):
        """Test generic bot handling non-200 response."""
        # Mock _notify_thread to prevent automatic bot triggering
        mock_notify.return_value = None

        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.content = b"error"
        mock_post.return_value = mock_response

        # Create message
        message = self.channel.with_context(tracking_disable=True).message_post(
            body="<p>Test message</p>",
            author_id=self.test_user.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Call generic_handle directly
        result = self.generic_bot.generic_handle(
            message, self.channel, self.bot_partner
        )

        # Should post error message
        self.assertTrue(result)
        error_messages = self.channel.message_ids.filtered(
            lambda m: m.author_id == self.bot_partner
            and self.generic_bot.on_error_message in m.body
        )
        self.assertEqual(len(error_messages), 1)

    @patch("requests.post")
    @patch(
        "odoo.addons.discuss_hub.models.discuss_channel.DiscussChannel._notify_thread"
    )
    def test_generic_bot_multiple_attachment_types(self, mock_notify, mock_post):
        """Test generic bot handling multiple attachment types."""
        # Mock _notify_thread to prevent automatic bot triggering
        mock_notify.return_value = None

        # Mock response with multiple attachment types
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "text": "Here are multiple files",
                "audio": base64.b64encode(b"audio data").decode("utf-8"),
                "video": base64.b64encode(b"video data").decode("utf-8"),
                "pdf": base64.b64encode(b"pdf data").decode("utf-8"),
            }
        ]
        mock_post.return_value = mock_response

        # Create message
        message = self.channel.with_context(tracking_disable=True).message_post(
            body="<p>Send me files</p>",
            author_id=self.test_user.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Call generic_handle directly
        result = self.generic_bot.generic_handle(
            message, self.channel, self.bot_partner
        )

        # Assertions
        self.assertTrue(result)

        # Check bot message has 3 attachments
        bot_message = self.channel.message_ids.filtered(
            lambda m: m.author_id == self.bot_partner
        )[-1]
        self.assertEqual(len(bot_message.attachment_ids), 3)

    @patch(
        "odoo.addons.discuss_hub.models.discuss_channel.DiscussChannel._notify_thread"
    )
    @patch("requests.post")
    def test_generic_bot_string_response(self, mock_post, mock_notify):
        """Test generic bot handling string response (instead of list/dict)."""
        # Mock _notify_thread to prevent automatic bot triggering
        mock_notify.return_value = None

        # Mock response with simple string
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = "Simple text response"
        mock_post.return_value = mock_response

        # Create message
        message = self.channel.with_context(tracking_disable=True).message_post(
            body="<p>Hello</p>",
            author_id=self.test_user.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Call generic_handle directly
        result = self.generic_bot.generic_handle(
            message, self.channel, self.bot_partner
        )

        # Assertions
        self.assertTrue(result)

        # Check bot message was posted with correct content
        bot_message = self.channel.message_ids.filtered(
            lambda m: m.author_id == self.bot_partner
        )[-1]
        self.assertEqual(bot_message.body, "Simple text response")

    @patch(
        "odoo.addons.discuss_hub.models.discuss_channel.DiscussChannel._notify_thread"
    )
    @patch("requests.post")
    def test_generic_bot_dict_response(self, mock_post, mock_notify):
        """Test generic bot handling dict response (instead of list)."""
        # Mock _notify_thread to prevent automatic bot triggering
        mock_notify.return_value = None

        # Mock response with single dict
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "Dict response"}
        mock_post.return_value = mock_response

        # Create message
        message = self.channel.with_context(tracking_disable=True).message_post(
            body="<p>Hello</p>",
            author_id=self.test_user.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Call generic_handle directly
        result = self.generic_bot.generic_handle(
            message, self.channel, self.bot_partner
        )

        # Assertions
        self.assertTrue(result)

        # Check bot message was posted
        bot_message = self.channel.message_ids.filtered(
            lambda m: m.author_id == self.bot_partner
        )[-1]
        self.assertEqual(bot_message.body, "Dict response")

    @patch(
        "odoo.addons.discuss_hub.models.discuss_channel.DiscussChannel._notify_thread"
    )
    @patch("requests.post")
    def test_generic_bot_invalid_json_response(self, mock_post, mock_notify):
        """Test generic bot handling invalid JSON response."""
        # Mock _notify_thread to prevent automatic bot triggering
        mock_notify.return_value = None

        # Mock response with invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response

        # Create message
        message = self.channel.with_context(tracking_disable=True).message_post(
            body="<p>Hello</p>",
            author_id=self.test_user.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Call generic_handle directly
        result = self.generic_bot.generic_handle(
            message, self.channel, self.bot_partner
        )

        # Assertions - should return False for invalid JSON
        self.assertFalse(result)


@tagged("discuss_hub", "bot_manager", "typebot")
class TestTypebotBotManager(TestBotManagerBase):
    """Test cases for typebot bot type."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create typebot bot manager
        cls.typebot_bot = cls.env["discuss_hub.bot_manager"].create(
            {
                "bot_type": "typebot",
                "bot_url": "http://typebot.example.com/api/v1/typebots/test-bot/",
                "bot_api_key": "test_typebot_api_key",
                "bot_url_timeout": 60,
                "on_error_message": "Typebot error occurred",
                "active": True,
            }
        )

        # Link bot to partner
        cls.bot_partner.bot = cls.typebot_bot.id

    def test_typebot_bot_creation(self):
        """Test typebot bot manager is created with correct attributes."""
        self.assertEqual(self.typebot_bot.bot_type, "typebot")
        self.assertTrue("api/v1/typebots" in self.typebot_bot.bot_url)
        self.assertTrue(self.typebot_bot.active)

    @patch("requests.post")
    @patch(
        "odoo.addons.discuss_hub.models.discuss_channel.DiscussChannel._notify_thread"
    )
    def test_typebot_start_chat_new_session(self, mock_notify, mock_post):
        """Test typebot starting a new chat session."""
        # Mock _notify_thread to prevent automatic bot triggering
        mock_notify.return_value = None

        # Mock successful start chat response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "sessionId": "new-session-123",
            "messages": [
                {"type": "text", "content": {"markdown": "Welcome! How can I help?"}}
            ],
        }
        mock_post.return_value = mock_response

        # Create message (without triggering bot automatically)
        self.channel.with_context(tracking_disable=True).message_post(
            body="<p>Hello typebot</p>",
            author_id=self.test_user.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Call outgo directly (which internally calls typebot_start_chat)
        result = self.typebot_bot.outgo(self.channel, self.bot_partner)

        # Assertions
        self.assertTrue(result)

        # Check session was created
        session = self.env["discuss_hub.bot_manager.session"].search(
            [
                ("bot_manager_id", "=", self.typebot_bot.id),
                ("channel_id", "=", self.channel.id),
            ]
        )
        self.assertEqual(len(session), 1)
        self.assertEqual(session.session_id, "new-session-123")
        self.assertFalse(session.expired)

    @patch("requests.post")
    @patch(
        "odoo.addons.discuss_hub.models.discuss_channel.DiscussChannel._notify_thread"
    )
    def test_typebot_continue_chat_existing_session(self, mock_notify, mock_post):
        """Test typebot continuing an existing chat session."""
        # Mock _notify_thread to prevent automatic bot triggering
        mock_notify.return_value = None

        # Create existing session
        existing_session = self.env["discuss_hub.bot_manager.session"].create(
            {
                "bot_manager_id": self.typebot_bot.id,
                "channel_id": self.channel.id,
                "session_id": "existing-session-456",
                "expired": False,
            }
        )

        # Mock successful continue chat response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.json.return_value = {
            "messages": [
                {"type": "text", "content": {"markdown": "Continuing our chat..."}}
            ]
        }
        mock_post.return_value = mock_response

        # Create message (without triggering bot automatically)
        self.channel.with_context(tracking_disable=True).message_post(
            body="<p>Continue chat</p>",
            author_id=self.test_user.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Call outgo directly
        result = self.typebot_bot.outgo(self.channel, self.bot_partner)

        # Assertions
        self.assertTrue(result)

        # Session should still exist and not be expired
        existing_session.invalidate_recordset()
        self.assertFalse(existing_session.expired)

    @patch("requests.post")
    @patch(
        "odoo.addons.discuss_hub.models.discuss_channel.DiscussChannel._notify_thread"
    )
    def test_typebot_session_expired_creates_new(self, mock_notify, mock_post):
        """Test typebot creates new session when existing one is expired/invalid."""
        # Mock _notify_thread to prevent automatic bot triggering
        mock_notify.return_value = None

        # Create expired session
        old_session = self.env["discuss_hub.bot_manager.session"].create(
            {
                "bot_manager_id": self.typebot_bot.id,
                "channel_id": self.channel.id,
                "session_id": "old-session-789",
                "expired": False,
            }
        )

        # Mock 404 for continue chat, then success for start chat
        mock_404_response = Mock()
        mock_404_response.status_code = 404
        mock_404_response.ok = False

        mock_success_response = Mock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {
            "sessionId": "new-session-abc",
            "messages": [
                {"type": "text", "content": {"markdown": "New session started"}}
            ],
        }

        # First call returns 404, second call returns success
        mock_post.side_effect = [mock_404_response, mock_success_response]

        # Create message (without triggering bot automatically)
        self.channel.with_context(tracking_disable=True).message_post(
            body="<p>Test expired session</p>",
            author_id=self.test_user.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Call outgo directly
        result = self.typebot_bot.outgo(self.channel, self.bot_partner)

        # Assertions
        self.assertTrue(result)

        # Old session should be expired
        old_session.invalidate_recordset()
        self.assertTrue(old_session.expired)

        # New session should exist
        new_session = self.env["discuss_hub.bot_manager.session"].search(
            [
                ("bot_manager_id", "=", self.typebot_bot.id),
                ("channel_id", "=", self.channel.id),
                ("expired", "=", False),
            ]
        )
        self.assertEqual(len(new_session), 1)
        self.assertEqual(new_session.session_id, "new-session-abc")

    @patch("requests.post")
    @patch("requests.get")
    @patch(
        "odoo.addons.discuss_hub.models.discuss_channel.DiscussChannel._notify_thread"
    )
    def test_typebot_image_attachment(self, mock_notify, mock_get, mock_post):
        """Test typebot handling image attachments."""
        # Mock _notify_thread to prevent automatic bot triggering
        mock_notify.return_value = None

        # Mock start chat with image response
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {
            "sessionId": "session-with-image",
            "messages": [
                {
                    "type": "image",
                    "content": {"url": "https://example.com/image.png"},
                }
            ],
        }
        mock_post.return_value = mock_post_response

        # Mock image download
        mock_get_response = Mock()
        mock_get_response.ok = True
        mock_get_response.content = b"fake image data"
        mock_get_response.headers = {"Content-Type": "image/png"}
        mock_get.return_value = mock_get_response

        # Create message (without triggering bot automatically)
        self.channel.with_context(tracking_disable=True).message_post(
            body="<p>Send me an image</p>",
            author_id=self.test_user.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Call outgo directly
        result = self.typebot_bot.outgo(self.channel, self.bot_partner)

        # Assertions
        self.assertTrue(result)

        # Check bot message has attachment
        bot_message = self.channel.message_ids.filtered(
            lambda m: m.author_id == self.bot_partner
        )[-1]
        self.assertEqual(len(bot_message.attachment_ids), 1)

    @patch("requests.post")
    @patch(
        "odoo.addons.discuss_hub.models.discuss_channel.DiscussChannel._notify_thread"
    )
    def test_typebot_markdown_newline_conversion(self, mock_notify, mock_post):
        """Test typebot converts markdown newlines to HTML breaks."""
        # Mock _notify_thread to prevent automatic bot triggering
        mock_notify.return_value = None

        # Mock response with markdown containing newlines
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "sessionId": "markdown-session",
            "messages": [
                {
                    "type": "text",
                    "content": {"markdown": "Line 1\nLine 2\nLine 3"},
                }
            ],
        }
        mock_post.return_value = mock_response

        # Create message (without triggering bot automatically)
        self.channel.with_context(tracking_disable=True).message_post(
            body="<p>Multi-line test</p>",
            author_id=self.test_user.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        # Call outgo directly
        result = self.typebot_bot.outgo(self.channel, self.bot_partner)

        # Assertions
        self.assertTrue(result)

        # Check message has <br> tags instead of \n
        bot_message = self.channel.message_ids.filtered(
            lambda m: m.author_id == self.bot_partner
        )[-1]
        self.assertIn("<br>", bot_message.body)
        self.assertNotIn("\n", bot_message.body)


@tagged("discuss_hub", "bot_manager", "routing")
class TestBotManagerRouting(TestBotManagerBase):
    """Test cases for bot manager routing and payload processing."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Mock HTTP requests for all tests in this class
        cls.patcher = patch("requests.post")
        cls.mock_post = cls.patcher.start()
        # Configure mock to return a successful response
        cls.mock_post.return_value.status_code = 200
        cls.mock_post.return_value.json.return_value = {"status": "ok"}

        # Create bot manager for routing tests
        cls.routing_bot = cls.env["discuss_hub.bot_manager"].create(
            {
                "bot_type": "generic",
                "bot_url": "https://routing-bot.example.com/webhook",
                "bot_api_key": "routing_api_key",
                "active": True,
            }
        )

        # Link bot to partner
        cls.bot_partner.bot = cls.routing_bot.id

        # Create routing team
        cls.routing_team = cls.env["discuss_hub.routing_team"].create(
            {
                "name": "Test Routing Team",
                "active": True,
            }
        )

        # Create agent user (not just partner)
        cls.agent_partner = cls.env["res.partner"].create(
            {
                "name": "Agent Partner",
                "phone": "+5511988886666",
            }
        )

        cls.agent_user = cls.env["res.users"].create(
            {
                "name": "Agent User",
                "login": "agent_user",
                "partner_id": cls.agent_partner.id,
            }
        )

        # Add agent to team (create team member record)
        cls.env["discuss_hub.routing_team_member"].create(
            {
                "team_id": cls.routing_team.id,
                "user_id": cls.agent_user.id,
                "order": 1,
                "count": 0,
            }
        )

    @classmethod
    def tearDownClass(cls):
        """Stop the HTTP request patcher."""
        cls.patcher.stop()
        super().tearDownClass()

    def test_process_payload_forward_action(self):
        """Test bot manager processing forward action payload."""
        payload = {
            "action": "forward",
            "channel_id": self.channel.id,
            "team_id": self.routing_team.id,
            "note": "Test forward action",
        }

        result = self.routing_bot.process_payload(payload)

        # Assertions
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("action"), "forward")
        self.assertEqual(result.get("channel_id"), self.channel.id)

    def test_process_payload_missing_required_fields(self):
        """Test bot manager handling payload with missing required fields."""
        payload = {
            "action": "forward",
            # missing channel_id
        }

        result = self.routing_bot.process_payload(payload)

        # Should return error
        self.assertIn("error", result)
        self.assertIn("required fields", result["error"].lower())

    def test_process_payload_invalid_channel(self):
        """Test bot manager handling payload with invalid channel ID."""
        payload = {
            "action": "forward",
            "channel_id": 999999,  # non-existent channel
            "team_id": self.routing_team.id,
        }

        result = self.routing_bot.process_payload(payload)

        # Should return error
        self.assertIn("error", result)
        self.assertIn("not found", result["error"].lower())

    def test_process_payload_inactive_team(self):
        """Test bot manager handling payload with inactive team."""
        # Deactivate team
        self.routing_team.active = False

        payload = {
            "action": "forward",
            "channel_id": self.channel.id,
            "team_id": self.routing_team.id,
        }

        result = self.routing_bot.process_payload(payload)

        # Should return error
        self.assertIn("error", result)
        self.assertIn("not active", result["error"].lower())

    def test_process_payload_unknown_action(self):
        """Test bot manager handling payload with unknown action."""
        payload = {
            "action": "unknown_action",
            "channel_id": self.channel.id,
        }

        result = self.routing_bot.process_payload(payload)

        # Should return error
        self.assertIn("error", result)
        self.assertIn("unknown action", result["error"].lower())

    def test_process_payload_forward_to_specific_agent(self):
        """Test bot manager forwarding to specific agent."""
        payload = {
            "action": "forward",
            "channel_id": self.channel.id,
            "agent_id": self.agent_user.id,
            "note": "Forward to specific agent",
        }

        result = self.routing_bot.process_payload(payload)

        # Assertions
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("action"), "forward")


@tagged("discuss_hub", "bot_manager", "session")
class TestBotManagerSession(TestBotManagerBase):
    """Test cases for bot manager session model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create typebot bot manager
        cls.typebot_bot = cls.env["discuss_hub.bot_manager"].create(
            {
                "bot_type": "typebot",
                "bot_url": "http://typebot.example.com/api/v1/typebots/session-test/",
                "bot_api_key": "session_test_key",
                "active": True,
            }
        )

    def test_session_creation(self):
        """Test session record creation."""
        session = self.env["discuss_hub.bot_manager.session"].create(
            {
                "bot_manager_id": self.typebot_bot.id,
                "channel_id": self.channel.id,
                "session_id": "test-session-001",
            }
        )

        self.assertEqual(session.bot_manager_id, self.typebot_bot)
        self.assertEqual(session.channel_id, self.channel)
        self.assertEqual(session.session_id, "test-session-001")
        self.assertFalse(session.expired)

    def test_typebot_get_latest_session(self):
        """Test getting latest non-expired session."""
        # Create multiple sessions
        self.env["discuss_hub.bot_manager.session"].create(
            {
                "bot_manager_id": self.typebot_bot.id,
                "channel_id": self.channel.id,
                "session_id": "old-session",
                "expired": True,
            }
        )

        latest_session = self.env["discuss_hub.bot_manager.session"].create(
            {
                "bot_manager_id": self.typebot_bot.id,
                "channel_id": self.channel.id,
                "session_id": "latest-session",
                "expired": False,
            }
        )

        # Get latest session
        result = self.typebot_bot.typebot_get_latest_session(self.channel)

        # Should return the latest non-expired session
        self.assertEqual(result, latest_session)
        self.assertEqual(result.session_id, "latest-session")

    def test_typebot_register_new_session_expires_old(self):
        """Test registering new session expires old ones."""
        # Create existing session
        old_session = self.env["discuss_hub.bot_manager.session"].create(
            {
                "bot_manager_id": self.typebot_bot.id,
                "channel_id": self.channel.id,
                "session_id": "old-session",
                "expired": False,
            }
        )

        # Register new session
        new_session = self.typebot_bot.typebot_register_new_session(
            self.channel, "new-session-id"
        )

        # Old session should be expired
        old_session.invalidate_recordset()
        self.assertTrue(old_session.expired)

        # New session should not be expired
        self.assertFalse(new_session.expired)
        self.assertEqual(new_session.session_id, "new-session-id")

    def test_multiple_channels_separate_sessions(self):
        """Test that different channels have separate sessions."""
        # Create another channel
        channel2 = self.env["discuss.channel"].create(
            {
                "name": "Test Channel 2",
                "discuss_hub_connector": self.connector.id,
            }
        )

        # Create sessions for both channels
        session1 = self.env["discuss_hub.bot_manager.session"].create(
            {
                "bot_manager_id": self.typebot_bot.id,
                "channel_id": self.channel.id,
                "session_id": "session-channel-1",
                "expired": False,
            }
        )

        session2 = self.env["discuss_hub.bot_manager.session"].create(
            {
                "bot_manager_id": self.typebot_bot.id,
                "channel_id": channel2.id,
                "session_id": "session-channel-2",
                "expired": False,
            }
        )

        # Get latest session for each channel
        latest1 = self.typebot_bot.typebot_get_latest_session(self.channel)
        latest2 = self.typebot_bot.typebot_get_latest_session(channel2)

        # Each channel should have its own session
        self.assertEqual(latest1, session1)
        self.assertEqual(latest2, session2)
        self.assertNotEqual(latest1, latest2)
