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
from unittest.mock import MagicMock, Mock, patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("discuss_hub", "bot_manager")
class TestBotManagerBase(TransactionCase):
    """Base test class for bot manager with common setup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Mock HTTP requests to prevent external calls during tests
        cls.patcher_requests_get = patch("requests.get")
        cls.patcher_requests_post = patch("requests.post")

        mock_get = cls.patcher_requests_get.start()
        mock_post = cls.patcher_requests_post.start()

        # Configure mocks to return empty/error responses
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.content = b""
        mock_response.json.return_value = {}
        mock_response.text = "{}"
        mock_get.return_value = mock_response
        mock_post.return_value = mock_response

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

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        cls.patcher_requests_get.stop()
        cls.patcher_requests_post.stop()
        super().tearDownClass()


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
        # Odoo wraps plain text in <p> tags
        self.assertIn("Simple text response", bot_message.body)

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
        # Odoo wraps plain text in <p> tags
        self.assertIn("Dict response", bot_message.body)

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
        self.env["discuss_hub.bot_manager.session"].create(
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

        # Manually trigger bot processing
        self.typebot_bot.outgo(self.channel, self.bot_partner)

        # Verify continue chat was called with correct session ID (in URL path)
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        # requests.post(new_url, ...) passes URL as first positional arg
        request_url = (
            call_args.args[0] if hasattr(call_args, "args") else call_args[0][0]
        )
        self.assertIn("existing-session-456", request_url)

    def test_outgo_not_triggered_when_inactive(self):
        # Create a bot manager marked as inactive, linked to a partner
        bot_manager = self.env["discuss_hub.bot_manager"].create(
            {
                "active": False,
                "bot_type": "generic",
                "bot_url": "http://localhost:9999/echo",
                "bot_api_key": "dummy",
                # Link at least one partner through o2m using commands
                "partner": [
                    (
                        0,
                        0,
                        {
                            "name": "Bot Partner",
                        },
                    )
                ],
            }
        )

        # Ensure generic_handle is NOT called when bot is inactive
        with patch.object(
            type(bot_manager), "generic_handle", autospec=True
        ) as mock_generic:
            result = bot_manager.outgo(self.channel, self.bot_partner)
            self.assertFalse(result, "outgo should return False when bot is inactive")
            mock_generic.assert_not_called()

    def test_outgo_returns_false_when_channel_has_no_messages(self):
        """Test that outgo returns False when channel has no messages."""
        # Create a bot manager
        bot_manager = self.env["discuss_hub.bot_manager"].create(
            {
                "active": True,
                "bot_type": "generic",
                "bot_url": "http://localhost:9999/echo",
                "bot_api_key": "dummy",
                "partner": [
                    (
                        0,
                        0,
                        {
                            "name": "Bot Partner",
                        },
                    )
                ],
            }
        )

        # Create a channel without messages
        empty_channel = self.env["discuss.channel"].create(
            {
                "name": "Empty Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        # Ensure outgo returns False when channel has no messages
        result = bot_manager.outgo(empty_channel, self.bot_partner)
        self.assertFalse(
            result, "outgo should return False when channel has no messages"
        )

    def test_respond_to_internal_direct_messages_default_true(self):
        """Test that respond_to_internal_direct_messages defaults to True."""
        bot_manager = self.env["discuss_hub.bot_manager"].create(
            {
                "active": True,
                "bot_type": "generic",
                "bot_url": "http://localhost:9999/echo",
                "bot_api_key": "dummy",
            }
        )
        self.assertTrue(
            bot_manager.respond_to_internal_direct_messages,
            "respond_to_internal_direct_messages should default to True",
        )

    def test_respond_to_internal_direct_messages_can_be_disabled(self):
        """Test that respond_to_internal_direct_messages can be set to False."""
        bot_manager = self.env["discuss_hub.bot_manager"].create(
            {
                "active": True,
                "bot_type": "generic",
                "bot_url": "http://localhost:9999/echo",
                "bot_api_key": "dummy",
                "respond_to_internal_direct_messages": False,
            }
        )
        self.assertFalse(
            bot_manager.respond_to_internal_direct_messages,
            "respond_to_internal_direct_messages should be False when explicitly set",
        )
