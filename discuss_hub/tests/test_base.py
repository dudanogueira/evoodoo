"""Test suite for the base plugin of discuss_hub.

This test suite covers the base plugin functionality including:
- Plugin initialization and basic properties
- NotImplementedError for abstract methods
- Partner creation and retrieval logic
- Channel creation and retrieval logic
- Profile picture update functionality
- Edge cases and error handling
"""

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("discuss_hub", "plugin_base")
class TestBasePlugin(HttpCase):
    """Test cases for the base plugin functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test data and environment."""
        super().setUpClass()
        # Create a test connector
        cls.connector = cls.env["discuss_hub.connector"].create(
            {
                "name": "Test Base Connector",
                "type": "base",
                "enabled": True,
                "uuid": "11111111-1111-1111-1111-111111111111",
                "url": "http://evolution:8080",
                "api_key": "test_api_key_1234567890",
                "partner_contact_field": "phone",
                "partner_contact_name": "whatsapp",
            }
        )
        cls.plugin = cls.connector.get_plugin()

        # Sample base64 image for testing (1x1 pixel PNG)
        cls.sample_image = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVQI12P4"
            "//8/AAX+Av7czFnnAAAAAElFTkSuQmCC"
        )

    def _create_test_partner(self, name="Test Partner", phone=None):
        """Helper method to create a test partner with optional contact."""
        partner_vals = {"name": name}
        if phone:
            partner_vals["phone"] = phone
        return self.env["res.partner"].create(partner_vals)

    def _create_test_contact_partner(self, parent, phone):
        """Helper method to create a contact partner."""
        return self.env["res.partner"].create(
            {
                "name": self.connector.partner_contact_name,
                "phone": phone,
                "parent_id": parent.id,
            }
        )

    # ===================================================================
    # BASIC PLUGIN TESTS
    # ===================================================================

    def test_plugin_initialization(self):
        """Test plugin is properly initialized with connector."""
        self.assertIsNotNone(self.plugin, "Plugin should be initialized")
        self.assertEqual(
            self.plugin.connector.id,
            self.connector.id,
            "Plugin should reference the correct connector",
        )

    def test_plugin_str_representation(self):
        """Test the string representation of the plugin."""
        plugin_str = str(self.plugin)
        self.assertIn(
            "DiscussHubPlugin: base",
            plugin_str,
            "Plugin string representation should include its name",
        )
        self.assertIn(
            str(self.connector),
            plugin_str,
            "Plugin string representation should include connector info",
        )

    def test_plugin_name(self):
        """Test the name property of the plugin."""
        self.assertEqual(self.plugin.name, "base", "Base plugin name should be 'base'")

    # ===================================================================
    # NOT IMPLEMENTED METHODS TESTS
    # ===================================================================

    def test_process_payload_not_implemented(self):
        """Test that process_payload raises NotImplementedError in base plugin."""
        with self.assertRaises(
            NotImplementedError,
            msg="Base plugin should raise NotImplementedError for process_payload",
        ):
            self.plugin.process_payload()

    def test_get_status_not_implemented(self):
        """Test that get_status raises NotImplementedError in base plugin."""
        with self.assertRaises(
            NotImplementedError,
            msg="Base plugin should raise NotImplementedError for get_status",
        ):
            self.plugin.get_status()

    def test_get_contact_identifier_not_implemented(self):
        """Test get_contact_identifier raises NotImplementedError."""
        with self.assertRaises(
            NotImplementedError,
            msg="Base plugin should raise NotImplementedError for "
            "get_contact_identifier",
        ):
            self.plugin.get_contact_identifier(payload={"name": "test"})

    def test_get_contact_name_not_implemented(self):
        """Test that get_contact_name raises NotImplementedError in base plugin."""
        with self.assertRaises(
            NotImplementedError,
            msg="Base plugin should raise NotImplementedError for get_contact_name",
        ):
            self.plugin.get_contact_name({})

    def test_get_message_id_not_implemented(self):
        """Test that get_message_id raises NotImplementedError in base plugin."""
        with self.assertRaises(
            NotImplementedError,
            msg="Base plugin should raise NotImplementedError for get_message_id",
        ):
            self.plugin.get_message_id({})

    def test_get_channel_name_not_implemented(self):
        """Test that get_channel_name raises NotImplementedError in base plugin."""
        with self.assertRaises(
            NotImplementedError,
            msg="Base plugin should raise NotImplementedError for get_channel_name",
        ):
            self.plugin.get_channel_name({})

    def test_restart_instance_not_implemented(self):
        """Test that restart_instance raises NotImplementedError in base plugin."""
        with self.assertRaises(
            NotImplementedError,
            msg="Base plugin should raise NotImplementedError for restart_instance",
        ):
            self.plugin.restart_instance()

    def test_outgo_reaction_not_implemented(self):
        """Test that outgo_reaction raises NotImplementedError in base plugin."""
        with self.assertRaises(
            NotImplementedError,
            msg="Base plugin should raise NotImplementedError for outgo_reaction",
        ):
            self.plugin.outgo_reaction(None, None, None)

    def test_logout_instance_not_implemented(self):
        """Test that logout_instance raises NotImplementedError in base plugin."""
        with self.assertRaises(
            NotImplementedError,
            msg="Base plugin should raise NotImplementedError for logout_instance",
        ):
            self.plugin.logout_instance()

    # ===================================================================
    # PARTNER CREATION AND RETRIEVAL TESTS
    # ===================================================================

    def test_get_or_create_partner_new(self):
        """Test creating a new partner when none exists."""
        # Mock required methods
        test_phone = "+1234567890"
        test_name = "New Test Partner"
        self.plugin.get_contact_identifier = lambda payload: test_phone
        self.plugin.get_contact_name = lambda payload: test_name
        self.plugin.get_message_id = lambda payload: "msg_123"

        # Test get_or_create_partner
        result_partner = self.plugin.get_or_create_partner(
            payload={"test": "data"}, update_profile_picture=False
        )

        self.assertEqual(
            result_partner.name,
            self.connector.partner_contact_name,
            "Contact partner should have the configured contact name",
        )
        self.assertEqual(
            result_partner.phone,
            test_phone,
            "Contact partner should have the correct phone",
        )
        self.assertEqual(
            result_partner.parent_id.name,
            test_name,
            "Parent partner should have the contact name from payload",
        )
        self.assertEqual(
            result_partner.parent_id.phone,
            test_phone,
            "Parent partner should have the same phone",
        )

    def test_get_or_create_partner_non_existing_no_create(self):
        """Test not creating a new partner when create_contact is False."""
        # Mock the contact identifier method
        self.plugin.get_contact_identifier = lambda payload: "+9999999999"
        self.plugin.get_message_id = lambda payload: "msg_124"

        # Test get_or_create_partner with create_contact=False
        result_partner = self.plugin.get_or_create_partner(
            payload={"test": "data"},
            update_profile_picture=False,
            create_contact=False,
        )

        self.assertFalse(
            result_partner,
            "Should return False when no partner exists and create_contact is False",
        )

    def test_get_or_create_partner_existing(self):
        """Test retrieving an existing partner."""
        test_phone = "+5511999887766"

        # Create an existing parent partner
        parent_partner = self._create_test_partner(
            name="Existing Parent Partner", phone=test_phone
        )

        # Create contact partner
        partner_contact = self._create_test_contact_partner(parent_partner, test_phone)

        # Mock methods
        self.plugin.get_contact_identifier = lambda payload: test_phone
        self.plugin.get_message_id = lambda payload: "msg_125"

        # Test get_or_create_partner
        result_partner = self.plugin.get_or_create_partner(
            payload={"test": "data"}, update_profile_picture=False
        )

        self.assertEqual(
            result_partner.id,
            partner_contact.id,
            "Should return the existing partner contact",
        )
        self.assertEqual(
            result_partner.parent_id.id,
            parent_partner.id,
            "Should reference the correct parent partner",
        )

    def test_get_or_create_partner_returns_parent_when_no_create(self):
        """Test get_or_create_partner returns parent when no create."""
        test_phone = "+5511888776655"

        # Create existing partners
        parent_partner = self._create_test_partner(name="Test Parent", phone=test_phone)
        self._create_test_contact_partner(parent_partner, test_phone)

        # Mock methods
        self.plugin.get_contact_identifier = lambda payload: test_phone
        self.plugin.get_message_id = lambda payload: "msg_126"

        # Test with create_contact=False
        result = self.plugin.get_or_create_partner(
            payload={"test": "data"},
            update_profile_picture=False,
            create_contact=False,
        )

        self.assertEqual(
            result.id,
            parent_partner.id,
            "Should return parent partner when create_contact=False",
        )

    # ===================================================================
    # PROFILE PICTURE UPDATE TESTS
    # ===================================================================

    def test_update_profile_picture_default_fields(self):
        """Test updating profile picture with default image fields."""
        test_partner = self._create_test_partner(name="Profile Pic Test Partner")

        # Test with default image fields
        result = self.plugin.update_profile_picture(test_partner, self.sample_image)

        self.assertTrue(result, "Profile picture update should succeed")
        sample_image_bytes = self.sample_image.encode("utf-8")
        self.assertEqual(
            test_partner.image_1920,
            sample_image_bytes,
            "Image should be updated in image_1920 field",
        )
        self.assertEqual(
            test_partner.image_128,
            sample_image_bytes,
            "Image should be updated in image_128 field",
        )

    def test_update_profile_picture_custom_fields(self):
        """Test updating profile picture with custom image fields."""
        test_partner = self._create_test_partner(name="Custom Field Test Partner")

        # Test with custom image fields
        custom_fields = ["image_128"]
        result = self.plugin.update_profile_picture(
            test_partner, self.sample_image, images=custom_fields
        )

        self.assertTrue(
            result, "Profile picture update with custom fields should succeed"
        )
        sample_image_bytes = self.sample_image.encode("utf-8")
        self.assertEqual(
            test_partner.image_128,
            sample_image_bytes,
            "Image should be updated in custom field",
        )

    def test_update_profile_picture_invalid_data(self):
        """Test updating profile picture with invalid image data."""
        test_partner = self._create_test_partner(name="Invalid Data Test Partner")

        # Test with invalid image data
        invalid_image = "not-a-valid-base64-image"
        result = self.plugin.update_profile_picture(test_partner, invalid_image)

        self.assertFalse(result, "Profile picture update with invalid data should fail")

    def test_get_or_create_partner_with_profile_picture_update(self):
        """Test get_or_create_partner with profile picture update enabled."""
        test_phone = "+5511777665544"
        test_name = "Profile Update Partner"

        # Mock methods
        self.plugin.get_contact_identifier = lambda p: test_phone
        self.plugin.get_contact_name = lambda p: test_name
        self.plugin.get_message_id = lambda p: "msg_127"
        self.plugin.get_profile_picture = lambda p: self.sample_image

        # Create a new partner with profile picture update
        partner = self.plugin.get_or_create_partner(
            payload={"test": "data"}, update_profile_picture=True
        )

        # Verify the partner was created
        self.assertEqual(partner.phone, test_phone, "Phone should match")
        self.assertEqual(partner.parent_id.name, test_name, "Parent name should match")

        # Verify profile picture was set
        sample_image_bytes = self.sample_image.encode("utf-8")
        self.assertEqual(
            partner.image_128,
            sample_image_bytes,
            "Profile picture should be set for contact",
        )
        self.assertEqual(
            partner.parent_id.image_128,
            sample_image_bytes,
            "Profile picture should be set for parent",
        )

    def test_get_or_create_partner_with_always_update_profile(self):
        """Test get_or_create_partner with always_update_profile_picture enabled."""
        # Enable always update profile picture
        self.connector.always_update_profile_picture = True

        test_phone = "+5511666554433"
        test_name = "Always Update Partner"

        # Old image (different from sample_image) - 1x1 pixel red PNG
        old_image = (
            b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVQI12P4"
            b"z8DwHwAFBQIB6OfH+gAAAABJRU5ErkJggg=="
        )

        # Create existing partners with profile pictures
        parent_partner = self._create_test_partner(name=test_name, phone=test_phone)
        parent_partner.image_128 = old_image

        partner_contact = self._create_test_contact_partner(parent_partner, test_phone)
        partner_contact.image_128 = old_image

        # Mock methods
        self.plugin.get_contact_identifier = lambda p: test_phone
        self.plugin.get_contact_name = lambda p: test_name
        self.plugin.get_message_id = lambda p: "msg_128"
        self.plugin.get_profile_picture = lambda p: self.sample_image

        # Call get_or_create_partner with update enabled
        result_partner = self.plugin.get_or_create_partner(
            payload={"test": "data"}, update_profile_picture=True
        )

        # Verify the existing partner was found
        self.assertEqual(
            result_partner.id,
            partner_contact.id,
            "Should return the existing partner",
        )

        # Verify profile picture was updated even though it already existed
        sample_image_bytes = self.sample_image.encode("utf-8")
        self.assertEqual(
            result_partner.image_128,
            sample_image_bytes,
            "Profile picture should be updated",
        )
        self.assertEqual(
            result_partner.parent_id.image_128,
            sample_image_bytes,
            "Parent profile picture should be updated",
        )

    def test_get_or_create_partner_skip_profile_update_when_exists(self):
        """Test profile picture not updated when exists and no always_update."""
        self.connector.always_update_profile_picture = False

        test_phone = "+5511555443322"
        # Use a valid base64 image (2x2 pixel PNG)
        old_image = (
            "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVQI12P4"
            "//8/AwMDMxADABUCAv8Jne1tAAAAAElFTkSuQmCC"
        )

        # Create existing partner with image
        parent_partner = self._create_test_partner(
            name="Has Image Partner", phone=test_phone
        )
        parent_partner.image_128 = old_image

        partner_contact = self._create_test_contact_partner(parent_partner, test_phone)
        partner_contact.image_128 = old_image

        # Mock methods
        self.plugin.get_contact_identifier = lambda p: test_phone
        self.plugin.get_message_id = lambda p: "msg_129"
        self.plugin.get_profile_picture = lambda p: self.sample_image

        # Call with update enabled but partner already has image
        result_partner = self.plugin.get_or_create_partner(
            payload={"test": "data"}, update_profile_picture=True
        )

        # Verify image was NOT updated (Odoo stores as bytes, so compare as bytes)
        self.assertEqual(
            result_partner.image_128,
            old_image.encode("utf-8"),
            "Profile picture should not be updated when it exists and "
            "always_update is False",
        )

    # ===================================================================
    # CHANNEL CREATION AND RETRIEVAL TESTS
    # ===================================================================

    def test_get_or_create_channel_new(self):
        """Test creating a new channel when none exists."""
        contact_identifier = "+5511444332211"
        channel_name = f"WhatsApp: Test <{contact_identifier}>"

        # Create test partner
        parent_partner = self._create_test_partner(name="Channel Test Parent")
        partner = self._create_test_contact_partner(parent_partner, contact_identifier)

        # Mock plugin methods
        self.plugin.get_message_id = lambda payload: "msg_130"
        self.plugin.get_channel_name = lambda payload: channel_name
        self.plugin.get_contact_identifier = lambda payload: contact_identifier

        # Mock connector method using patch
        with patch.object(
            type(self.connector), "get_initial_routed_partners", return_value=[]
        ):
            # Call the method
            channel = self.plugin.get_or_create_channel(partner, {})

        # Verify new channel was created
        self.assertIsNotNone(channel, "Channel should be created")
        self.assertEqual(channel.name, channel_name, "Channel name should match")
        self.assertEqual(
            channel.discuss_hub_connector.id,
            self.connector.id,
            "Channel should be linked to connector",
        )
        self.assertEqual(
            channel.discuss_hub_outgoing_destination,
            contact_identifier,
            "Channel should have correct destination",
        )
        self.assertTrue(channel.active, "Channel should be active")
        self.assertIn(
            parent_partner.id,
            channel.channel_member_ids.partner_id.ids,
            "Parent partner should be a channel member",
        )

    def test_get_or_create_channel_existing_active(self):
        """Test get_or_create_channel when an active channel already exists."""
        contact_identifier = "+5511333221100"
        channel_name = f"WhatsApp: Existing <{contact_identifier}>"

        # Create test partner
        parent_partner = self._create_test_partner(name="Existing Channel Parent")
        partner = self._create_test_contact_partner(parent_partner, contact_identifier)

        # Create an existing active channel
        existing_channel = self.env["discuss.channel"].create(
            {
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": contact_identifier,
                "name": channel_name,
                "channel_type": "group",
                "active": True,
            }
        )
        # Add parent partner as member
        existing_channel.add_members([parent_partner.id])

        # Mock plugin methods
        self.plugin.get_message_id = lambda payload: "msg_131"
        self.plugin.get_channel_name = lambda payload: channel_name
        self.plugin.get_contact_identifier = lambda payload: contact_identifier

        # Call the method
        channel = self.plugin.get_or_create_channel(partner, {})

        # Verify the existing channel was returned
        self.assertEqual(
            channel.id,
            existing_channel.id,
            "Should return the existing active channel",
        )
        self.assertTrue(channel.active, "Channel should remain active")

    def test_get_or_create_channel_reopen_archived(self):
        """Test get_or_create_channel with reopen_last_archived_channel enabled."""
        # Enable reopen configuration
        self.connector.reopen_last_archived_channel = True

        contact_identifier = "+5511222110099"
        channel_name = f"WhatsApp: Archived <{contact_identifier}>"

        # Create test partners
        parent_partner = self._create_test_partner(name="Archived Channel Parent")
        partner = self._create_test_contact_partner(parent_partner, contact_identifier)

        # Create agent partner for routing
        agent_partner = self._create_test_partner(name="Agent Partner")

        # Create an archived channel
        archived_channel = self.env["discuss.channel"].create(
            {
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": contact_identifier,
                "name": channel_name,
                "channel_type": "group",
                "active": False,  # Archived
            }
        )
        # Add parent partner as member
        archived_channel.add_members([parent_partner.id])

        # Mock plugin methods
        self.plugin.get_message_id = lambda payload: "msg_132"
        self.plugin.get_channel_name = lambda payload: channel_name
        self.plugin.get_contact_identifier = lambda payload: contact_identifier

        # Mock connector method using patch
        with patch.object(
            type(self.connector),
            "get_initial_routed_partners",
            return_value=[agent_partner],
        ):
            # Call the method
            channel = self.plugin.get_or_create_channel(partner, {})

        # Verify the channel was reopened
        self.assertEqual(
            channel.id,
            archived_channel.id,
            "Should return the same channel (reopened)",
        )
        self.assertTrue(channel.active, "Channel should be reactivated")
        self.assertIn(
            agent_partner.id,
            channel.channel_member_ids.partner_id.ids,
            "Agent partner should be added to reopened channel",
        )

    def test_get_or_create_channel_no_reopen_creates_new(self):
        """Test that a new channel is created when reopen is disabled."""
        # Disable reopen configuration
        self.connector.reopen_last_archived_channel = False

        contact_identifier = "+5511111009988"
        channel_name = f"WhatsApp: No Reopen <{contact_identifier}>"

        # Create test partner
        parent_partner = self._create_test_partner(name="No Reopen Parent")
        partner = self._create_test_contact_partner(parent_partner, contact_identifier)

        # Create an archived channel
        archived_channel = self.env["discuss.channel"].create(
            {
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": contact_identifier,
                "name": channel_name,
                "channel_type": "group",
                "active": False,  # Archived
            }
        )
        archived_channel.add_members([parent_partner.id])

        # Mock plugin methods
        self.plugin.get_message_id = lambda payload: "msg_133"
        self.plugin.get_channel_name = lambda payload: channel_name
        self.plugin.get_contact_identifier = lambda payload: contact_identifier

        # Mock connector method using patch
        with patch.object(
            type(self.connector), "get_initial_routed_partners", return_value=[]
        ):
            # Call the method
            channel = self.plugin.get_or_create_channel(partner, {})

        # Verify a new channel was created instead of reopening
        self.assertNotEqual(
            channel.id,
            archived_channel.id,
            "Should create a new channel when reopen is disabled",
        )
        self.assertTrue(channel.active, "New channel should be active")
        self.assertFalse(archived_channel.active, "Old channel should remain archived")

    def test_get_or_create_channel_multiple_memberships(self):
        """Test that get_or_create_channel returns the most recent active channel."""
        contact_identifier = "+5511000998877"

        # Create test partner
        parent_partner = self._create_test_partner(name="Multi Channel Parent")
        partner = self._create_test_contact_partner(parent_partner, contact_identifier)

        # Create two channels with different creation times
        old_channel = self.env["discuss.channel"].create(
            {
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": contact_identifier,
                "name": f"Old Channel <{contact_identifier}>",
                "channel_type": "group",
                "active": True,
            }
        )
        old_channel.add_members([parent_partner.id])

        # Create newer channel
        new_channel = self.env["discuss.channel"].create(
            {
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": contact_identifier,
                "name": f"New Channel <{contact_identifier}>",
                "channel_type": "group",
                "active": True,
            }
        )
        new_channel.add_members([parent_partner.id])

        # Mock methods
        self.plugin.get_message_id = lambda payload: "msg_134"
        self.plugin.get_channel_name = lambda payload: f"Test <{contact_identifier}>"
        self.plugin.get_contact_identifier = lambda payload: contact_identifier

        # Call the method
        channel = self.plugin.get_or_create_channel(partner, {})

        # Verify the most recent channel was returned
        self.assertEqual(
            channel.id,
            new_channel.id,
            "Should return the most recently created active channel",
        )

    # ===================================================================
    # EDGE CASES AND ERROR HANDLING TESTS
    # ===================================================================

    def test_get_or_create_partner_with_fallback_name(self):
        """Test contact identifier used as fallback when no name."""
        test_phone = "+5510009988776"

        # Mock methods - get_contact_name returns None
        self.plugin.get_contact_identifier = lambda payload: test_phone
        self.plugin.get_contact_name = lambda payload: None
        self.plugin.get_message_id = lambda payload: "msg_135"

        # Create partner
        partner = self.plugin.get_or_create_partner(
            payload={"test": "data"}, update_profile_picture=False
        )

        # Verify contact identifier was used as name
        self.assertEqual(
            partner.parent_id.name,
            test_phone,
            "Contact identifier should be used as fallback name",
        )

    def test_update_profile_picture_empty_string(self):
        """Test that update_profile_picture handles empty string gracefully."""
        test_partner = self._create_test_partner(name="Empty String Test")

        result = self.plugin.update_profile_picture(test_partner, "")

        # Should fail gracefully (likely raises exception internally)
        self.assertFalse(result, "Update with empty string should fail gracefully")

    def test_get_or_create_channel_with_image_from_partner(self):
        """Test that new channel inherits image from partner."""
        contact_identifier = "+5519998887776"
        channel_name = f"WhatsApp: Image Test <{contact_identifier}>"

        # Create partner with image
        parent_partner = self._create_test_partner(name="Image Parent")
        partner = self._create_test_contact_partner(parent_partner, contact_identifier)
        partner.image_128 = self.sample_image.encode("utf-8")

        # Mock plugin methods
        self.plugin.get_message_id = lambda payload: "msg_136"
        self.plugin.get_channel_name = lambda payload: channel_name
        self.plugin.get_contact_identifier = lambda payload: contact_identifier

        # Mock connector method using patch
        with patch.object(
            type(self.connector), "get_initial_routed_partners", return_value=[]
        ):
            # Create channel
            channel = self.plugin.get_or_create_channel(partner, {})

        # Verify channel has the partner's image
        self.assertEqual(
            channel.image_128,
            partner.image_128,
            "Channel should inherit image from partner",
        )
