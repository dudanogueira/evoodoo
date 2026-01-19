"""Test suite to reproduce webhook user creation issue.

This test simulates the exact webhook flow that triggers the user creation.
"""

import logging
from unittest.mock import MagicMock, patch

from odoo.tests import tagged
from odoo.tests.common import HttpCase

_logger = logging.getLogger(__name__)


@tagged("discuss_hub", "webhook_user_creation")
class TestWebhookUserCreation(HttpCase):
    """Test cases to reproduce real webhook user creation scenario."""

    @classmethod
    def setUpClass(cls):
        """Set up test data and environment."""
        super().setUpClass()

        # Mock HTTP requests to prevent external calls during tests
        cls.patcher_requests = patch("requests.get")
        cls.patcher_requests_post = patch("requests.post")
        cls.patcher_requests_session = patch("requests.Session")

        mock_get = cls.patcher_requests.start()
        mock_post = cls.patcher_requests_post.start()
        mock_session = cls.patcher_requests_session.start()

        # Configure mocks to return empty/error responses
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.content = b""
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response
        mock_post.return_value = mock_response

        # Mock session methods
        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_response
        mock_session_instance.post.return_value = mock_response
        mock_session.return_value = mock_session_instance

        # Create connector with portal user creation (like production)
        cls.connector = cls.env["discuss_hub.connector"].create(
            {
                "name": "Test Webhook Connector - Portal",
                "type": "evolution",
                "enabled": True,
                "uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
                "url": "http://evolution:8080",
                "api_key": "test_webhook_api_key",
                "partner_contact_field": "phone",
                "partner_contact_name": "whatsapp",
                "create_user_for_visitor": "portal",
            }
        )

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        cls.patcher_requests.stop()
        cls.patcher_requests_post.stop()
        cls.patcher_requests_session.stop()
        super().tearDownClass()

    def test_webhook_payload_creates_portal_user(self):
        """Test that webhook payload creates portal user - simulating real scenario."""
        # Get plugin instance
        plugin = self.connector.get_plugin()

        # Simulate a real webhook payload from Evolution API
        webhook_payload = {
            "instance": "test_instance",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "MESSAGE_ID_12345",
                },
                "pushName": "Test Webhook User",
                "message": {"conversation": "Hello from webhook test"},
            },
            "destination": "5511999999999@s.whatsapp.net",
            "date_time": "2026-01-19T21:00:00.000Z",
            "sender": "5511999999999",
            "server_url": "http://evolution:8080",
            "apikey": "test_webhook_api_key",
            "event": "messages.upsert",
        }

        # This should trigger the full flow: get_or_create_partner -> create user
        try:
            partner = plugin.get_or_create_partner(webhook_payload)

            # Verify partner was created
            self.assertTrue(partner, "Partner should be created from webhook payload")

            # Verify parent partner exists
            parent_partner = partner.parent_id
            self.assertTrue(parent_partner, "Parent partner should exist")

            # Verify portal user was created
            user = self.env["res.users"].search(
                [("partner_id", "=", parent_partner.id)], limit=1
            )
            self.assertTrue(
                user,
                "Portal user should be created from webhook payload",
            )

            # Verify user has portal group
            portal_group = self.env.ref("base.group_portal")
            self.assertIn(
                portal_group,
                user.group_ids,
                "User should have portal group assigned",
            )

            _logger.info(
                "\n✅ Test passed! User created: %s (login: %s)",
                user.name,
                user.login,
            )
            _logger.info("   Groups: %s", user.group_ids.mapped("name"))

        except Exception as e:
            _logger.error("\n❌ Error during webhook user creation: %s", e)
            _logger.error("   Error type: %s", type(e).__name__)
            raise

    def test_webhook_payload_with_existing_partner_creates_user(self):
        """Test that webhook creates user even when partner already exists."""
        # First, create a partner manually (without user)
        existing_phone = "5511888888888"
        existing_partner = self.env["res.partner"].create(
            {
                "name": "Existing Webhook Partner",
                "phone": existing_phone,
            }
        )

        # Create contact partner
        self.env["res.partner"].create(
            {
                "name": "whatsapp",
                "phone": existing_phone,
                "parent_id": existing_partner.id,
            }
        )

        # Verify no user exists yet
        user = self.env["res.users"].search(
            [("partner_id", "=", existing_partner.id)], limit=1
        )
        self.assertFalse(user, "No user should exist initially")

        # Get plugin and process webhook payload
        plugin = self.connector.get_plugin()

        webhook_payload = {
            "instance": "test_instance",
            "data": {
                "key": {
                    "remoteJid": f"{existing_phone}@s.whatsapp.net",
                    "fromMe": False,
                    "id": "MESSAGE_ID_67890",
                },
                "pushName": "Existing Webhook Partner",
                "message": {"conversation": "Message from existing partner"},
            },
            "destination": f"{existing_phone}@s.whatsapp.net",
            "sender": existing_phone,
            "event": "messages.upsert",
        }

        try:
            # Process payload - should create user for existing partner
            plugin.get_or_create_partner(webhook_payload)

            # Verify user was created
            user = self.env["res.users"].search(
                [("partner_id", "=", existing_partner.id)], limit=1
            )
            self.assertTrue(
                user,
                "User should be created for existing partner",
            )

            # Verify user has portal group
            portal_group = self.env.ref("base.group_portal")
            self.assertIn(
                portal_group,
                user.group_ids,
                "User should have portal group assigned",
            )

            _logger.info("\n✅ User created for existing partner: %s", user.name)
            _logger.info("   Groups: %s", user.group_ids.mapped("name"))

        except Exception as e:
            _logger.error("\n❌ Error creating user for existing partner: %s", e)
            _logger.error("   Error type: %s", type(e).__name__)
            raise

    def test_manual_user_creation_with_groups(self):
        """Test manual user creation to understand Odoo 19 groups_id behavior."""
        # Create a simple partner
        partner = self.env["res.partner"].create(
            {
                "name": "Manual Test User",
                "phone": "5511777777777",
            }
        )

        portal_group = self.env.ref("base.group_portal")

        # Method 1: Try creating user with group_ids in create()
        _logger.info("\n=== Testing Method 1: group_ids in create() ===")
        try:
            user1 = self.env["res.users"].create(
                {
                    "name": "Test User Method 1",
                    "login": "test_user_method_1",
                    "partner_id": partner.id,
                    "group_ids": [(6, 0, [portal_group.id])],
                }
            )
            _logger.info("✅ Method 1 SUCCESS: %s", user1.name)
            _logger.info("   Groups: %s", user1.group_ids.mapped("name"))
        except Exception as e:
            _logger.error("❌ Method 1 FAILED: %s: %s", type(e).__name__, e)

        # Method 2: Try creating user without groups, then write
        _logger.info("\n=== Testing Method 2: write() after create() ===")
        partner2 = self.env["res.partner"].create(
            {
                "name": "Manual Test User 2",
                "phone": "5511666666666",
            }
        )
        try:
            user2 = self.env["res.users"].create(
                {
                    "name": "Test User Method 2",
                    "login": "test_user_method_2",
                    "partner_id": partner2.id,
                }
            )
            _logger.info("   User created: %s", user2.name)

            # Now try to write group_ids
            user2.write({"group_ids": [(6, 0, [portal_group.id])]})
            _logger.info("✅ Method 2 SUCCESS: %s", user2.name)
            _logger.info("   Groups: %s", user2.group_ids.mapped("name"))
        except Exception as e:
            _logger.error("❌ Method 2 FAILED: %s: %s", type(e).__name__, e)

        # Method 3: Try with sudo()
        _logger.info("\n=== Testing Method 3: sudo().write() ===")
        partner3 = self.env["res.partner"].create(
            {
                "name": "Manual Test User 3",
                "phone": "5511555555555",
            }
        )
        try:
            user3 = self.env["res.users"].create(
                {
                    "name": "Test User Method 3",
                    "login": "test_user_method_3",
                    "partner_id": partner3.id,
                }
            )
            _logger.info("   User created: %s", user3.name)

            # Try with sudo
            user3.sudo().write({"group_ids": [(6, 0, [portal_group.id])]})
            _logger.info("✅ Method 3 SUCCESS: %s", user3.name)
            _logger.info("   Groups: %s", user3.group_ids.mapped("name"))
        except Exception as e:
            _logger.error("❌ Method 3 FAILED: %s: %s", type(e).__name__, e)

        # Method 4: Using Command.set() directly in create()
        _logger.info("\n=== Testing Method 4: Using Command.set() in create() ===")
        partner4 = self.env["res.partner"].create(
            {
                "name": "Manual Test User 4",
                "phone": "5511444444444",
            }
        )
        try:
            from odoo import Command

            user4 = self.env["res.users"].create(
                {
                    "name": "Test User Method 4",
                    "login": "test_user_method_4",
                    "partner_id": partner4.id,
                    "group_ids": [Command.set([portal_group.id])],
                }
            )
            _logger.info("✅ Method 4 SUCCESS: %s", user4.name)
            _logger.info("   Groups: %s", user4.group_ids.mapped("name"))
        except Exception as e:
            _logger.error("❌ Method 4 FAILED: %s: %s", type(e).__name__, e)
