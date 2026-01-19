"""Test suite for Guest Channel Creation.

This test reproduces the error when trying to create a channel with guest_ids.
"""

from unittest.mock import patch, MagicMock
from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("discuss_hub", "guest", "channel_creation")
class TestGuestChannelCreation(HttpCase):
    """Test cases for creating channels with guests."""

    @classmethod
    def setUpClass(cls):
        """Set up test data and environment."""
        super().setUpClass()
        
        # Mock HTTP requests to prevent external calls during tests
        cls.patcher_requests = patch('requests.get')
        cls.patcher_requests_post = patch('requests.post')
        cls.patcher_requests_session = patch('requests.Session')
        
        mock_get = cls.patcher_requests.start()
        mock_post = cls.patcher_requests_post.start()
        mock_session = cls.patcher_requests_session.start()
        
        # Configure mocks to return empty/error responses
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.content = b''
        mock_get.return_value = mock_response
        mock_post.return_value = mock_response
        
        # Mock session methods
        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_response
        mock_session_instance.post.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        # Create connector with guest creation
        cls.connector_guest = cls.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector - Guest",
                "type": "example",
                "enabled": True,
                "uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
                "url": "http://example:8080",
                "api_key": "test_api_key",
                "partner_contact_field": "phone",
                "partner_contact_name": "whatsapp",
                "create_user_for_visitor": "guest",
            }
        )

        # Sample payload for testing
        cls.sample_payload = {
            "message": {
                "from": "5511888888888",
                "body": "Test message for guest channel",
                "name": "Guest Visitor",
            },
            "contact_identifier": "5511888888888",
            "contact_name": "Guest Visitor",
        }
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        cls.patcher_requests.stop()
        cls.patcher_requests_post.stop()
        cls.patcher_requests_session.stop()
        super().tearDownClass()

    def test_guest_channel_creation_works(self):
        """Test that channel creation with guest works correctly."""
        # Get plugin
        plugin = self.connector_guest.get_plugin()
        
        # Create partner and guest
        partner = plugin.get_or_create_partner(self.sample_payload)
        
        # Verify guest was created
        parent_partner = partner.parent_id
        guest = self.env["mail.guest"].search(
            [("name", "=", parent_partner.name)], limit=1
        )
        self.assertTrue(guest, "Guest should be created")
        
        # Create channel - should work without errors
        channel = plugin.get_or_create_channel(partner, self.sample_payload)
        
        # Verify channel was created
        self.assertTrue(channel, "Channel should be created")
        self.assertEqual(
            channel.discuss_hub_connector.id,
            self.connector_guest.id,
            "Channel should be linked to guest connector"
        )
        
        # Verify guest is a member of the channel
        # In Odoo, guests are members through discuss.channel.member with guest_id
        guest_member = self.env["discuss.channel.member"].search(
            [
                ("channel_id", "=", channel.id),
                ("guest_id", "=", guest.id),
            ],
            limit=1,
        )
        self.assertTrue(guest_member, "Guest should be a member of the channel")
