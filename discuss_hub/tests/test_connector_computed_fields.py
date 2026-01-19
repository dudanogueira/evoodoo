"""Tests for connector computed fields and utility methods."""

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("discuss_hub", "connector", "computed_fields")
class TestConnectorComputedFields(TransactionCase):
    """Test suite for discuss_hub.connector computed fields and methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a test connector
        cls.connector = cls.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector",
                "type": "base",
                "enabled": True,
                "uuid": "test-computed-uuid",
                "url": "http://test.example.com",
                "api_key": "test_key",
            }
        )

        # Create test channels for the connector
        cls.channel1 = cls.env["discuss.channel"].create(
            {
                "name": "Test Channel 1",
                "discuss_hub_connector": cls.connector.id,
            }
        )

        cls.channel2 = cls.env["discuss.channel"].create(
            {
                "name": "Test Channel 2",
                "discuss_hub_connector": cls.connector.id,
            }
        )

    def test_compute_channels_total(self):
        """Test _compute_channels_total returns correct count."""
        # Trigger compute
        self.connector._compute_channels_total()

        # Verify count
        self.assertEqual(
            self.connector.channels_total,
            2,
            "Should have 2 channels associated with connector",
        )

    def test_compute_channels_total_zero(self):
        """Test _compute_channels_total returns 0 when no channels."""
        # Create connector without channels
        connector_no_channels = self.env["discuss_hub.connector"].create(
            {
                "name": "Connector No Channels",
                "type": "base",
                "enabled": True,
                "uuid": "no-channels-uuid",
            }
        )

        # Trigger compute
        connector_no_channels._compute_channels_total()

        # Verify count is 0
        self.assertEqual(connector_no_channels.channels_total, 0)

    def test_compute_last_message(self):
        """Test _compute_last_message returns latest message date."""
        # Create messages in channels
        import datetime

        # Old message
        old_date = datetime.datetime(2024, 1, 1, 10, 0, 0)
        self.env["mail.message"].create(
            {
                "body": "<p>Old message</p>",
                "model": "discuss.channel",
                "res_id": self.channel1.id,
            }
        )
        self.channel1.write_date = old_date

        # New message
        new_date = datetime.datetime(2024, 1, 2, 10, 0, 0)
        self.env["mail.message"].create(
            {
                "body": "<p>New message</p>",
                "model": "discuss.channel",
                "res_id": self.channel2.id,
            }
        )
        self.channel2.write_date = new_date

        # Trigger compute
        self.connector._compute_last_message()

        # Verify it returns the latest date
        self.assertIsNotNone(self.connector.last_message_date)

    def test_compute_last_message_no_channels(self):
        """Test _compute_last_message returns None when no channels."""
        # Create connector without channels
        connector_empty = self.env["discuss_hub.connector"].create(
            {
                "name": "Empty Connector",
                "type": "base",
                "enabled": True,
                "uuid": "empty-connector-uuid",
            }
        )

        # Trigger compute
        connector_empty._compute_last_message()

        # Verify returns None
        self.assertFalse(connector_empty.last_message_date)

    def test_compute_evolution_sync_queue_evolution(self):
        """Test _compute_evolution_sync_queue for evolution connector."""
        # Create evolution connector
        evo_connector = self.env["discuss_hub.connector"].create(
            {
                "name": "Evolution Connector",
                "type": "evolution",
                "enabled": True,
                "uuid": "evolution-uuid",
                "evolution_contact_queue": ["contact1", "contact2", "contact3"],
            }
        )

        # Trigger compute
        evo_connector._compute_evolution_sync_queue()

        # Verify count
        self.assertEqual(evo_connector.evolution_contacts_storage_count, 3)

    def test_compute_evolution_sync_queue_non_evolution(self):
        """Test _compute_evolution_sync_queue for non-evolution connector."""
        # Trigger compute on base connector
        self.connector._compute_evolution_sync_queue()

        # Verify count is 0
        self.assertEqual(self.connector.evolution_contacts_storage_count, 0)

    def test_compute_evolution_sync_queue_empty(self):
        """Test _compute_evolution_sync_queue with empty queue."""
        # Create evolution connector with empty queue
        evo_connector = self.env["discuss_hub.connector"].create(
            {
                "name": "Evolution Empty Queue",
                "type": "evolution",
                "enabled": True,
                "uuid": "evolution-empty-uuid",
                "evolution_contact_queue": None,
            }
        )

        # Trigger compute
        evo_connector._compute_evolution_sync_queue()

        # Verify count is 0
        self.assertEqual(evo_connector.evolution_contacts_storage_count, 0)

    @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.get_status")
    def test_compute_status(self, mock_get_status):
        """Test _compute_status sets correct status."""
        # Mock status response
        mock_get_status.return_value = {
            "status": "open",
            "qr_code_base64": "base64encodedqr",
        }

        # Trigger compute
        self.connector._compute_status()

        # Verify status and qr_code
        self.assertEqual(self.connector.status, "open")
        self.assertEqual(self.connector.qr_code_base64, "base64encodedqr")

    @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.get_status")
    def test_compute_status_not_found(self, mock_get_status):
        """Test _compute_status with not_found status."""
        # Mock status response
        mock_get_status.return_value = {"status": "not_found", "qr_code_base64": None}

        # Trigger compute
        self.connector._compute_status()

        # Verify status
        self.assertEqual(self.connector.status, "not_found")
        self.assertFalse(self.connector.qr_code_base64)

    @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.get_status")
    def test_compute_status_qr_code(self, mock_get_status):
        """Test _compute_status with qr_code status."""
        # Mock status response
        mock_get_status.return_value = {
            "status": "qr_code",
            "qr_code_base64": "qr_code_data",
        }

        # Trigger compute
        self.connector._compute_status()

        # Verify status and qr_code
        self.assertEqual(self.connector.status, "qr_code")
        self.assertEqual(self.connector.qr_code_base64, "qr_code_data")

    def test_get_initial_routed_partners(self):
        """Test get_initial_routed_partners returns correct partners."""
        # Create partners
        partner1 = self.env["res.partner"].create({"name": "Partner 1"})
        partner2 = self.env["res.partner"].create({"name": "Partner 2"})

        # Add automatic partners to connector
        self.connector.automatic_added_partners = [(6, 0, [partner1.id, partner2.id])]

        # Get routed partners
        partners = self.connector.get_initial_routed_partners(connector=self.connector)

        # Verify both partners are returned
        self.assertIn(partner1, partners)
        self.assertIn(partner2, partners)

    def test_get_initial_routed_partners_with_team(self):
        """Test get_initial_routed_partners includes team member."""
        # Create partner
        partner1 = self.env["res.partner"].create({"name": "Auto Partner"})

        # Create user for team
        user1 = self.env["res.users"].create(
            {"name": "Team User", "login": "teamuser", "active": True}
        )

        # Create team
        team = self.env["discuss_hub.routing_team"].create(
            {
                "name": "Routing Team",
                "routing_strategy": "round_robin",
                "online_users_only": False,
            }
        )

        # Add user to team
        self.env["discuss_hub.routing_team_member"].create(
            {"team_id": team.id, "user_id": user1.id, "count": 0, "order": 1}
        )

        # Add partner and team to connector
        self.connector.automatic_added_partners = [(6, 0, [partner1.id])]
        self.connector.automatic_added_teams = [(6, 0, [team.id])]

        # Get routed partners
        partners = self.connector.get_initial_routed_partners(connector=self.connector)

        # Verify both automatic partner and team member are included
        self.assertIn(partner1, partners)
        self.assertIn(user1.partner_id, partners)

    def test_get_initial_routed_partners_empty(self):
        """Test get_initial_routed_partners returns empty set when none configured."""
        # Create clean connector
        connector = self.env["discuss_hub.connector"].create(
            {
                "name": "Clean Connector",
                "type": "base",
                "enabled": True,
                "uuid": "clean-uuid",
            }
        )

        # Get routed partners
        partners = connector.get_initial_routed_partners(connector=connector)

        # Verify empty set
        self.assertEqual(len(partners), 0)

    @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.restart_instance")
    def test_restart_instance(self, mock_restart):
        """Test restart_instance calls plugin method."""
        # Call restart
        self.connector.restart_instance()

        # Verify plugin method was called
        mock_restart.assert_called_once()

    @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.logout_instance")
    def test_logout_instance(self, mock_logout):
        """Test logout_instance calls plugin method."""
        # Call logout
        self.connector.logout_instance()

        # Verify plugin method was called
        mock_logout.assert_called_once()

    @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.sync_contacts")
    def test_sync_contacts(self, mock_sync):
        """Test sync_contacts calls plugin method."""
        # Call sync
        self.connector.sync_contacts()

        # Verify plugin method was called
        mock_sync.assert_called_once()

    def test_open_status_modal(self):
        """Test open_status_modal returns correct action."""
        # Call method
        result = self.connector.open_status_modal()

        # Verify return value
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["view_mode"], "form")
        self.assertEqual(result["res_model"], "discuss_hub.connector")
        self.assertEqual(result["res_id"], self.connector.id)
        self.assertEqual(result["target"], "new")
