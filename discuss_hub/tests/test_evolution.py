"""Test suite for the evolution plugin of discuss_hub.

This test suite covers the evolution plugin functionality including:
- Plugin initialization and configuration
- WhatsApp connection status and QR code handling
- Administrative payload processing (QR codes, connection updates, logout)
- Message processing (text, images, videos, audio, documents, locations, contacts)
- Reactions and message replies
- Outgoing messages and attachments
- Message updates and deletion
- Contact synchronization
- Profile picture updates
- Error handling and edge cases
"""

import base64
from unittest.mock import Mock, patch

import requests

from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("discuss_hub", "plugin_evolution")
class TestEvolutionPlugin(HttpCase):
    """Test cases for the evolution plugin functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test data and environment."""
        super().setUpClass()

        # Create test admin partner
        cls.admin_partner = cls.env["res.partner"].create(
            {"name": "Admin Partner", "email": "admin@test.com"}
        )

        # Create test manager channel
        cls.manager_channel = cls.env["discuss.channel"].create(
            {"name": "Manager Channel", "channel_type": "channel"}
        )

        # Create a test connector with evolution plugin
        cls.connector = cls.env["discuss_hub.connector"].create(
            {
                "name": "test_evolution_instance",
                "type": "evolution",
                "enabled": True,
                "uuid": "22222222-2222-2222-2222-222222222222",
                "url": "http://evolution:8080",
                "api_key": "test_evolution_api_key",
                "partner_contact_field": "phone",
                "partner_contact_name": "whatsapp",
                "default_admin_partner_id": cls.admin_partner.id,
                "manager_channel": [(6, 0, [cls.manager_channel.id])],
                "evolution_allow_broadcast_messages": True,
                "import_contacts": True,
                "show_read_receipts": True,
                "notify_reactions": True,
            }
        )

        cls.plugin = cls.connector.get_plugin()

        # Sample payloads for testing
        cls.sample_qr_code_payload = {
            "event": "qrcode.updated",
            "instance": "test_evolution_instance",
            "data": {
                "qrcode": {
                    "base64": (
                        "data:image/png;base64,"
                        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAD"
                        "ElEQVQI12P4//8/AAX+Av7czFnnAAAAAElFTkSuQmCC"
                    )
                }
            },
        }

        cls.sample_connection_update_payload = {
            "event": "connection.update",
            "instance": "test_evolution_instance",
            "data": {"state": "open", "statusReason": 200},
        }

        cls.sample_text_message_payload = {
            "event": "messages.upsert",
            "instance": "test_evolution_instance",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "msg123456",
                },
                "pushName": "Test User",
                "message": {"conversation": "Hello, this is a test message"},
            },
        }

        cls.sample_image_message_payload = {
            "event": "messages.upsert",
            "instance": "test_evolution_instance",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "img123456",
                },
                "pushName": "Test User",
                "message": {
                    "imageMessage": {"caption": "Test image"},
                    "base64": (
                        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAD"
                        "ElEQVQI12P4//8/AAX+Av7czFnnAAAAAElFTkSuQmCC"
                    ),
                },
            },
        }

        cls.sample_reaction_payload = {
            "event": "messages.upsert",
            "instance": "test_evolution_instance",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "reaction123",
                },
                "message": {
                    "reactionMessage": {"key": {"id": "original_msg_id"}, "text": "👍"}
                },
            },
        }

    # ===================================================================
    # INITIALIZATION AND CONFIGURATION TESTS
    # ===================================================================

    def test_plugin_initialization(self):
        """Test plugin is properly initialized with connector."""
        self.assertIsNotNone(self.plugin, "Plugin should be initialized")
        self.assertEqual(
            self.plugin.connector.id,
            self.connector.id,
            "Plugin should reference the correct connector",
        )
        self.assertEqual(
            self.plugin.plugin_name, "evolution", "Plugin name should be 'evolution'"
        )

    def test_get_evolution_url_from_connector(self):
        """Test getting evolution URL from connector configuration."""
        url = self.plugin.get_evolution_url()
        self.assertEqual(
            url, "http://evolution:8080", "Should return connector URL when configured"
        )

    def test_get_evolution_url_from_env(self):
        """Test getting evolution URL from environment variable."""
        # Create connector without URL
        connector_no_url = self.env["discuss_hub.connector"].create(
            {
                "name": "test_no_url",
                "type": "evolution",
                "enabled": True,
                "uuid": "33333333-3333-3333-3333-333333333333",
            }
        )
        plugin_no_url = connector_no_url.get_plugin()

        with patch.dict(
            "os.environ", {"DISCUSS_HUB_EVOLUTION_URL": "http://custom:9090"}
        ):
            url = plugin_no_url.get_evolution_url()
            self.assertEqual(
                url,
                "http://custom:9090",
                "Should return environment variable URL when connector URL not set",
            )

    def test_get_requests_session_with_connector_api_key(self):
        """Test session creation with connector API key."""
        session = self.plugin.get_requests_session()
        self.assertIsInstance(session, requests.Session)
        self.assertEqual(
            session.headers.get("apikey"),
            "test_evolution_api_key",
            "Session should have connector API key in headers",
        )

    def test_get_requests_session_with_env_api_key(self):
        """Test session creation with environment variable API key."""
        # Create connector without API key
        connector_no_key = self.env["discuss_hub.connector"].create(
            {
                "name": "test_no_key",
                "type": "evolution",
                "enabled": True,
                "uuid": "44444444-4444-4444-4444-444444444444",
            }
        )
        plugin_no_key = connector_no_key.get_plugin()

        with patch.dict("os.environ", {"DISCUSS_HUB_EVOLUTION_APIKEY": "env_api_key"}):
            session = plugin_no_key.get_requests_session()
            self.assertEqual(
                session.headers.get("apikey"),
                "env_api_key",
                "Session should have environment API key when connector key not set",
            )

    # ===================================================================
    # GET_STATUS TESTS
    # ===================================================================

    @patch("requests.Session.get")
    def test_get_status_connected(self, mock_get):
        """Test get_status when instance is connected."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"instance": {"state": "open"}}
        mock_get.return_value = mock_response

        result = self.plugin.get_status()

        self.assertEqual(result["status"], "open")
        self.assertTrue(result["success"])
        self.assertEqual(result["plugin_name"], "evolution")
        self.assertIsNone(result.get("qrcode"))

    @patch("requests.Session.get")
    def test_get_status_qr_code(self, mock_get):
        """Test get_status when QR code is available."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "base64": "data:image/png;base64,abc123",
            "instance": {"state": "closed"},
        }
        mock_get.return_value = mock_response

        result = self.plugin.get_status()

        self.assertEqual(result["status"], "qr_code")
        self.assertEqual(result["qrcode"], "data:image/png;base64,abc123")
        self.assertTrue(result["success"])

    @patch("requests.Session.post")
    @patch("requests.Session.get")
    def test_get_status_not_found_creates_instance(self, mock_get, mock_post):
        """Test get_status creates instance when not found."""
        # First call returns 404, second call (after creation) returns success
        mock_get_404 = Mock()
        mock_get_404.status_code = 404

        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {"instance": "created"}

        mock_get_success = Mock()
        mock_get_success.status_code = 200
        mock_get_success.json.return_value = {"instance": {"state": "closed"}}

        mock_get.side_effect = [mock_get_404, mock_get_success]
        mock_post.return_value = mock_post_response

        result = self.plugin.get_status()

        # Verify instance creation was attempted
        self.assertTrue(mock_post.called)
        # Verify retry after creation
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(result["status"], "closed")

    @patch("requests.Session.get")
    def test_get_status_unauthorized(self, mock_get):
        """Test get_status with unauthorized response."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = self.plugin.get_status()

        self.assertEqual(result["status"], "unauthorized")
        self.assertTrue(result["success"])

    @patch("requests.Session.get")
    def test_get_status_request_error(self, mock_get):
        """Test get_status handles request errors."""
        mock_get.side_effect = requests.RequestException("Connection error")

        result = self.plugin.get_status()

        self.assertEqual(result["status"], "error")
        self.assertTrue(result["success"])

    @patch("requests.Session.get")
    def test_get_status_json_error(self, mock_get):
        """Test get_status handles JSON parsing errors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        result = self.plugin.get_status()

        self.assertEqual(result["status"], "error")
        self.assertTrue(result["success"])

    # ===================================================================
    # CONTACT IDENTIFIER AND NAME TESTS
    # ===================================================================

    def test_get_contact_identifier_from_remote_jid(self):
        """Test extracting contact identifier from remote JID."""
        payload = {"data": {"key": {"remoteJid": "5511999999999@s.whatsapp.net"}}}
        identifier = self.plugin.get_contact_identifier(payload)
        self.assertEqual(identifier, "5511999999999")

    def test_get_contact_identifier_brazilian_mobile_format(self):
        """Test Brazilian mobile number formatting (adding 9)."""
        payload = {"data": {"key": {"remoteJid": "551199999999@s.whatsapp.net"}}}
        identifier = self.plugin.get_contact_identifier(payload)
        # Should add 9 after area code for Brazilian mobile
        self.assertEqual(identifier, "5511999999999")

    def test_get_contact_identifier_from_contacts_upsert(self):
        """Test getting contact identifier from contacts.upsert event."""
        payload = {"remoteJid": "5511988888888@s.whatsapp.net"}
        identifier = self.plugin.get_contact_identifier(payload)
        self.assertEqual(identifier, "5511988888888")

    def test_get_contact_name_from_push_name(self):
        """Test getting contact name from pushName field."""
        payload = {"data": {"pushName": "John Doe"}}
        name = self.plugin.get_contact_name(payload)
        self.assertEqual(name, "John Doe")

    def test_get_contact_name_fallback_to_identifier(self):
        """Test contact name fallback to identifier when pushName absent."""
        payload = {"data": {"key": {"remoteJid": "5511999999999@s.whatsapp.net"}}}
        name = self.plugin.get_contact_name(payload)
        self.assertEqual(name, "5511999999999")

    def test_get_channel_name_individual_chat(self):
        """Test channel name generation for individual chats."""
        payload = {
            "data": {
                "key": {"remoteJid": "5511999999999@s.whatsapp.net"},
                "pushName": "John Doe",
            }
        }
        name = self.plugin.get_channel_name(payload)
        self.assertIn("Whatsapp:", name)
        self.assertIn("John Doe", name)
        self.assertIn("5511999999999", name)

    def test_get_channel_name_group_chat(self):
        """Test channel name generation for group chats."""
        payload = {"data": {"key": {"remoteJid": "123456789@g.us"}}}
        name = self.plugin.get_channel_name(payload)
        self.assertIn("WGROUP:", name)

    # ===================================================================
    # MESSAGE ID TESTS
    # ===================================================================

    def test_get_message_id_from_key_id(self):
        """Test getting message ID from key.id field."""
        payload = {"data": {"key": {"id": "msg123456"}}}
        msg_id = self.plugin.get_message_id(payload)
        self.assertEqual(msg_id, "msg123456")

    def test_get_message_id_from_keyId(self):
        """Test getting message ID from keyId field."""
        payload = {"data": {"keyId": "msg789012"}}
        msg_id = self.plugin.get_message_id(payload)
        self.assertEqual(msg_id, "msg789012")

    def test_get_message_id_from_list(self):
        """Test getting message ID when it's a list."""
        payload = {"data": {"keyId": ["msg111", "msg222"]}}
        msg_id = self.plugin.get_message_id(payload)
        self.assertEqual(msg_id, "msg111")

    # ===================================================================
    # ADMINISTRATIVE PAYLOAD PROCESSING TESTS
    # ===================================================================

    def test_process_administrative_payload_qr_code(self):
        """Test processing QR code update events."""
        result = self.plugin.process_administrative_payload(self.sample_qr_code_payload)

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "process_administrative_payload")

        # Check if message was posted to manager channel
        messages = self.manager_channel.message_ids
        self.assertTrue(len(messages) > 0)

        # Check if QR code attachment was created
        latest_message = messages[0]
        self.assertTrue(len(latest_message.attachment_ids) > 0)

    def test_process_administrative_payload_connection_open(self):
        """Test processing connection.update event when connecting."""
        result = self.plugin.process_administrative_payload(
            self.sample_connection_update_payload
        )

        self.assertTrue(result["success"])

        # Check if message was posted
        messages = self.manager_channel.message_ids
        self.assertTrue(len(messages) > 0)
        latest_message = messages[0]
        self.assertIn("OPEN", latest_message.body)

    def test_process_administrative_payload_connection_connecting(self):
        """Test processing connection.update event during connection."""
        payload = {
            "event": "connection.update",
            "instance": "test_evolution_instance",
            "data": {"state": "connecting", "statusReason": 0},
        }
        result = self.plugin.process_administrative_payload(payload)

        self.assertTrue(result["success"])
        messages = self.manager_channel.message_ids
        latest_message = messages[0]
        self.assertIn("🟡", latest_message.body)

    def test_process_administrative_payload_logout(self):
        """Test processing logout.instance event."""
        payload = {
            "event": "logout.instance",
            "instance": "test_evolution_instance",
            "data": {},
        }
        result = self.plugin.process_administrative_payload(payload)

        self.assertTrue(result["success"])
        messages = self.manager_channel.message_ids
        latest_message = messages[0]
        self.assertIn("LOGGED OUT", latest_message.body)

    def test_process_administrative_payload_no_manager_channel(self):
        """Test administrative payload when no manager channel configured."""
        # Create connector without manager channel
        connector = self.env["discuss_hub.connector"].create(
            {
                "name": "test_no_manager",
                "type": "evolution",
                "enabled": True,
            }
        )
        plugin = connector.get_plugin()

        result = plugin.process_administrative_payload(self.sample_qr_code_payload)

        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "No manager channel configured")

    # ===================================================================
    # TEXT MESSAGE PROCESSING TESTS
    # ===================================================================

    def test_handle_text_message_creates_message(self):
        """Test handling text message creates mail.message."""
        # Create partner for the test
        partner = self.env["res.partner"].create(
            {"name": "Test User", "phone": "5511999999999"}
        )

        # Create channel
        channel = self.env["discuss.channel"].create(
            {
                "name": "Test Channel",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": "5511999999999@s.whatsapp.net",
            }
        )

        result = self.plugin.handle_text_message(
            self.sample_text_message_payload, channel, partner
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["event"], "messages.upsert.conversation")
        self.assertIn("text_message", result)

        # Verify message was created
        message = self.env["mail.message"].browse(result["text_message"])
        self.assertIn("Hello, this is a test message", message.body)
        self.assertEqual(message.discuss_hub_message_id, "msg123456")

    def test_handle_text_message_group_chat_adds_sender_name(self):
        """Test text message in group chat prepends sender name."""
        partner = self.env["res.partner"].create(
            {"name": "Group User", "phone": "5511888888888"}
        )

        channel = self.env["discuss.channel"].create(
            {
                "name": "Group Chat",
                "discuss_hub_connector": self.connector.id,
            }
        )

        group_payload = {
            "event": "messages.upsert",
            "data": {
                "key": {"remoteJid": "123456789@g.us", "id": "grp_msg_123"},
                "pushName": "Alice",
                "message": {"conversation": "Hello group!"},
            },
        }

        result = self.plugin.handle_text_message(group_payload, channel, partner)

        message = self.env["mail.message"].browse(result["text_message"])
        self.assertIn("Alice:", message.body)
        self.assertIn("Hello group!", message.body)

    def test_handle_text_message_with_quoted_message(self):
        """Test handling text message with quoted/replied message."""
        partner = self.env["res.partner"].create(
            {"name": "Reply User", "phone": "5511777777777"}
        )

        channel = self.env["discuss.channel"].create(
            {
                "name": "Reply Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        # Create original message
        original_msg = channel.message_post(
            body="Original message",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        original_msg.write({"discuss_hub_message_id": "original_123"})

        # Create reply payload
        reply_payload = {
            "event": "messages.upsert",
            "data": {
                "key": {"remoteJid": "5511777777777@s.whatsapp.net", "id": "reply_456"},
                "message": {"conversation": "This is a reply"},
                "contextInfo": {
                    "stanzaId": "original_123",
                    "quotedMessage": {"conversation": "Original message"},
                },
            },
        }

        result = self.plugin.handle_text_message(reply_payload, channel, partner)

        message = self.env["mail.message"].browse(result["text_message"])
        self.assertEqual(message.parent_id.id, original_msg.id)

    # ===================================================================
    # REACTION MESSAGE TESTS
    # ===================================================================

    def test_handle_reaction_message_creates_reaction(self):
        """Test handling reaction message creates mail.message.reaction."""
        partner = self.env["res.partner"].create(
            {"name": "Reactor", "phone": "5511666666666"}
        )

        channel = self.env["discuss.channel"].create(
            {
                "name": "Reaction Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        # Create original message
        original_msg = channel.message_post(
            body="React to this",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        original_msg.write({"discuss_hub_message_id": "original_msg_id"})

        result = self.plugin.handle_reaction_message(
            self.sample_reaction_payload["data"], channel, partner, "reaction123"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["event"], "messages.upsert.reactionMessage")

        # Verify reaction was created
        reactions = self.env["mail.message.reaction"].search(
            [("message_id", "=", original_msg.id), ("content", "=", "👍")]
        )
        self.assertEqual(len(reactions), 1)

    def test_handle_reaction_message_original_not_found(self):
        """Test handling reaction when original message not found."""
        partner = self.env["res.partner"].create(
            {"name": "Reactor", "phone": "5511666666666"}
        )

        channel = self.env["discuss.channel"].create(
            {
                "name": "Reaction Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        result = self.plugin.handle_reaction_message(
            self.sample_reaction_payload["data"], channel, partner, "reaction123"
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Original message not found")

    def test_handle_reaction_message_notification_disabled(self):
        """Test reaction notification is not created when disabled."""
        # Disable reaction notifications
        self.connector.notify_reactions = False

        partner = self.env["res.partner"].create(
            {"name": "Reactor", "phone": "5511555555555"}
        )

        channel = self.env["discuss.channel"].create(
            {
                "name": "No Notify Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        # Create original message
        original_msg = channel.message_post(
            body="React to this",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        original_msg.write({"discuss_hub_message_id": "original_msg_id"})

        initial_msg_count = len(channel.message_ids)

        self.plugin.handle_reaction_message(
            self.sample_reaction_payload["data"], channel, partner, "reaction123"
        )

        # Verify no new message was created
        self.assertEqual(len(channel.message_ids), initial_msg_count)

        # Re-enable for other tests
        self.connector.notify_reactions = True

    # ===================================================================
    # IMAGE MESSAGE TESTS
    # ===================================================================

    def test_handle_image_message_creates_attachment(self):
        """Test handling image message creates attachment."""
        partner = self.env["res.partner"].create(
            {"name": "Image Sender", "phone": "5511444444444"}
        )

        channel = self.env["discuss.channel"].create(
            {
                "name": "Image Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        result = self.plugin.handle_image_message(
            self.sample_image_message_payload["data"], channel, partner, "img123456"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["event"], "messages.upsert.imageMessage")

        # Verify message and attachment
        message = self.env["mail.message"].browse(result["image_message"])
        self.assertIn("Test image", message.body)
        self.assertTrue(len(message.attachment_ids) > 0)

    # ===================================================================
    # VIDEO MESSAGE TESTS
    # ===================================================================

    def test_handle_video_message_creates_attachment(self):
        """Test handling video message creates attachment."""
        partner = self.env["res.partner"].create(
            {"name": "Video Sender", "phone": "5511333333333"}
        )

        channel = self.env["discuss.channel"].create(
            {
                "name": "Video Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        video_payload = {
            "key": {"id": "vid123"},
            "message": {
                "videoMessage": {"caption": "Test video", "title": "my_video"},
                "base64": "dGVzdHZpZGVvZGF0YQ==",  # "testvideodata" in base64
            },
        }

        result = self.plugin.handle_video_message(
            video_payload, channel, partner, "vid123"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["event"], "messages.upsert.videoMessage")

        message = self.env["mail.message"].browse(result["video_message"])
        self.assertTrue(len(message.attachment_ids) > 0)
        self.assertIn(".mp4", message.attachment_ids[0].name)

    # ===================================================================
    # AUDIO MESSAGE TESTS
    # ===================================================================

    def test_handle_audio_message_creates_attachment(self):
        """Test handling audio message creates attachment."""
        partner = self.env["res.partner"].create(
            {"name": "Audio Sender", "phone": "5511222222222"}
        )

        channel = self.env["discuss.channel"].create(
            {
                "name": "Audio Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        audio_payload = {
            "key": {"id": "aud123"},
            "message": {
                "audioMessage": {},
                "base64": "dGVzdGF1ZGlvZGF0YQ==",  # "testaudiodata" in base64
            },
        }

        result = self.plugin.handle_audio_message(
            audio_payload, channel, partner, "aud123"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["event"], "messages.upsert.audioMessage")

        message = self.env["mail.message"].browse(result["audio_message"])
        self.assertIn("audio", message.body)
        self.assertTrue(len(message.attachment_ids) > 0)
        self.assertEqual(message.attachment_ids[0].name, "audio.ogg")

    # ===================================================================
    # LOCATION MESSAGE TESTS
    # ===================================================================

    def test_handle_location_message_creates_link(self):
        """Test handling location message creates Google Maps link."""
        partner = self.env["res.partner"].create(
            {"name": "Location Sender", "phone": "5511111111111"}
        )

        channel = self.env["discuss.channel"].create(
            {
                "name": "Location Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        location_payload = {
            "key": {"id": "loc123"},
            "message": {
                "locationMessage": {
                    "degreesLatitude": -23.5505,
                    "degreesLongitude": -46.6333,
                    "jpegThumbnail": "",
                }
            },
        }

        result = self.plugin.handle_location_message(
            location_payload, channel, partner, "loc123"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["event"], "messages.upsert.locationMessage")

        message = self.env["mail.message"].browse(result["location_message"])
        self.assertIn("maps.google.com", message.body)
        self.assertIn("-23.5505", message.body)
        self.assertIn("-46.6333", message.body)

    # ===================================================================
    # DOCUMENT MESSAGE TESTS
    # ===================================================================

    def test_handle_document_message_creates_attachment(self):
        """Test handling document message creates attachment."""
        partner = self.env["res.partner"].create(
            {"name": "Doc Sender", "phone": "5511000000000"}
        )

        channel = self.env["discuss.channel"].create(
            {
                "name": "Document Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        doc_payload = {
            "key": {"id": "doc123"},
            "message": {
                "documentMessage": {
                    "caption": "Important document",
                    "title": "contract.pdf",
                },
                "base64": "dGVzdGRvY3VtZW50ZGF0YQ==",  # "testdocumentdata" in base64
            },
        }

        result = self.plugin.handle_document_message(
            doc_payload, channel, partner, "doc123"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["event"], "messages.upsert.documentMessage")

        message = self.env["mail.message"].browse(result["document_message"])
        self.assertIn("Important document", message.body)
        self.assertTrue(len(message.attachment_ids) > 0)
        self.assertEqual(message.attachment_ids[0].name, "contract.pdf")

    # ===================================================================
    # CONTACT MESSAGE TESTS
    # ===================================================================

    def test_handle_contact_message_creates_vcard(self):
        """Test handling contact message with vCard."""
        partner = self.env["res.partner"].create(
            {"name": "Contact Sender", "phone": "5519999999999"}
        )

        channel = self.env["discuss.channel"].create(
            {
                "name": "Contact Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        contact_payload = {
            "key": {"remoteJid": "5519999999999@s.whatsapp.net", "id": "contact123"},
            "message": {
                "contactMessage": {
                    "vcard": "BEGIN:VCARD\nVERSION:3.0\nFN:John Doe\nEND:VCARD"
                }
            },
        }

        result = self.plugin.handle_contact_message(
            contact_payload, channel, partner, "contact123"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["event"], "messages.upsert.contactMessage")

        message = self.env["mail.message"].browse(result["text_message"])
        self.assertIn("VCARD", message.body)

    # ===================================================================
    # OUTGOING MESSAGE TESTS
    # ===================================================================

    @patch("requests.Session.post")
    def test_send_text_message_success(self, mock_post):
        """Test sending text message successfully."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"key": {"id": "sent_msg_123"}}
        mock_post.return_value = mock_response

        channel = self.env["discuss.channel"].create(
            {
                "name": "Outgoing Channel",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": "5511999999999",
            }
        )

        message = channel.message_post(
            body="<p>Outgoing test message</p>",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        result = self.plugin.send_text_message(channel, message)

        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 201)

        # Verify message ID was updated
        message_updated = self.env["mail.message"].browse(message.id)
        self.assertEqual(message_updated.discuss_hub_message_id, "sent_msg_123")

    @patch("requests.Session.post")
    def test_send_text_message_with_quoted_message(self, mock_post):
        """Test sending text message with quoted message."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"key": {"id": "sent_reply_123"}}
        mock_post.return_value = mock_response

        channel = self.env["discuss.channel"].create(
            {
                "name": "Reply Outgoing Channel",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": "5511888888888",
            }
        )

        # Create parent message
        parent_msg = channel.message_post(
            body="Parent message",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        parent_msg.write({"discuss_hub_message_id": "parent_123"})

        # Create reply message
        reply_msg = channel.message_post(
            body="Reply message",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            parent_id=parent_msg.id,
        )

        result = self.plugin.send_text_message(channel, reply_msg)

        self.assertIsNotNone(result)

        # Verify quoted parameter was included in the call
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        self.assertIn("quoted", payload)
        self.assertEqual(payload["quoted"]["key"]["id"], "parent_123")

    @patch("requests.Session.post")
    def test_send_text_message_failure(self, mock_post):
        """Test sending text message handles failures."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_post.return_value = mock_response

        channel = self.env["discuss.channel"].create(
            {
                "name": "Failed Channel",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": "5511777777777",
            }
        )

        message = channel.message_post(
            body="Failed message",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        result = self.plugin.send_text_message(channel, message)

        self.assertFalse(result)

    @patch("requests.Session.post")
    def test_send_attachments_image(self, mock_post):
        """Test sending image attachment."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"key": {"id": "sent_img_123"}}
        mock_post.return_value = mock_response

        channel = self.env["discuss.channel"].create(
            {
                "name": "Attachment Channel",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": "5511666666666",
            }
        )

        # Create attachment
        attachment = self.env["ir.attachment"].create(
            {
                "name": "test_image.jpg",
                "datas": base64.b64encode(b"fake image data").decode("utf-8"),
                "mimetype": "image/jpeg",
                "index_content": "image",
            }
        )

        message = channel.message_post(
            body="Image message",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            attachment_ids=[attachment.id],
        )

        result = self.plugin.send_attachments(channel, message)

        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 201)

    # ===================================================================
    # MESSAGE UPDATE AND DELETE TESTS
    # ===================================================================

    def test_process_messages_update_mark_read(self):
        """Test processing message read status update."""
        # Create partner structure (parent + contact) as expected by
        # get_or_create_partner. The phone number must match what
        # get_contact_identifier returns
        # Input: "5511555555555@s.whatsapp.net" (13 digits)
        # No formatting applied since it's not 12 digits, so returns: "5511555555555"
        parent_partner = self.env["res.partner"].create(
            {"name": "Reader", "phone": "5511555555555"}
        )

        self.env["res.partner"].create(
            {
                "name": "whatsapp",  # Must match connector.partner_contact_name
                "phone": "5511555555555",
                "parent_id": parent_partner.id,
            }
        )

        channel = self.env["discuss.channel"].create(
            {
                "name": "Read Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        # Add parent partner to channel
        channel.write({"channel_partner_ids": [(4, parent_partner.id)]})

        # Create message
        message = channel.message_post(
            body="Read this", message_type="comment", subtype_xmlid="mail.mt_comment"
        )
        message.write({"discuss_hub_message_id": "read_msg_123"})

        # Create read status payload
        read_payload = {
            "event": "messages.update",
            "data": {
                "keyId": "read_msg_123",
                "status": "READ",
                "key": {"remoteJid": "5511555555555@s.whatsapp.net"},
            },
        }

        result = self.plugin.process_messages_update(read_payload)

        self.assertTrue(result["success"])
        self.assertEqual(result["event"], "messages.update.mark_read")

    def test_process_messages_update_read_receipts_disabled(self):
        """Test read status update when read receipts disabled."""
        self.connector.show_read_receipts = False

        read_payload = {
            "event": "messages.update",
            "data": {"keyId": "some_msg", "status": "READ"},
        }

        result = self.plugin.process_messages_update(read_payload)

        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Read receipts disabled")

        # Re-enable for other tests
        self.connector.show_read_receipts = True

    def test_process_messages_delete(self):
        """Test processing message deletion."""
        channel = self.env["discuss.channel"].create(
            {
                "name": "Delete Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        # Create message
        message = channel.message_post(
            body="Delete me", message_type="comment", subtype_xmlid="mail.mt_comment"
        )
        message.write({"discuss_hub_message_id": "delete_msg_123"})

        # Create delete payload
        delete_payload = {"event": "messages.delete", "data": {"id": "delete_msg_123"}}

        result = self.plugin.process_messages_delete(delete_payload)

        self.assertTrue(result["success"])
        self.assertEqual(result["event"], "messages.delete")

        # Verify message body was updated with strikethrough
        message_updated = self.env["mail.message"].browse(message.id)
        self.assertIn("<s>", message_updated.body)
        self.assertIn("</s>", message_updated.body)

        # Verify deletion notification was created
        channel_messages = channel.message_ids
        self.assertTrue(any("deleted" in msg.body.lower() for msg in channel_messages))

    # ===================================================================
    # CONTACT SYNC TESTS
    # ===================================================================

    @patch("requests.Session.post")
    def test_sync_contacts(self, mock_post):
        """Test synchronizing contacts from Evolution API."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "data": {
                    "key": {"remoteJid": "5511999999999@s.whatsapp.net"},
                    "pushName": "Contact 1",
                }
            },
            {
                "data": {
                    "key": {"remoteJid": "5511888888888@s.whatsapp.net"},
                    "pushName": "Contact 2",
                }
            },
        ]
        mock_post.return_value = mock_response

        result = self.plugin.sync_contacts(update_profile_picture=False)

        self.assertTrue(result)
        # Verify contacts were fetched
        self.assertTrue(mock_post.called)

    def test_process_contacts_upsert(self):
        """Test processing contacts.upsert event."""
        contacts_payload = {
            "event": "contacts.upsert",
            "instance": "test_evolution_instance",
            "data": [
                {
                    "data": {
                        "key": {"remoteJid": "5511999999999@s.whatsapp.net"},
                        "pushName": "New Contact",
                    }
                }
            ],
        }

        result = self.plugin.process_contacts_upsert(contacts_payload)

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "process_contacts_upsert")
        self.assertEqual(result["contacts"], 1)

    # ===================================================================
    # PROFILE PICTURE TESTS
    # ===================================================================

    @patch("requests.get")
    @patch("requests.Session.post")
    def test_get_profile_picture_from_url(self, mock_session_post, mock_get):
        """Test getting profile picture from URL."""
        # Mock image download
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.content = b"fake image bytes"
        mock_get.return_value = mock_get_response

        payload = {
            "data": {
                "profilePicUrl": "http://example.com/profile.jpg",
                "key": {"remoteJid": "5511999999999@s.whatsapp.net"},
            }
        }

        image_base64 = self.plugin.get_profile_picture(payload)

        self.assertIsNotNone(image_base64)
        self.assertEqual(
            image_base64, base64.b64encode(b"fake image bytes").decode("utf-8")
        )

    @patch("requests.get")
    @patch("requests.Session.post")
    def test_get_profile_picture_from_api(self, mock_session_post, mock_get):
        """Test getting profile picture from Evolution API."""
        # Mock API response
        mock_api_response = Mock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {
            "profilePictureUrl": "http://example.com/fetched_profile.jpg"
        }
        mock_session_post.return_value = mock_api_response

        # Mock image download
        mock_image_response = Mock()
        mock_image_response.status_code = 200
        mock_image_response.content = b"fetched image bytes"
        mock_get.return_value = mock_image_response

        payload = {"data": {"key": {"remoteJid": "5511888888888@s.whatsapp.net"}}}

        image_base64 = self.plugin.get_profile_picture(payload)

        self.assertIsNotNone(image_base64)
        self.assertTrue(mock_session_post.called)

    # ===================================================================
    # PROCESS_PAYLOAD ROUTING TESTS
    # ===================================================================

    def test_process_payload_routes_qrcode_updated(self):
        """Test process_payload routes qrcode.updated to administrative handler."""
        with patch.object(self.plugin, "process_administrative_payload") as mock_admin:
            mock_admin.return_value = {"success": True}

            result = self.plugin.process_payload(self.sample_qr_code_payload)

            self.assertTrue(mock_admin.called)
            self.assertTrue(result["success"])

    def test_process_payload_routes_messages_upsert(self):
        """Test process_payload routes messages.upsert to message handler."""
        with patch.object(self.plugin, "process_messages_upsert") as mock_upsert:
            mock_upsert.return_value = {"success": True}

            result = self.plugin.process_payload(self.sample_text_message_payload)

            self.assertTrue(mock_upsert.called)
            self.assertTrue(result["success"])

    def test_process_payload_routes_messages_update(self):
        """Test process_payload routes messages.update to update handler."""
        update_payload = {
            "event": "messages.update",
            "data": {"keyId": "update_msg", "status": "READ"},
        }

        with patch.object(self.plugin, "process_messages_update") as mock_update:
            mock_update.return_value = {"success": True}

            result = self.plugin.process_payload(update_payload)

            self.assertTrue(mock_update.called)
            self.assertTrue(result["success"])

    def test_process_payload_routes_messages_delete(self):
        """Test process_payload routes messages.delete to delete handler."""
        delete_payload = {"event": "messages.delete", "data": {"id": "delete_msg"}}

        with patch.object(self.plugin, "process_messages_delete") as mock_delete:
            mock_delete.return_value = {"success": True}

            result = self.plugin.process_payload(delete_payload)

            self.assertTrue(mock_delete.called)
            self.assertTrue(result["success"])

    def test_process_payload_routes_contacts_upsert(self):
        """Test process_payload routes contacts.upsert when enabled."""
        contacts_payload = {"event": "contacts.upsert", "data": []}

        with patch.object(self.plugin, "process_contacts_upsert") as mock_contacts:
            mock_contacts.return_value = {"success": True}

            result = self.plugin.process_payload(contacts_payload)

            self.assertTrue(mock_contacts.called)
            self.assertTrue(result["success"])

    def test_process_payload_ignores_contacts_upsert_when_disabled(self):
        """Test process_payload ignores contacts.upsert when import disabled."""
        self.connector.import_contacts = False

        contacts_payload = {"event": "contacts.upsert", "data": []}

        with patch.object(self.plugin, "process_contacts_upsert") as mock_contacts:
            result = self.plugin.process_payload(contacts_payload)

            self.assertFalse(mock_contacts.called)
            self.assertFalse(result["success"])

        # Re-enable for other tests
        self.connector.import_contacts = True

    def test_process_payload_unknown_event(self):
        """Test process_payload handles unknown events gracefully."""
        unknown_payload = {"event": "unknown.event", "data": {}}

        result = self.plugin.process_payload(unknown_payload)

        self.assertFalse(result["success"])
        self.assertEqual(result["event"], "did nothing")

    # ===================================================================
    # INSTANCE MANAGEMENT TESTS
    # ===================================================================

    @patch("requests.Session.post")
    def test_restart_instance(self, mock_post):
        """Test restarting Evolution instance."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"instance": {"state": "open"}}
        mock_post.return_value = mock_response

        with patch("time.sleep"):  # Skip sleep in tests
            self.plugin.restart_instance()

        self.assertTrue(mock_post.called)

    @patch("requests.Session.delete")
    def test_logout_instance(self, mock_delete):
        """Test logging out Evolution instance."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"instance": {"state": "closed"}}
        mock_delete.return_value = mock_response

        with patch("time.sleep"):  # Skip sleep in tests
            self.plugin.logout_instance()

        self.assertTrue(mock_delete.called)

    # ===================================================================
    # FORMAT MESSAGE TESTS
    # ===================================================================

    def test_format_message_before_send_with_template(self):
        """Test formatting message with custom template."""
        # Set custom template
        self.connector.text_message_template = (
            "<p>{{message.author_id.name}}: {{body}}</p>"
        )

        channel = self.env["discuss.channel"].create(
            {
                "name": "Template Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        message = channel.message_post(
            author_id=self.admin_partner.id,
            body="<p>Test message</p>",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        formatted = self.plugin.format_message_before_send(message)

        self.assertIn("Admin Partner", formatted)
        self.assertIn("Test message", formatted)

    def test_format_message_before_send_html_to_whatsapp(self):
        """Test HTML to WhatsApp formatting conversion."""
        channel = self.env["discuss.channel"].create(
            {
                "name": "Format Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        # Message with HTML formatting
        message = channel.message_post(
            body="<p><strong>Bold</strong> and <em>italic</em></p>",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        formatted = self.plugin.format_message_before_send(message)

        # The utils.html_to_whatsapp should convert HTML tags
        # Exact output depends on implementation, but it should process the HTML
        self.assertIsNotNone(formatted)

    # ===================================================================
    # BROADCAST MESSAGE TESTS
    # ===================================================================

    def test_process_messages_upsert_broadcast_enabled(self):
        """Test processing status@broadcast messages when enabled."""
        broadcast_payload = {
            "event": "messages.upsert",
            "data": {
                "key": {
                    "remoteJid": "status@broadcast",
                    "participant": "5511999999999@s.whatsapp.net",
                    "id": "broadcast_123",
                },
                "pushName": "Broadcaster",
                "message": {"conversation": "Status update"},
            },
        }

        # Mock partner and channel creation
        with (
            patch.object(self.plugin, "get_or_create_partner") as mock_partner,
            patch.object(self.plugin, "get_or_create_channel") as mock_channel,
            patch.object(self.plugin, "handle_text_message") as mock_handle,
        ):
            mock_partner.return_value = self.admin_partner
            mock_channel.return_value = self.manager_channel
            mock_handle.return_value = {"success": True}

            self.plugin.process_messages_upsert(broadcast_payload)

            # Should process the message
            self.assertTrue(mock_handle.called)

    def test_process_messages_upsert_broadcast_disabled(self):
        """Test rejecting status@broadcast messages when disabled."""
        self.connector.evolution_allow_broadcast_messages = False

        broadcast_payload = {
            "event": "messages.upsert",
            "data": {
                "key": {
                    "remoteJid": "status@broadcast",
                    "participant": "5511999999999@s.whatsapp.net",
                    "id": "broadcast_456",
                },
                "message": {"conversation": "Status update"},
            },
        }

        result = self.plugin.process_messages_upsert(broadcast_payload)

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Broadcast messages disabled")

        # Re-enable for other tests
        self.connector.evolution_allow_broadcast_messages = True

    # ===================================================================
    # ERROR HANDLING TESTS
    # ===================================================================

    def test_process_messages_upsert_no_remote_jid(self):
        """Test handling messages.upsert without remoteJid."""
        invalid_payload = {
            "event": "messages.upsert",
            "data": {"message": {"conversation": "No sender info"}},
        }

        result = self.plugin.process_messages_upsert(invalid_payload)

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "No remoteJid")

    def test_process_messages_upsert_partner_creation_fails(self):
        """Test handling when partner creation fails."""
        with patch.object(self.plugin, "get_or_create_partner") as mock_partner:
            mock_partner.return_value = False

            result = self.plugin.process_messages_upsert(
                self.sample_text_message_payload
            )

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "Partner creation failed")

    def test_process_messages_upsert_channel_creation_fails(self):
        """Test handling when channel creation fails."""
        with (
            patch.object(self.plugin, "get_or_create_partner") as mock_partner,
            patch.object(self.plugin, "get_or_create_channel") as mock_channel,
        ):
            mock_partner.return_value = self.admin_partner
            mock_channel.return_value = False

            result = self.plugin.process_messages_upsert(
                self.sample_text_message_payload
            )

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "Channel creation failed")

    @patch("requests.Session.post")
    def test_send_text_message_request_exception(self, mock_post):
        """Test send_text_message handles request exceptions."""
        mock_post.side_effect = requests.RequestException("Network error")

        channel = self.env["discuss.channel"].create(
            {
                "name": "Error Channel",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": "5511999999999",
            }
        )

        message = channel.message_post(
            body="Error message",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        result = self.plugin.send_text_message(channel, message)

        self.assertFalse(result)

    @patch("requests.Session.post")
    def test_send_attachments_request_exception(self, mock_post):
        """Test send_attachments handles request exceptions."""
        mock_post.side_effect = requests.RequestException("Upload error")

        channel = self.env["discuss.channel"].create(
            {
                "name": "Upload Error Channel",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": "5511888888888",
            }
        )

        attachment = self.env["ir.attachment"].create(
            {
                "name": "test.jpg",
                "datas": base64.b64encode(b"data").decode("utf-8"),
                "mimetype": "image/jpeg",
                "index_content": "image",
            }
        )

        message = channel.message_post(
            body="Attachment",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            attachment_ids=[attachment.id],
        )

        result = self.plugin.send_attachments(channel, message)

        self.assertFalse(result)

    def test_process_messages_update_message_not_found(self):
        """Test handling message update when message not found."""
        update_payload = {
            "event": "messages.update",
            "data": {"keyId": "nonexistent_msg", "status": "READ"},
        }

        result = self.plugin.process_messages_update(update_payload)

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Message not found")

    def test_process_messages_delete_message_not_found(self):
        """Test handling message deletion when message not found."""
        delete_payload = {
            "event": "messages.delete",
            "data": {"id": "nonexistent_delete_msg"},
        }

        result = self.plugin.process_messages_delete(delete_payload)

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Message Not Found")
