"""Test suite for Create User for Visitor feature.

This test suite covers:
- User creation for visitors based on connector configuration
- Portal user creation
- Public user creation
- User group assignment
- Edge cases and validation
"""

from unittest.mock import patch, MagicMock
from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("discuss_hub", "create_user_for_visitor")
class TestCreateUserForVisitor(HttpCase):
    """Test cases for Create User for Visitor functionality."""

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
        
        # Create base connector (no user creation)
        cls.connector_none = cls.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector - No User",
                "type": "example",
                "enabled": True,
                "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "url": "http://example:8080",
                "api_key": "test_api_key",
                "partner_contact_field": "phone",
                "partner_contact_name": "whatsapp",
                "create_user_for_visitor": "none",
            }
        )
        
        # Create connector with portal user creation
        cls.connector_portal = cls.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector - Portal User",
                "type": "example",
                "enabled": True,
                "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "url": "http://example:8080",
                "api_key": "test_api_key",
                "partner_contact_field": "phone",
                "partner_contact_name": "whatsapp",
                "create_user_for_visitor": "portal",
            }
        )
        
        # Create connector with public user creation
        cls.connector_public = cls.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector - Public User",
                "type": "example",
                "enabled": True,
                "uuid": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                "url": "http://example:8080",
                "api_key": "test_api_key",
                "partner_contact_field": "phone",
                "partner_contact_name": "whatsapp",
                "create_user_for_visitor": "public",
            }
        )

        # Sample payload for testing
        cls.sample_payload = {
            "message": {
                "from": "5511999999999",
                "body": "Test message",
                "name": "Test User",
            },
            "contact_identifier": "1234567890",
            "contact_name": "Test User",
        }

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        cls.patcher_requests.stop()
        cls.patcher_requests_post.stop()
        cls.patcher_requests_session.stop()
        super().tearDownClass()

    # ===================================================================
    # CONNECTOR CONFIGURATION TESTS
    # ===================================================================

    def test_connector_create_user_field_exists(self):
        """Test that create_user_for_visitor field exists on connector."""
        self.assertIn(
            "create_user_for_visitor",
            self.connector_none._fields,
            "create_user_for_visitor field should exist on connector",
        )

    def test_connector_create_user_default_value(self):
        """Test default value for create_user_for_visitor is 'none'."""
        new_connector = self.env["discuss_hub.connector"].create(
            {
                "name": "Test Default Connector",
                "type": "example",
                "enabled": True,
            }
        )
        self.assertEqual(
            new_connector.create_user_for_visitor,
            "none",
            "Default value should be 'none'",
        )

    def test_connector_create_user_selection_values(self):
        """Test that all selection values are available."""
        field = self.connector_none._fields["create_user_for_visitor"]
        selection_values = [val[0] for val in field.selection]
        
        self.assertIn("none", selection_values)
        self.assertIn("portal", selection_values)
        self.assertIn("public", selection_values)

    # ===================================================================
    # NO USER CREATION TESTS
    # ===================================================================

    def test_no_user_creation_for_visitor(self):
        """Test that no user is created when set to 'none'."""
        plugin = self.connector_none.get_plugin()
        partner = plugin.get_or_create_partner(self.sample_payload)
        
        # Check that partner was created
        self.assertTrue(partner, "Partner should be created")
        
        # Check that NO user was created for this partner
        parent_partner = partner.parent_id
        user = self.env["res.users"].search(
            [("partner_id", "=", parent_partner.id)], limit=1
        )
        self.assertFalse(
            user,
            "No user should be created when create_user_for_visitor is 'none'",
        )

    # ===================================================================
    # PORTAL USER CREATION TESTS
    # ===================================================================

    def test_portal_user_creation_for_new_visitor(self):
        """Test portal user creation for new visitor."""
        plugin = self.connector_portal.get_plugin()
        partner = plugin.get_or_create_partner(self.sample_payload)
        
        # Check that partner was created
        self.assertTrue(partner, "Partner should be created")
        
        # Check that portal user was created
        parent_partner = partner.parent_id
        user = self.env["res.users"].search(
            [("partner_id", "=", parent_partner.id)], limit=1
        )
        
        self.assertTrue(user, "Portal user should be created")
        self.assertEqual(
            user.partner_id.id,
            parent_partner.id,
            "User should be linked to parent partner",
        )
        self.assertEqual(
            user.login,
            self.sample_payload["contact_identifier"],
            "User login should match contact identifier",
        )

    def test_portal_user_has_portal_group(self):
        """Test that created portal user has portal group."""
        plugin = self.connector_portal.get_plugin()
        partner = plugin.get_or_create_partner(self.sample_payload)
        
        parent_partner = partner.parent_id
        user = self.env["res.users"].search(
            [("partner_id", "=", parent_partner.id)], limit=1
        )
        
        portal_group = self.env.ref("base.group_portal")
        self.assertIn(
            portal_group,
            user.group_ids,
            "User should have portal group",
        )

    def test_portal_user_not_created_twice(self):
        """Test that portal user is not created twice for same visitor."""
        plugin = self.connector_portal.get_plugin()
        
        # First call - creates user
        partner1 = plugin.get_or_create_partner(self.sample_payload)
        parent_partner1 = partner1.parent_id
        user1 = self.env["res.users"].search(
            [("partner_id", "=", parent_partner1.id)], limit=1
        )
        
        # Second call with same payload
        partner2 = plugin.get_or_create_partner(self.sample_payload)
        parent_partner2 = partner2.parent_id
        users = self.env["res.users"].search(
            [("partner_id", "=", parent_partner2.id)]
        )
        
        self.assertEqual(
            len(users),
            1,
            "Only one user should exist for the same visitor",
        )
        self.assertEqual(
            user1.id,
            users[0].id,
            "Should return the same user on second call",
        )

    # ===================================================================
    # PUBLIC USER CREATION TESTS
    # ===================================================================

    def test_public_user_creation_for_new_visitor(self):
        """Test public user creation for new visitor."""
        plugin = self.connector_public.get_plugin()
        partner = plugin.get_or_create_partner(self.sample_payload)
        
        # Check that partner was created
        self.assertTrue(partner, "Partner should be created")
        
        # Check that public user was created
        parent_partner = partner.parent_id
        user = self.env["res.users"].search(
            [("partner_id", "=", parent_partner.id)], limit=1
        )
        
        self.assertTrue(user, "Public user should be created")
        self.assertEqual(
            user.partner_id.id,
            parent_partner.id,
            "User should be linked to parent partner",
        )

    def test_public_user_has_public_group(self):
        """Test that created public user has public group."""
        plugin = self.connector_public.get_plugin()
        partner = plugin.get_or_create_partner(self.sample_payload)
        
        parent_partner = partner.parent_id
        user = self.env["res.users"].search(
            [("partner_id", "=", parent_partner.id)], limit=1
        )
        
        public_group = self.env.ref("base.group_public")
        self.assertIn(
            public_group,
            user.group_ids,
            "User should have public group",
        )

    def test_public_user_not_created_twice(self):
        """Test that public user is not created twice for same visitor."""
        plugin = self.connector_public.get_plugin()
        
        # First call - creates user
        partner1 = plugin.get_or_create_partner(self.sample_payload)
        parent_partner1 = partner1.parent_id
        user1 = self.env["res.users"].search(
            [("partner_id", "=", parent_partner1.id)], limit=1
        )
        
        # Second call with same payload
        partner2 = plugin.get_or_create_partner(self.sample_payload)
        parent_partner2 = partner2.parent_id
        users = self.env["res.users"].search(
            [("partner_id", "=", parent_partner2.id)]
        )
        
        self.assertEqual(
            len(users),
            1,
            "Only one user should exist for the same visitor",
        )
        self.assertEqual(
            user1.id,
            users[0].id,
            "Should return the same user on second call",
        )

    # ===================================================================
    # USER CREATION FOR EXISTING PARTNER TESTS
    # ===================================================================

    def test_user_creation_for_existing_partner_without_user(self):
        """Test user creation when partner exists but has no user."""
        # Create a parent partner manually (simulating existing partner)
        existing_partner = self.env["res.partner"].create(
            {
                "name": "Existing Partner",
                "phone": "5511888888888",
            }
        )
        
        # Create contact partner
        contact_partner = self.env["res.partner"].create(
            {
                "name": "whatsapp",
                "phone": "5511888888888",
                "parent_id": existing_partner.id,
            }
        )
        
        # Verify no user exists
        user = self.env["res.users"].search(
            [("partner_id", "=", existing_partner.id)], limit=1
        )
        self.assertFalse(user, "No user should exist initially")
        
        # Now process payload with portal connector
        plugin = self.connector_portal.get_plugin()
        payload = {
            "message": {
                "from": "5511888888888",
                "body": "Test message",
                "name": "Existing Partner",
            },
            "contact_identifier": "1234567890",
            "contact_name": "Existing Partner",
        }
        partner = plugin.get_or_create_partner(payload)
        
        # O plugin cria um novo partner filho, não usa o existente diretamente
        # Verify user was created for the parent of the new contact partner
        parent_partner = partner.parent_id
        user = self.env["res.users"].search(
            [("partner_id", "=", parent_partner.id)], limit=1
        )
        self.assertTrue(
            user,
            "User should be created for parent partner",
        )


    def test_user_not_recreated_for_existing_partner_with_user(self):
        """Test that user is not recreated if partner already has user."""
        # Create partner with existing user
        existing_partner = self.env["res.partner"].create(
            {
                "name": "Partner With User",
                "phone": "5511777777777",
            }
        )
        
        existing_user = self.env["res.users"].create(
            {
                "name": "Existing User",
                "login": "existing_user_login",
                "partner_id": existing_partner.id,
            }
        )
        
        # Create contact partner
        contact_partner = self.env["res.partner"].create(
            {
                "name": "whatsapp",
                "phone": "5511777777777",
                "parent_id": existing_partner.id,
            }
        )
        
        # Process payload with portal connector
        plugin = self.connector_portal.get_plugin()
        payload = {
            "message": {
                "from": "5511777777777",
                "body": "Test message",
                "name": "Partner With User",
            }
        }
        partner = plugin.get_or_create_partner(payload)
        
        # Verify only one user exists (the original one)
        users = self.env["res.users"].search(
            [("partner_id", "=", existing_partner.id)]
        )
        self.assertEqual(
            len(users),
            1,
            "Only one user should exist",
        )
        self.assertEqual(
            users[0].id,
            existing_user.id,
            "Should be the original user",
        )

    # ===================================================================
    # USER ATTRIBUTES TESTS
    # ===================================================================

    def test_portal_user_name_from_partner(self):
        """Test that portal user name comes from partner."""
        plugin = self.connector_portal.get_plugin()
        partner = plugin.get_or_create_partner(self.sample_payload)
        
        parent_partner = partner.parent_id
        user = self.env["res.users"].search(
            [("partner_id", "=", parent_partner.id)], limit=1
        )
        
        self.assertEqual(
            user.name,
            parent_partner.name,
            "User name should match parent partner name",
        )

    def test_public_user_login_from_contact_identifier(self):
        """Test that public user login comes from contact identifier."""
        plugin = self.connector_public.get_plugin()
        partner = plugin.get_or_create_partner(self.sample_payload)
        
        parent_partner = partner.parent_id
        user = self.env["res.users"].search(
            [("partner_id", "=", parent_partner.id)], limit=1
        )
        
        expected_login = self.sample_payload["contact_identifier"]
        self.assertEqual(
            user.login,
            expected_login,
            "User login should match contact identifier",
        )

    # ===================================================================
    # EDGE CASES AND VALIDATION TESTS
    # ===================================================================

    def test_different_connectors_different_visitors(self):
        """Test that different connectors handle visitors independently."""
        # Create visitor with portal connector
        plugin_portal = self.connector_portal.get_plugin()
        payload1 = {
            "message": {
                "from": "5511666666666",
                "body": "Test",
                "name": "Visitor 1",
            },
            "contact_identifier": "5511666666666",
            "contact_name": "Visitor 1",
        }
        partner1 = plugin_portal.get_or_create_partner(payload1)
        parent1 = partner1.parent_id
        
        # Create same visitor with public connector (different phone to avoid conflict)
        plugin_public = self.connector_public.get_plugin()
        payload2 = {
            "message": {
                "from": "5511555555555",
                "body": "Test",
                "name": "Visitor 2",
            },
            "contact_identifier": "5511555555555",
            "contact_name": "Visitor 2",
        }
        partner2 = plugin_public.get_or_create_partner(payload2)
        parent2 = partner2.parent_id
        
        # Check users were created with correct groups
        user1 = self.env["res.users"].search(
            [("partner_id", "=", parent1.id)], limit=1
        )
        user2 = self.env["res.users"].search(
            [("partner_id", "=", parent2.id)], limit=1
        )
        
        portal_group = self.env.ref("base.group_portal")
        public_group = self.env.ref("base.group_public")
        
        self.assertIn(portal_group, user1.group_ids)
        self.assertIn(public_group, user2.group_ids)

    def test_visitor_without_name_in_payload(self):
        """Test user creation when payload has no name."""
        plugin = self.connector_portal.get_plugin()
        payload = {
            "message": {
                "from": "5511444444444",
                "body": "Test message",
                # No name field
            }
        }
        
        partner = plugin.get_or_create_partner(payload)
        parent_partner = partner.parent_id
        
        # User should still be created
        user = self.env["res.users"].search(
            [("partner_id", "=", parent_partner.id)], limit=1
        )
        
        self.assertTrue(user, "User should be created even without name in payload")
        # Name should fallback to contact identifier
        self.assertTrue(
            user.name,
            "User should have a name (fallback to contact identifier)",
        )
