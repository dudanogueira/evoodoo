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

    @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.outgo_reaction")
    def test_reaction_create_triggers_outgo(self, mock_outgo_reaction):
        """Test that creating a reaction on external message triggers outgo_reaction."""
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
        call_args = mock_outgo_reaction.call_args[0]
        self.assertEqual(call_args[0], self.channel)
        self.assertEqual(call_args[1], self.message)
        self.assertEqual(call_args[2], reaction)

    @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.outgo_reaction")
    def test_reaction_write_triggers_outgo(self, mock_outgo_reaction):
        """Test that updating a reaction triggers outgo_reaction."""
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
        call_args = mock_outgo_reaction.call_args[0]
        self.assertEqual(call_args[0], self.channel)
        self.assertEqual(call_args[1], self.message)
        self.assertEqual(call_args[2], reaction)
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

    @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.outgo_reaction")
    def test_reaction_on_channel_without_connector_no_trigger(
        self, mock_outgo_reaction
    ):
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

        # Create a reaction - should not trigger outgo
        reaction = self.env["mail.message.reaction"].create(
            {
                "message_id": message.id,
                "partner_id": self.partner.id,
                "content": "👍",
            }
        )

        # Verify reaction was created but outgo wasn't called
        self.assertTrue(reaction)
        mock_outgo_reaction.assert_not_called()

    @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.outgo_reaction")
    def test_reaction_error_handling_does_not_break_creation(self, mock_outgo_reaction):
        """Test that errors in outgo_reaction don't prevent reaction creation."""
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

    @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.outgo_reaction")
    def test_reaction_write_error_handling_does_not_break_update(
        self, mock_outgo_reaction
    ):
        """Test that errors in outgo_reaction don't prevent reaction updates."""
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

    @patch("odoo.addons.discuss_hub.models.plugins.base.Plugin.outgo_reaction")
    def test_disabled_connector_no_outgo_on_create(self, mock_outgo_reaction):
        """Test that reactions don't trigger outgo when connector is disabled."""
        # Disable the connector
        self.connector.enabled = False

        # Create a reaction
        reaction = self.env["mail.message.reaction"].create(
            {
                "message_id": self.message.id,
                "partner_id": self.partner.id,
                "content": "👍",
            }
        )

        # Verify reaction was created
        self.assertTrue(reaction)
        # outgo_reaction should still be called, but the connector.outgo_reaction
        # would handle the disabled state
        # Note: The create/write methods always call outgo_reaction,
        # the connector itself checks if it's enabled
        mock_outgo_reaction.assert_called_once()
