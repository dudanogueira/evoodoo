"""Tests for mail.message.reaction model extensions."""

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("discuss_hub", "mail_message_reaction")
class TestMailMessageReaction(TransactionCase):
    """Test suite for mail.message.reaction integration with discuss_hub."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a test connector
        cls.connector = cls.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector",
                "type": "base",
                "enabled": True,
                "uuid": "test-reaction-uuid",
            }
        )

        # Create a test channel
        cls.channel = cls.env["discuss.channel"].create(
            {
                "name": "Test Channel",
                "discuss_hub_connector": cls.connector.id,
            }
        )

        # Create a test partner
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )

        # Create a test message with discuss_hub_message_id
        cls.message = cls.env["mail.message"].create(
            {
                "body": "<p>Test message for reaction</p>",
                "model": "discuss.channel",
                "res_id": cls.channel.id,
                "discuss_hub_message_id": "external-msg-123",
            }
        )

    def test_reaction_create_triggers_outgo(self):
        """Test that creating a reaction on external message triggers outgo_reaction."""
        with patch(
            "odoo.addons.discuss_hub.models.models.DiscussHubConnector.outgo_reaction"
        ) as mock_outgo_reaction:
            mock_outgo_reaction.return_value = {"success": True}

            # Create a reaction on the message
            reaction = self.env["mail.message.reaction"].create(
                {
                    "message_id": self.message.id,
                    "partner_id": self.partner.id,
                    "content": "👍",
                }
            )

            # Verify the reaction was created
            self.assertTrue(reaction)
            self.assertEqual(reaction.content, "👍")

            # Verify outgo_reaction was called
            mock_outgo_reaction.assert_called_once()
            # call_args[0] contains (self, channel, message, reaction)
            # We need to check indices [1], [2], [3] (skipping self at [0])
            call_args = mock_outgo_reaction.call_args[0]
            self.assertEqual(call_args[0], self.channel)  # channel
            self.assertEqual(call_args[1], self.message)  # message
            self.assertEqual(call_args[2], reaction)  # reaction

    def test_reaction_write_triggers_outgo(self):
        """Test that updating a reaction triggers outgo_reaction."""
        with patch(
            "odoo.addons.discuss_hub.models.models.DiscussHubConnector.outgo_reaction"
        ) as mock_outgo_reaction:
            mock_outgo_reaction.return_value = {"success": True}

            # Create a reaction first
            reaction = self.env["mail.message.reaction"].create(
                {
                    "message_id": self.message.id,
                    "partner_id": self.partner.id,
                    "content": "👍",
                }
            )

            # Reset the mock to clear create() call
            mock_outgo_reaction.reset_mock()

            # Update the reaction
            reaction.write({"content": "❤️"})

            # Verify outgo_reaction was called on write
            mock_outgo_reaction.assert_called_once()
            # call_args[0] contains (channel, message, reaction)
            call_args = mock_outgo_reaction.call_args[0]
            self.assertEqual(call_args[0], self.channel)  # channel
            self.assertEqual(call_args[1], self.message)  # message
            self.assertEqual(call_args[2], reaction)  # reaction
            self.assertEqual(reaction.content, "❤️")

    def test_reaction_on_message_without_external_id_no_trigger(self):
        """Test that reaction on non-external message doesn't trigger outgo."""
        # Create a message without discuss_hub_message_id
        local_message = self.env["mail.message"].create(
            {
                "body": "<p>Local message</p>",
                "model": "discuss.channel",
                "res_id": self.channel.id,
            }
        )

        # Create a reaction - should not raise error
        reaction = self.env["mail.message.reaction"].create(
            {
                "message_id": local_message.id,
                "partner_id": self.partner.id,
                "content": "👍",
            }
        )

        # Verify reaction was created successfully
        self.assertTrue(reaction)
        self.assertEqual(reaction.content, "👍")

    def test_reaction_on_channel_without_connector_no_trigger(self):
        """Test that reaction on channel without connector doesn't trigger outgo."""
        # Create a channel without connector
        channel_no_connector = self.env["discuss.channel"].create(
            {
                "name": "Channel Without Connector",
            }
        )

        # Create a message with external ID but no connector
        message = self.env["mail.message"].create(
            {
                "body": "<p>Message in channel without connector</p>",
                "model": "discuss.channel",
                "res_id": channel_no_connector.id,
                "discuss_hub_message_id": "external-msg-456",
            }
        )

        # Create a reaction - should not trigger outgo (no error, just no call)
        reaction = self.env["mail.message.reaction"].create(
            {
                "message_id": message.id,
                "partner_id": self.partner.id,
                "content": "👍",
            }
        )

        # Verify reaction was created
        self.assertTrue(reaction)

    def test_reaction_error_handling_does_not_break_creation(self):
        """Test that errors in outgo_reaction don't prevent reaction creation."""
        with patch(
            "odoo.addons.discuss_hub.models.models.DiscussHubConnector.outgo_reaction"
        ) as mock_outgo_reaction:
            # Make outgo_reaction raise an exception
            mock_outgo_reaction.side_effect = Exception("Connector error")

            # Create a reaction - should succeed despite the error
            reaction = self.env["mail.message.reaction"].create(
                {
                    "message_id": self.message.id,
                    "partner_id": self.partner.id,
                    "content": "👍",
                }
            )

            # Verify reaction was created successfully
            self.assertTrue(reaction)
            self.assertEqual(reaction.content, "👍")
            # Verify outgo_reaction was attempted
            mock_outgo_reaction.assert_called_once()

    def test_reaction_write_error_handling_does_not_break_update(self):
        """Test that errors in outgo_reaction don't prevent reaction updates."""
        with patch(
            "odoo.addons.discuss_hub.models.models.DiscussHubConnector.outgo_reaction"
        ) as mock_outgo_reaction:
            # Create a reaction first
            reaction = self.env["mail.message.reaction"].create(
                {
                    "message_id": self.message.id,
                    "partner_id": self.partner.id,
                    "content": "👍",
                }
            )

            # Make outgo_reaction raise an exception for write
            mock_outgo_reaction.side_effect = Exception("Connector error on write")

            # Update the reaction - should succeed despite the error
            reaction.write({"content": "❤️"})

            # Verify reaction was updated successfully
            self.assertEqual(reaction.content, "❤️")

    def test_disabled_connector_no_outgo_on_create(self):
        """Test that reactions don't trigger outgo when connector is disabled."""
        # Disable the connector
        self.connector.enabled = False

        # Create a reaction - connector will reject it because it's disabled
        reaction = self.env["mail.message.reaction"].create(
            {
                "message_id": self.message.id,
                "partner_id": self.partner.id,
                "content": "👍",
            }
        )

        # Verify reaction was created
        self.assertTrue(reaction)
        # outgo_reaction would be called but connector checks if it's enabled

    def test_reaction_create_multi_triggers_outgo_for_each(self):
        """Test that creating multiple reactions triggers outgo for each one."""
        with patch(
            "odoo.addons.discuss_hub.models.models.DiscussHubConnector.outgo_reaction"
        ) as mock_outgo_reaction:
            mock_outgo_reaction.return_value = {"success": True}

            # Create a second partner
            partner2 = self.env["res.partner"].create({"name": "Test Partner 2"})

            # Create multiple reactions at once using create with list
            reactions = self.env["mail.message.reaction"].create(
                [
                    {
                        "message_id": self.message.id,
                        "partner_id": self.partner.id,
                        "content": "👍",
                    },
                    {
                        "message_id": self.message.id,
                        "partner_id": partner2.id,
                        "content": "❤️",
                    },
                ]
            )

            # Verify both reactions were created
            self.assertEqual(len(reactions), 2)
            self.assertEqual(reactions[0].content, "👍")
            self.assertEqual(reactions[1].content, "❤️")

            # Verify outgo_reaction was called twice
            self.assertEqual(mock_outgo_reaction.call_count, 2)

    @patch("odoo.addons.discuss_hub.models.mail_message_reaction._logger")
    def test_reaction_create_logs_info_on_success(self, mock_logger):
        """Test that successful reaction creation logs info message."""
        with patch(
            "odoo.addons.discuss_hub.models.models.DiscussHubConnector.outgo_reaction"
        ) as mock_outgo_reaction:
            mock_outgo_reaction.return_value = {"success": True}

            # Create a reaction
            self.env["mail.message.reaction"].create(
                {
                    "message_id": self.message.id,
                    "partner_id": self.partner.id,
                    "content": "👍",
                }
            )

            # Verify info log was called
            self.assertTrue(mock_logger.info.called)
            log_message = mock_logger.info.call_args[0][0]
            self.assertIn("mail_message_reaction.create", log_message)
            self.assertIn(str(self.connector.id), log_message)
            self.assertIn(str(self.channel.id), log_message)

    @patch("odoo.addons.discuss_hub.models.mail_message_reaction._logger")
    def test_reaction_create_logs_error_on_exception(self, mock_logger):
        """Test that exception during reaction creation logs error."""
        with patch(
            "odoo.addons.discuss_hub.models.models.DiscussHubConnector.outgo_reaction"
        ) as mock_outgo_reaction:
            # Make outgo_reaction raise an exception
            mock_outgo_reaction.side_effect = ValueError("Test error message")

            # Create a reaction - should succeed despite the error
            reaction = self.env["mail.message.reaction"].create(
                {
                    "message_id": self.message.id,
                    "partner_id": self.partner.id,
                    "content": "👍",
                }
            )

            # Verify reaction was created
            self.assertTrue(reaction)

            # Verify error log was called with exc_info=True
            self.assertTrue(mock_logger.error.called)
            log_message = mock_logger.error.call_args[0][0]
            self.assertIn("Error sending outgoing reaction to connector", log_message)
            self.assertIn("Test error message", log_message)
            # Check that exc_info=True was passed
        self.assertTrue(mock_logger.error.call_args[1].get("exc_info"))

    @patch("odoo.addons.discuss_hub.models.mail_message_reaction._logger")
    @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.outgo_reaction")
    def test_reaction_write_logs_info_on_success(
        self, mock_outgo_reaction, mock_logger
    ):
        """Test that successful reaction update logs info message."""
        mock_outgo_reaction.return_value = {"success": True}

        # Create a reaction first
        reaction = self.env["mail.message.reaction"].create(
            {
                "message_id": self.message.id,
                "partner_id": self.partner.id,
                "content": "👍",
            }
        )

        # Reset mock to clear create logs
        mock_logger.reset_mock()

        # Update the reaction
        reaction.write({"content": "❤️"})

        # Verify info log was called
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        self.assertIn("mail_message_reaction.write", log_message)
        self.assertIn(str(self.connector), log_message)
        self.assertIn(str(self.channel), log_message)

    @patch("odoo.addons.discuss_hub.models.mail_message_reaction._logger")
    def test_reaction_write_logs_error_on_exception(self, mock_logger):
        """Test that exception during reaction update logs error."""
        with patch(
            "odoo.addons.discuss_hub.models.models.DiscussHubConnector.outgo_reaction"
        ) as mock_outgo_reaction:
            # Create a reaction first
            reaction = self.env["mail.message.reaction"].create(
                {
                    "message_id": self.message.id,
                    "partner_id": self.partner.id,
                    "content": "👍",
                }
            )

            # Reset mock and make outgo_reaction raise an exception
            mock_logger.reset_mock()
            mock_outgo_reaction.side_effect = RuntimeError("Write error test")

            # Update the reaction - should succeed despite the error
            reaction.write({"content": "❤️"})

            # Verify reaction was updated
            self.assertEqual(reaction.content, "❤️")

            # Verify error log was called with exc_info=True
            self.assertTrue(mock_logger.error.called)
            log_message = mock_logger.error.call_args[0][0]
            self.assertIn(
                "Error sending outgoing reaction update to connector", log_message
            )
            self.assertIn("Write error test", log_message)
            # Check that exc_info=True was passed
            self.assertTrue(mock_logger.error.call_args[1].get("exc_info"))
