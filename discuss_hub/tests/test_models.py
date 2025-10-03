from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# @tagged("discuss_hub", "connector")
# class TestDiscussHubConnector(TransactionCase):
#     @classmethod
#     def setUpClass(cls):
#         super().setUpClass()
#         # Create a test connector
#         cls.connector = cls.env["discuss_hub.connector"].create({
#             "name": "test_connector",
#             "type": "base",  # Use base plugin for simplicity
#             "enabled": True,
#             "uuid": "test-uuid-1234",
#             "url": "http://test.example.com",
#             "api_key": "test_api_key",
#             "partner_contact_field": "phone",
#         })

#         # Create a test channel
#         cls.channel = cls.env["discuss.channel"].create({
#             "name": "Test Channel",
#             "discuss_hub_connector": cls.connector.id,
#             "discuss_hub_outgoing_destination": "123456789",
#         })

#         # Create a test message
#         cls.message = cls.env["mail.message"].create({
#             "body": "<p>Test message</p>",
#             "model": "discuss.channel",
#             "res_id": cls.channel.id,
#         })

#         # Create a test partner
#         cls.partner = cls.env["res.partner"].create({
#             "name": "Test Partner",
#             "phone": "123456789",
#         })

#     def test_get_plugin(self):
#         """Test plugin loading functionality"""
#         plugin = self.connector.get_plugin()
#         self.assertEqual(plugin.name, "base")
#         self.assertEqual(plugin.connector, self.connector)

#     @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.process_payload")
#     def test_process_payload(self, mock_process):
#         """Test payload processing is delegated to plugin"""
#         mock_process.return_value = {"success": True}
#         payload = {"event": "test_event", "data": {"key": "value"}}

#         result = self.plugin.process_payload(payload)

#         mock_process.assert_called_once_with(payload)
#         self.assertEqual(result, {"success": True})

#     @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.outgo_message")
#     def test_outgo_message(self, mock_outgo):
#         """Test outgoing message handling"""
#         mock_outgo.return_value = {"message_id": "test_id"}

#         # Test with enabled connector
#         result = self.connector.outgo_message(self.channel, self.message)
#         mock_outgo.assert_called_once_with(self.channel, self.message)
#         self.assertEqual(result, {"message_id": "test_id"})

#         # Test with disabled connector
#         self.connector.enabled = False
#         result = self.connector.outgo_message(self.channel, self.message)
#         self.assertIsNone(result)

#         # Test with missing channel or message
#         self.connector.enabled = True
#         result = self.connector.outgo_message(None, self.message)
#         self.assertIsNone(result)

#     @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.outgo_reaction")
#     def test_outgo_reaction(self, mock_reaction):
#         """Test outgoing reaction handling"""
#         mock_reaction.return_value = {"success": True}

#         # Test with enabled connector
#         result = self.connector.outgo_reaction(self.channel, self.message, "👍")
#         mock_reaction.assert_called_once_with(self.channel, self.message, "👍")
#         self.assertEqual(result, {"success": True})

#         # Test with disabled connector
#         self.connector.enabled = False
#         result = self.connector.outgo_reaction(self.channel, self.message, "👍")
#         self.assertIsNone(result)

#         # Test with missing parameters
#         self.connector.enabled = True
#         result = self.connector.outgo_reaction(None, self.message, "👍")
#         self.assertIsNone(result)

#     @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.get_status")
#     def test_get_status(self, mock_status):
#         """Test status checking"""
#         mock_status.return_value = {
#           "status": "open", "qrcode": "data:image/png;base64,abc123"
#         }

#         result = self.connector.get_status()

#         mock_status.assert_called_once()
#         self.assertEqual(
#               result, {"status": "open", "qrcode": "data:image/png;base64,abc123"}
#         )

#     def test_compute_status(self):
#         """Test status computation"""
#         with patch.object(self.connector, 'get_status') as mock_status:
#             mock_status.return_value = {
#                 "status": "open",
#                 "qr_code_base64": "abc123"
#             }

#             self.connector._compute_status()

#             self.assertEqual(self.connector.status, "open")
#             self.assertEqual(self.connector.qr_code_base64, "abc123")

#     def test_compute_channels_total(self):
#         """Test channels total computation"""
#         # Create additional test channels
#         self.env["discuss.channel"].create({
#             "name": "Test Channel 2",
#             "discuss_hub_connector": self.connector.id,
#         })

#         self.connector._compute_channels_total()

#         # Should have 2 channels (the one created in setup + the one created here)
#         self.assertEqual(self.connector.channels_total, 2)

#     @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.restart_instance")
#     def test_restart_instance(self, mock_restart):
#         """Test restart instance functionality"""
#         self.connector.restart_instance()
#         mock_restart.assert_called_once()

#     @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.logout_instance")
#     def test_logout_instance(self, mock_logout):
#         """Test logout instance functionality"""
#         self.connector.logout_instance()
#         mock_logout.assert_called_once()


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
        with patch.object(self.connector, "get_status") as mock_status:
            # Prepare mock data
            mock_status.return_value = {
                "status": "closed",
                "qrcode": "data:image/png;base64,abc123",
                "success": True,
                "plugin_name": "evolution",
                "connector": str(self.connector),
            }

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


#     #         self.assertTrue("Connector Status" in result["name"])
