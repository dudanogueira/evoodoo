from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("discuss_hub", "connector")
class TestDiscussHubConnector(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a test connector
        cls.connector = cls.env["discuss_hub.connector"].create(
            {
                "name": "test_connector",
                "type": "base",  # Use base plugin for simplicity
                "enabled": True,
                "uuid": "test-uuid-1234",
                "url": "http://test.example.com",
                "api_key": "test_api_key",
                "partner_contact_field": "phone",
            }
        )

        # Create a test channel
        cls.channel = cls.env["discuss.channel"].create(
            {
                "name": "Test Channel",
                "discuss_hub_connector": cls.connector.id,
                "discuss_hub_outgoing_destination": "123456789",
            }
        )

        # Create test partners
        cls.internal_partner = cls.env["res.partner"].create(
            {
                "name": "Internal User Partner",
                "phone": "111111111",
            }
        )

        cls.portal_partner = cls.env["res.partner"].create(
            {
                "name": "Portal User Partner",
                "phone": "222222222",
            }
        )

        cls.public_partner = cls.env["res.partner"].create(
            {
                "name": "Public User Partner",
                "phone": "333333333",
            }
        )

        # Create users - groups will be assigned via user.group_ids using Command.set
        # Following the pattern from base.py plugin
        internal_group = cls.env.ref("base.group_user")
        portal_group = cls.env.ref("base.group_portal")
        public_group = cls.env.ref("base.group_public")

        cls.internal_user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Internal User",
                    "login": "internal_test@test.com",
                    "password": "internal",
                    "partner_id": cls.internal_partner.id,
                }
            )
        )
        cls.internal_user.sudo().write({"group_ids": [(6, 0, [internal_group.id])]})

        cls.portal_user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Portal User",
                    "login": "portal_test@test.com",
                    "password": "portal",
                    "partner_id": cls.portal_partner.id,
                }
            )
        )
        cls.portal_user.sudo().write({"group_ids": [(6, 0, [portal_group.id])]})

        cls.public_user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Public User",
                    "login": "public_test@test.com",
                    "password": "public",
                    "partner_id": cls.public_partner.id,
                }
            )
        )
        cls.public_user.sudo().write({"group_ids": [(6, 0, [public_group.id])]})

        # Create a routing team for testing
        cls.routing_team = cls.env["discuss_hub.routing_team"].create(
            {
                "name": "Test Team",
                "routing_strategy": "round_robin",
                "online_users_only": False,  # Allow offline users for testing
            }
        )
        # Add a team member
        cls.env["discuss_hub.routing_team_member"].create(
            {
                "team_id": cls.routing_team.id,
                "user_id": cls.internal_user.id,
            }
        )

    def test_get_plugin(self):
        """Test plugin loading functionality"""
        plugin = self.connector.get_plugin()
        self.assertEqual(plugin.plugin_name, "base")
        self.assertEqual(plugin.connector, self.connector)

    @patch("plugins.base.Plugin.process_payload")
    def test_process_payload(self, mock_process):
        """Test payload processing is delegated to plugin"""
        mock_process.return_value = {"success": True}
        payload = {"event": "test_event", "data": {"key": "value"}}

        result = self.connector.process_payload(payload)

        mock_process.assert_called_once_with(payload)
        self.assertEqual(result, {"success": True})

    @patch("plugins.base.Plugin.outgo_message")
    def test_outgo_message_enabled_connector(self, mock_outgo):
        """Test outgoing message with enabled connector"""
        mock_outgo.return_value = {"message_id": "test_id"}

        # Create message from internal user
        message = self.env["mail.message"].create(
            {
                "body": "<p>Test message</p>",
                "model": "discuss.channel",
                "res_id": self.channel.id,
                "author_id": self.internal_partner.id,
                "message_type": "comment",
            }
        )

        result = self.connector.outgo_message(self.channel, message)
        mock_outgo.assert_called_once_with(self.channel, message)
        self.assertEqual(result, {"message_id": "test_id"})

    def test_outgo_message_disabled_connector(self):
        """Test outgoing message with disabled connector"""
        self.connector.enabled = False

        message = self.env["mail.message"].create(
            {
                "body": "<p>Test message</p>",
                "model": "discuss.channel",
                "res_id": self.channel.id,
                "author_id": self.internal_partner.id,
            }
        )

        result = self.connector.outgo_message(self.channel, message)
        self.assertIsNone(result)

    def test_outgo_message_skip_notification_messages(self):
        """Test notification messages skipped when setting is False."""
        self.connector.reproduce_notification_messages = False

        message = self.env["mail.message"].create(
            {
                "body": "<p>System notification</p>",
                "model": "discuss.channel",
                "res_id": self.channel.id,
                "author_id": self.internal_partner.id,
                "message_type": "notification",
            }
        )

        result = self.connector.outgo_message(self.channel, message)
        self.assertIsNone(result)

    @patch("plugins.base.Plugin.outgo_message")
    def test_outgo_message_send_notification_messages(self, mock_outgo):
        """Test notification messages sent when reproduce_notification_messages=True."""
        self.connector.reproduce_notification_messages = True
        mock_outgo.return_value = {"message_id": "test_id"}

        message = self.env["mail.message"].create(
            {
                "body": "<p>System notification</p>",
                "model": "discuss.channel",
                "res_id": self.channel.id,
                "author_id": self.internal_partner.id,
                "message_type": "notification",
            }
        )

        result = self.connector.outgo_message(self.channel, message)
        mock_outgo.assert_called_once_with(self.channel, message)
        self.assertEqual(result, {"message_id": "test_id"})

    def test_outgo_message_skip_portal_user(self):
        """Test that messages from portal users are skipped"""
        message = self.env["mail.message"].create(
            {
                "body": "<p>Portal message</p>",
                "model": "discuss.channel",
                "res_id": self.channel.id,
                "author_id": self.portal_partner.id,
            }
        )

        result = self.connector.outgo_message(self.channel, message)
        self.assertIsNone(result)

    def test_outgo_message_skip_public_user(self):
        """Test that messages from public users are skipped"""
        message = self.env["mail.message"].create(
            {
                "body": "<p>Public message</p>",
                "model": "discuss.channel",
                "res_id": self.channel.id,
                "author_id": self.public_partner.id,
            }
        )

        result = self.connector.outgo_message(self.channel, message)
        self.assertIsNone(result)

    @patch("plugins.base.Plugin.outgo_reaction")
    def test_outgo_reaction_enabled(self, mock_reaction):
        """Test outgoing reaction with enabled connector"""
        mock_reaction.return_value = {"success": True}

        message = self.env["mail.message"].create(
            {
                "body": "<p>Test message</p>",
                "model": "discuss.channel",
                "res_id": self.channel.id,
            }
        )

        reaction = self.env["mail.message.reaction"].create(
            {
                "message_id": message.id,
                "partner_id": self.internal_partner.id,
                "content": "👍",
            }
        )

        result = self.connector.outgo_reaction(self.channel, message, reaction)
        mock_reaction.assert_called_once_with(self.channel, message, reaction)
        self.assertEqual(result, {"success": True})

    def test_outgo_reaction_disabled(self):
        """Test outgoing reaction with disabled connector"""
        self.connector.enabled = False

        message = self.env["mail.message"].create(
            {
                "body": "<p>Test message</p>",
                "model": "discuss.channel",
                "res_id": self.channel.id,
            }
        )

        reaction = "👍"

        result = self.connector.outgo_reaction(self.channel, message, reaction)
        self.assertIsNone(result)

    def test_outgo_reaction_missing_parameters(self):
        """Test outgoing reaction with missing parameters"""
        message = self.env["mail.message"].create(
            {
                "body": "<p>Test message</p>",
                "model": "discuss.channel",
                "res_id": self.channel.id,
            }
        )

        # Missing channel
        result = self.connector.outgo_reaction(None, message, "👍")
        self.assertIsNone(result)

        # Missing message
        result = self.connector.outgo_reaction(self.channel, None, "👍")
        self.assertIsNone(result)

        # Missing reaction
        result = self.connector.outgo_reaction(self.channel, message, None)
        self.assertIsNone(result)

    @patch("plugins.base.Plugin.get_status")
    def test_get_status(self, mock_status):
        """Test status checking"""
        mock_status.return_value = {
            "status": "open",
            "qrcode": "data:image/png;base64,abc123",
        }

        result = self.connector.get_status()

        mock_status.assert_called_once()
        self.assertEqual(
            result, {"status": "open", "qrcode": "data:image/png;base64,abc123"}
        )

    def test_compute_status(self):
        """Test status computation with default plugin implementation"""
        # The base plugin returns {"status": "not_found", "plugin_name": "base"}
        # by default, so we test that behavior
        self.connector._compute_status()

        # With the default base plugin implementation
        self.assertEqual(self.connector.status, "not_found")
        self.assertFalse(self.connector.qr_code_base64)

    def test_compute_status_not_found(self):
        """Test status computation defaults to not_found when status key is missing"""
        # The base plugin already returns {"status": "not_found"}, so this
        # tests the actual default behavior
        self.connector._compute_status()

        self.assertEqual(self.connector.status, "not_found")

    def test_compute_channels_total(self):
        """Test channels total computation"""
        # Create additional test channel
        self.env["discuss.channel"].create(
            {
                "name": "Test Channel 2",
                "discuss_hub_connector": self.connector.id,
            }
        )

        self.connector._compute_channels_total()

        # Should have 2 channels (the one created in setup + the one created here)
        self.assertEqual(self.connector.channels_total, 2)

    def test_compute_last_message(self):
        """Test last message date computation"""
        self.connector._compute_last_message()

        # Should have a last message date from the channel
        self.assertIsNotNone(self.connector.last_message_date)

    def test_compute_last_message_no_channels(self):
        """Test last message date computation with no channels"""
        # Create a new connector without channels
        connector_no_channels = self.env["discuss_hub.connector"].create(
            {
                "name": "test_connector_no_channels",
                "type": "base",
                "enabled": True,
            }
        )

        connector_no_channels._compute_last_message()

        # Should have no last message date
        self.assertFalse(connector_no_channels.last_message_date)

    def test_compute_evolution_sync_queue(self):
        """Test evolution sync queue computation"""
        # Create evolution connector
        evolution_connector = self.env["discuss_hub.connector"].create(
            {
                "name": "test_evolution",
                "type": "evolution",
                "enabled": True,
                "evolution_contact_queue": [
                    {"id": "1", "name": "Contact 1"},
                    {"id": "2", "name": "Contact 2"},
                ],
            }
        )

        evolution_connector._compute_evolution_sync_queue()

        self.assertEqual(evolution_connector.evolution_contacts_storage_count, 2)

    def test_compute_evolution_sync_queue_non_evolution(self):
        """Test evolution sync queue computation for non-evolution connector"""
        self.connector._compute_evolution_sync_queue()

        self.assertEqual(self.connector.evolution_contacts_storage_count, 0)

    def test_compute_evolution_sync_queue_empty(self):
        """Test evolution sync queue computation with empty queue"""
        evolution_connector = self.env["discuss_hub.connector"].create(
            {
                "name": "test_evolution_empty",
                "type": "evolution",
                "enabled": True,
                "evolution_contact_queue": None,
            }
        )

        evolution_connector._compute_evolution_sync_queue()

        self.assertEqual(evolution_connector.evolution_contacts_storage_count, 0)

    @patch("plugins.base.Plugin.restart_instance")
    def test_restart_instance(self, mock_restart):
        """Test restart instance functionality"""
        self.connector.restart_instance()
        mock_restart.assert_called_once()

    @patch("plugins.base.Plugin.logout_instance")
    def test_logout_instance(self, mock_logout):
        """Test logout instance functionality"""
        self.connector.logout_instance()
        mock_logout.assert_called_once()

    def test_get_initial_routed_partners_with_partners(self):
        """Test get_initial_routed_partners with automatic partners"""
        self.connector.automatic_added_partners = [(6, 0, [self.internal_partner.id])]

        partners = self.connector.get_initial_routed_partners()

        self.assertIn(self.internal_partner, partners)

    def test_get_initial_routed_partners_with_teams(self):
        """Test get_initial_routed_partners with routing teams"""
        self.connector.automatic_added_teams = [(6, 0, [self.routing_team.id])]

        partners = self.connector.get_initial_routed_partners()

        # Should contain a partner from the team
        self.assertTrue(len(partners) > 0)

    def test_get_initial_routed_partners_empty(self):
        """Test get_initial_routed_partners with no routing"""
        partners = self.connector.get_initial_routed_partners()

        # Should return empty set
        self.assertEqual(len(partners), 0)

    def test_action_send_msg(self):
        """Test action_send_msg opens wizard"""
        result = self.connector.action_send_msg()

        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "whatsapp.send.message")
        self.assertEqual(result["target"], "new")

    def test_open_status_modal(self):
        """Test open_status_modal opens form view"""
        result = self.connector.open_status_modal()

        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "discuss_hub.connector")
        self.assertEqual(result["res_id"], self.connector.id)
        self.assertEqual(result["target"], "new")


@tagged("discuss_hub", "connector", "integration")
class TestDiscussHubConnectorIntegration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a test connector with evolution plugin
        cls.connector = cls.env["discuss_hub.connector"].create(
            {
                "name": "test_evolution",
                "type": "evolution",
                "enabled": True,
                "uuid": "test-uuid-5678",
                "url": "http://evolution:8080",
                "api_key": "test_api_key",
                "partner_contact_field": "phone",
            }
        )

    def test_action_open_start(self):
        """Test the action_open_start method which opens the connector status dialog"""
        # Mock the plugin's get_status method instead of the connector's
        plugin = self.connector.get_plugin()

        with patch.object(
            type(plugin),
            "get_status",
            return_value={
                "status": "closed",
                "qrcode": "data:image/png;base64,abc123",
                "success": True,
                "plugin_name": "evolution",
                "connector": str(self.connector),
            },
        ):
            # Call the method to be tested
            result = self.connector.action_open_start()

            # Verify the result
            self.assertEqual(result["type"], "ir.actions.act_window")
            self.assertEqual(result["res_model"], "discuss_hub.connector.status")
            self.assertTrue("default_html_content" in result["context"])

            # Verify the content contains the expected status and QR code
            html_content = result["context"]["default_html_content"]
            self.assertIn("Status: closed", html_content)
            self.assertIn("data:image/png;base64,abc123", html_content)
            self.assertIn(self.connector.name, html_content)

    def test_action_open_start_with_qr_code_status(self):
        """Test action_open_start with different status values"""
        plugin = self.connector.get_plugin()

        with patch.object(
            type(plugin),
            "get_status",
            return_value={
                "status": "qr_code",
                "qrcode": "data:image/png;base64,qrcode123",
            },
        ):
            result = self.connector.action_open_start()
            html_content = result["context"]["default_html_content"]
            self.assertIn("Status: qr_code", html_content)


@tagged("discuss_hub", "social_network_type")
class TestDiscussHubSocialNetworkType(TransactionCase):
    def test_create_social_network_type(self):
        """Test creating a social network type"""
        network_type = self.env["discuss_hub.social_network_type"].create(
            {
                "name": "WhatsApp",
            }
        )

        self.assertEqual(network_type.name, "WhatsApp")
        self.assertTrue(network_type.id)

    def test_social_network_type_name_required(self):
        """Test that name is required for social network type"""
        from psycopg2 import IntegrityError

        # The database will raise IntegrityError
        # Try to create without name and expect it to fail
        with self.assertRaises(IntegrityError):
            self.env["discuss_hub.social_network_type"].create({})
            # Force flush to database to trigger constraint
            self.env.cr.flush()


@tagged("discuss_hub", "connector_status")
class TestDiscussHubConnectorStatus(TransactionCase):
    def test_create_connector_status(self):
        """Test creating a connector status transient model"""
        status = self.env["discuss_hub.connector.status"].create(
            {
                "html_content": "<h1>Test Status</h1>",
            }
        )

        self.assertEqual(status.html_content, "<h1>Test Status</h1>")
        self.assertTrue(status.id)

    def test_connector_status_readonly(self):
        """Test that html_content can be set on creation"""
        status = self.env["discuss_hub.connector.status"].create(
            {
                "html_content": "<p>Initial content</p>",
            }
        )

        # Verify content was set
        self.assertEqual(status.html_content, "<p>Initial content</p>")


@tagged("discuss_hub", "connector_fields")
class TestDiscussHubConnectorFields(TransactionCase):
    def test_default_uuid_generation(self):
        """Test that UUID is automatically generated on create"""
        connector1 = self.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector 1",
                "type": "base",
            }
        )

        connector2 = self.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector 2",
                "type": "base",
            }
        )

        # Both should have UUIDs
        self.assertTrue(connector1.uuid)
        self.assertTrue(connector2.uuid)

        # UUIDs should be different
        self.assertNotEqual(connector1.uuid, connector2.uuid)

    def test_default_values(self):
        """Test default field values"""
        connector = self.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector",
                "type": "evolution",
            }
        )

        self.assertTrue(connector.enabled)
        self.assertTrue(connector.import_contacts)
        self.assertEqual(connector.partner_contact_name, "whatsapp")
        self.assertEqual(connector.partner_contact_field, "phone")
        self.assertFalse(connector.reopen_last_archived_channel)
        self.assertFalse(connector.always_update_profile_picture)
        self.assertTrue(connector.show_read_receipts)
        self.assertTrue(connector.notify_reactions)
        self.assertFalse(connector.reproduce_notification_messages)
        self.assertTrue(connector.evolution_allow_broadcast_messages)

    def test_text_message_template_default(self):
        """Test default text message template"""
        connector = self.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector",
                "type": "base",
            }
        )

        expected_template = (
            "<p><b>[{{message.author_id.name}}]</b><br /><p>{{body}}</p></p>"
        )
        self.assertEqual(connector.text_message_template, expected_template)

    def test_default_admin_partner(self):
        """Test default admin partner is set"""
        connector = self.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector",
                "type": "base",
            }
        )

        # Should have default admin partner (usually the admin user)
        self.assertTrue(connector.default_admin_partner_id)

    def test_create_user_for_visitor_options(self):
        """Test create_user_for_visitor field options"""
        connector = self.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector",
                "type": "base",
                "create_user_for_visitor": "portal",
            }
        )

        self.assertEqual(connector.create_user_for_visitor, "portal")

        # Test other options
        connector.create_user_for_visitor = "guest"
        self.assertEqual(connector.create_user_for_visitor, "guest")

        connector.create_user_for_visitor = "none"
        self.assertEqual(connector.create_user_for_visitor, "none")


@tagged("discuss_hub", "connector_relations")
class TestDiscussHubConnectorRelations(TransactionCase):
    def test_many2many_manager_channel(self):
        """Test manager_channel Many2many relation"""
        connector = self.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector",
                "type": "base",
            }
        )

        channel1 = self.env["discuss.channel"].create(
            {
                "name": "Manager Channel 1",
            }
        )

        channel2 = self.env["discuss.channel"].create(
            {
                "name": "Manager Channel 2",
            }
        )

        connector.manager_channel = [(6, 0, [channel1.id, channel2.id])]

        self.assertEqual(len(connector.manager_channel), 2)
        self.assertIn(channel1, connector.manager_channel)
        self.assertIn(channel2, connector.manager_channel)

    def test_many2many_automatic_added_partners(self):
        """Test automatic_added_partners Many2many relation"""
        connector = self.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector",
                "type": "base",
            }
        )

        partner1 = self.env["res.partner"].create(
            {
                "name": "Partner 1",
            }
        )

        partner2 = self.env["res.partner"].create(
            {
                "name": "Partner 2",
            }
        )

        connector.automatic_added_partners = [(6, 0, [partner1.id, partner2.id])]

        self.assertEqual(len(connector.automatic_added_partners), 2)
        self.assertIn(partner1, connector.automatic_added_partners)
        self.assertIn(partner2, connector.automatic_added_partners)

    def test_many2many_automatic_added_teams(self):
        """Test automatic_added_teams Many2many relation"""
        connector = self.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector",
                "type": "base",
            }
        )

        team1 = self.env["discuss_hub.routing_team"].create(
            {
                "name": "Team 1",
            }
        )

        team2 = self.env["discuss_hub.routing_team"].create(
            {
                "name": "Team 2",
            }
        )

        connector.automatic_added_teams = [(6, 0, [team1.id, team2.id])]

        self.assertEqual(len(connector.automatic_added_teams), 2)
        self.assertIn(team1, connector.automatic_added_teams)
        self.assertIn(team2, connector.automatic_added_teams)

    def test_many2many_ignore_partners(self):
        """Test ignore_partners Many2many relation"""
        connector = self.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector",
                "type": "base",
            }
        )

        partner1 = self.env["res.partner"].create(
            {
                "name": "Ignored Partner 1",
            }
        )

        connector.ignore_partners = [(6, 0, [partner1.id])]

        self.assertEqual(len(connector.ignore_partners), 1)
        self.assertIn(partner1, connector.ignore_partners)


@tagged("discuss_hub", "connector_evolution")
class TestDiscussHubConnectorEvolutionFields(TransactionCase):
    def test_evolution_specific_fields(self):
        """Test evolution-specific fields"""
        connector = self.env["discuss_hub.connector"].create(
            {
                "name": "Evolution Connector",
                "type": "evolution",
                "evolution_allow_broadcast_messages": False,
                "evolution_contact_queue": [{"id": "1"}, {"id": "2"}],
            }
        )

        self.assertFalse(connector.evolution_allow_broadcast_messages)
        self.assertEqual(len(connector.evolution_contact_queue), 2)


@tagged("discuss_hub", "connector_whatsapp_cloud")
class TestDiscussHubConnectorWhatsAppCloudFields(TransactionCase):
    def test_whatsapp_cloud_specific_fields(self):
        """Test WhatsApp Cloud-specific fields"""
        connector = self.env["discuss_hub.connector"].create(
            {
                "name": "WhatsApp Cloud Connector",
                "type": "whatsapp_cloud",
                "verify_token": "my_verify_token_123",
                "whatsapp_cloud_reengage_template": "reengage_template_name",
            }
        )

        self.assertEqual(connector.verify_token, "my_verify_token_123")
        self.assertEqual(
            connector.whatsapp_cloud_reengage_template, "reengage_template_name"
        )
