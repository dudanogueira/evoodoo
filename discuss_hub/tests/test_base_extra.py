from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("discuss_hub", "plugin_base")
class TestBasePluginExtra(HttpCase):
    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.connector = self.env["discuss_hub.connector"].create(
            {
                "name": "test_connector_extra",
                "type": "base",
                "enabled": True,
                "uuid": "22222222-2222-2222-2222-222222222222",
                "url": "http://evolution:8080",
                "api_key": "0987654321",
            }
        )
        self.plugin = self.connector.get_plugin()

    def test_not_implemented_methods_raise(self):
        """Ensure stub methods raise NotImplementedError"""
        with self.assertRaises(NotImplementedError):
            self.plugin.restart_instance()

        with self.assertRaises(NotImplementedError):
            self.plugin.outgo_reaction(None, None, None)

        with self.assertRaises(NotImplementedError):
            self.plugin.logout_instance()

    def test_get_or_create_partner_create_contact_false_existing(self):
        """When partner exists and create_contact=False, return parent partner"""
        # Prepare connector fields
        self.connector.partner_contact_field = "phone"
        self.connector.partner_contact_name = "whatsapp"

        # Create parent and contact partner
        parent = self.env["res.partner"].create({"name": "Parent A", "phone": "555"})
        self.env["res.partner"].create(
            {"name": "whatsapp", "phone": "555", "parent_id": parent.id}
        )

        # Mock identifier
        self.plugin.get_contact_identifier = lambda payload: "555"

        result = self.plugin.get_or_create_partner(
            payload={}, update_profile_picture=False, create_contact=False
        )
        # Should return the parent partner record
        self.assertEqual(result.id, parent.id)

    def test_update_profile_picture_exception_path(self):
        """Simulate exception during write and ensure False is returned"""

        class BadPartner:
            def __init__(self):
                self.id = 99999

            def write(self, vals):
                # pylint: disable=method-required-super
                raise Exception("write failed")

        bad = BadPartner()
        res = self.plugin.update_profile_picture(bad, "somebase64")
        self.assertFalse(res, "Should return False when partner.write raises")

    def test_get_or_create_channel_inactive_membership_no_reopen_creates_new(self):
        """If membership points to an inactive channel and reopen flag is False,
        a new channel should be created instead of reopening the old one."""
        # Ensure reopen flag is False
        self.connector.reopen_last_archived_channel = False

        contact_identifier = "999888777"
        parent_partner = self.env["res.partner"].create({"name": "PARENT"})
        partner = self.env["res.partner"].create(
            {
                "name": self.plugin.connector.partner_contact_name or "whatsapp",
                "parent_id": parent_partner.id,
                "phone": contact_identifier,
            }
        )

        # Create an archived channel with a membership for the parent
        archived_channel = self.env["discuss.channel"].create(
            {
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": contact_identifier,
                "name": f"Archived <{contact_identifier}>",
                "channel_type": "group",
                "active": False,
            }
        )
        archived_channel.add_members([parent_partner.id])

        # Ensure plugin methods used in creation path are stubbed
        self.plugin.get_message_id = lambda payload: "mid"
        self.plugin.get_channel_name = lambda payload: f"New <{contact_identifier}>"
        self.plugin.get_contact_identifier = lambda payload: contact_identifier

        new_channel = self.plugin.get_or_create_channel(partner, {})

        self.assertNotEqual(
            new_channel.id,
            archived_channel.id,
            "Should create a new channel when archived and not reopening",
        )
        self.assertEqual(new_channel.discuss_hub_connector.id, self.connector.id)
        self.assertEqual(
            new_channel.discuss_hub_outgoing_destination, contact_identifier
        )
