"""
Tests for res.partner model extensions.

Tests cover:
- _compute_discuss_hub_count for partners with channels
- _compute_discuss_hub_count with parent/child relationships
- action_view_channel method
- get_or_create_discuss_hub_channel method
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("discuss_hub", "res_partner")
class TestResPartnerDiscussHubCount(TransactionCase):
    """Test cases for discuss_hub_channel_count computation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create connector
        cls.connector = cls.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector",
                "type": "example",
                "enabled": True,
                "uuid": "test-connector-uuid-partner",
                "url": "http://test.example.com",
            }
        )

        # Create parent partner
        cls.parent_partner = cls.env["res.partner"].create(
            {
                "name": "Parent Company",
                "phone": "+5511988887777",
                "is_company": True,
            }
        )

        # Create child partner
        cls.child_partner = cls.env["res.partner"].create(
            {
                "name": "Child Contact",
                "phone": "+5511999999999",
                "parent_id": cls.parent_partner.id,
            }
        )

        # Create standalone partner
        cls.standalone_partner = cls.env["res.partner"].create(
            {
                "name": "Standalone Partner",
                "phone": "+5511977777777",
            }
        )

    def test_compute_count_no_channels(self):
        """Test partner with no channels has count of 0."""
        new_partner = self.env["res.partner"].create(
            {
                "name": "No Channels Partner",
                "phone": "+5511966666666",
            }
        )

        self.assertEqual(
            new_partner.discuss_hub_channel_count,
            0,
            "Partner with no channels should have count of 0",
        )

    def test_compute_count_single_channel(self):
        """Test partner with one channel has count of 1."""
        # Create channel with partner
        channel = self.env["discuss.channel"].create(
            {
                "name": "Test Channel 1",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": self.standalone_partner.phone,
            }
        )
        channel.channel_partner_ids = [(4, self.standalone_partner.id)]

        # Force recomputation
        self.standalone_partner.invalidate_recordset()

        self.assertEqual(
            self.standalone_partner.discuss_hub_channel_count,
            1,
            "Partner with one channel should have count of 1",
        )

    def test_compute_count_multiple_channels(self):
        """Test partner with multiple channels has correct count."""
        # Create multiple channels
        for i in range(3):
            channel = self.env["discuss.channel"].create(
                {
                    "name": f"Test Channel {i}",
                    "discuss_hub_connector": self.connector.id,
                    "discuss_hub_outgoing_destination": self.standalone_partner.phone,
                }
            )
            channel.channel_partner_ids = [(4, self.standalone_partner.id)]

        # Force recomputation
        self.standalone_partner.invalidate_recordset()

        self.assertEqual(
            self.standalone_partner.discuss_hub_channel_count,
            3,
            "Partner with three channels should have count of 3",
        )

    def test_compute_count_excludes_non_discuss_hub_channels(self):
        """Test that regular Odoo channels without connector are not counted."""
        # Create discuss_hub channel
        hub_channel = self.env["discuss.channel"].create(
            {
                "name": "Hub Channel",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": self.standalone_partner.phone,
            }
        )
        hub_channel.channel_partner_ids = [(4, self.standalone_partner.id)]

        # Create regular channel (no connector)
        regular_channel = self.env["discuss.channel"].create(
            {
                "name": "Regular Channel",
            }
        )
        regular_channel.channel_partner_ids = [(4, self.standalone_partner.id)]

        # Force recomputation
        self.standalone_partner.invalidate_recordset()

        self.assertEqual(
            self.standalone_partner.discuss_hub_channel_count,
            1,
            "Only channels with discuss_hub_connector should be counted",
        )

    def test_compute_count_includes_parent_channels(self):
        """Test child partner count includes parent's channels."""
        # Create channel for parent
        parent_channel = self.env["discuss.channel"].create(
            {
                "name": "Parent Channel",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": self.parent_partner.phone,
            }
        )
        parent_channel.channel_partner_ids = [(4, self.parent_partner.id)]

        # Force recomputation
        self.child_partner.invalidate_recordset()

        self.assertGreaterEqual(
            self.child_partner.discuss_hub_channel_count,
            1,
            "Child partner should include parent's channels in count",
        )

    def test_compute_count_includes_child_channels(self):
        """Test parent partner count includes child's channels."""
        # Create channel for child
        child_channel = self.env["discuss.channel"].create(
            {
                "name": "Child Channel",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": self.child_partner.phone,
            }
        )
        child_channel.channel_partner_ids = [(4, self.child_partner.id)]

        # Force recomputation
        self.parent_partner.invalidate_recordset()

        self.assertGreaterEqual(
            self.parent_partner.discuss_hub_channel_count,
            1,
            "Parent partner should include child's channels in count",
        )

    def test_compute_count_parent_and_child_channels(self):
        """Test count includes both parent and child channels."""
        # Create channel for parent
        parent_channel = self.env["discuss.channel"].create(
            {
                "name": "Parent Channel",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": self.parent_partner.phone,
            }
        )
        parent_channel.channel_partner_ids = [(4, self.parent_partner.id)]

        # Create channel for child
        child_channel = self.env["discuss.channel"].create(
            {
                "name": "Child Channel",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": self.child_partner.phone,
            }
        )
        child_channel.channel_partner_ids = [(4, self.child_partner.id)]

        # Force recomputation
        self.child_partner.invalidate_recordset()
        self.parent_partner.invalidate_recordset()

        # Both should see both channels
        self.assertGreaterEqual(
            self.child_partner.discuss_hub_channel_count,
            2,
            "Child should see both parent and own channels",
        )
        self.assertGreaterEqual(
            self.parent_partner.discuss_hub_channel_count,
            2,
            "Parent should see both own and child channels",
        )

    def test_compute_count_with_inactive_channels(self):
        """Test that inactive channels are included in count."""
        # Create active channel
        active_channel = self.env["discuss.channel"].create(
            {
                "name": "Active Channel",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": self.standalone_partner.phone,
                "active": True,
            }
        )
        active_channel.channel_partner_ids = [(4, self.standalone_partner.id)]

        # Create inactive channel
        inactive_channel = self.env["discuss.channel"].create(
            {
                "name": "Inactive Channel",
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": self.standalone_partner.phone,
                "active": False,
            }
        )
        inactive_channel.channel_partner_ids = [(4, self.standalone_partner.id)]

        # Force recomputation
        self.standalone_partner.invalidate_recordset()

        # Both active and inactive should be counted (active_test=False in compute)
        self.assertEqual(
            self.standalone_partner.discuss_hub_channel_count,
            2,
            "Count should include both active and inactive channels",
        )


@tagged("discuss_hub", "res_partner", "action")
class TestResPartnerActions(TransactionCase):
    """Test cases for res.partner action methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create connector
        cls.connector = cls.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector",
                "type": "example",
                "enabled": True,
                "uuid": "test-connector-actions",
                "url": "http://test.example.com",
            }
        )

        # Create parent and child partners
        cls.parent_partner = cls.env["res.partner"].create(
            {
                "name": "Parent Company",
                "phone": "+5511988887777",
            }
        )

        cls.child_partner = cls.env["res.partner"].create(
            {
                "name": "Child Contact",
                "phone": "+5511999999999",
                "parent_id": cls.parent_partner.id,
            }
        )

        # Create standalone partner
        cls.standalone_partner = cls.env["res.partner"].create(
            {
                "name": "Standalone Partner",
                "phone": "+5511977777777",
            }
        )

    def test_action_view_channel_standalone_partner(self):
        """Test action_view_channel for standalone partner."""
        # Create channel
        channel = self.env["discuss.channel"].create(
            {
                "name": "Test Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )
        channel.channel_partner_ids = [(4, self.standalone_partner.id)]

        # Call action
        action = self.standalone_partner.action_view_channel()

        # Assertions
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertIn("domain", action)
        self.assertEqual(
            action["domain"],
            [("channel_partner_ids.id", "=", self.standalone_partner.id)],
        )

    def test_action_view_channel_child_partner(self):
        """Test action_view_channel for child partner includes parent."""
        # Create channels for both parent and child
        parent_channel = self.env["discuss.channel"].create(
            {
                "name": "Parent Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )
        parent_channel.channel_partner_ids = [(4, self.parent_partner.id)]

        child_channel = self.env["discuss.channel"].create(
            {
                "name": "Child Channel",
                "discuss_hub_connector": self.connector.id,
            }
        )
        child_channel.channel_partner_ids = [(4, self.child_partner.id)]

        # Call action on child
        action = self.child_partner.action_view_channel()

        # Assertions
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertIn("domain", action)

        # Domain should include OR condition for both child and parent
        expected_domain = [
            "|",
            ("channel_partner_ids.id", "=", self.child_partner.id),
            ("channel_partner_ids.id", "=", self.parent_partner.id),
        ]
        self.assertEqual(action["domain"], expected_domain)

    def test_get_or_create_discuss_hub_channel_existing_active(self):
        """Test get_or_create with existing active channel."""
        # Create active channel
        channel = self.env["discuss.channel"].create(
            {
                "name": "Existing Channel",
                "discuss_hub_connector": self.connector.id,
                "active": True,
            }
        )
        channel.channel_partner_ids = [(4, self.standalone_partner.id)]

        # Call method
        result = self.standalone_partner.get_or_create_discuss_hub_channel()

        # Should return action to open existing channel
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "mail.action_discuss")
        self.assertEqual(result["params"]["channel_id"], channel.id)

    def test_get_or_create_discuss_hub_channel_child_finds_parent_channel(self):
        """Test child partner can find parent's channel."""
        # Create channel for parent
        channel = self.env["discuss.channel"].create(
            {
                "name": "Parent Channel",
                "discuss_hub_connector": self.connector.id,
                "active": True,
            }
        )
        channel.channel_partner_ids = [(4, self.parent_partner.id)]

        # Call method on child
        result = self.child_partner.get_or_create_discuss_hub_channel()

        # Should return action to open parent's channel
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "mail.action_discuss")
        self.assertEqual(result["params"]["channel_id"], channel.id)

    def test_get_or_create_discuss_hub_channel_inactive_ignored(self):
        """Test that inactive channels are ignored."""
        # Create inactive channel
        inactive_channel = self.env["discuss.channel"].create(
            {
                "name": "Inactive Channel",
                "discuss_hub_connector": self.connector.id,
                "active": False,
            }
        )
        inactive_channel.channel_partner_ids = [(4, self.standalone_partner.id)]

        # Call method
        result = self.standalone_partner.get_or_create_discuss_hub_channel()

        # Should return None (no active channel found)
        self.assertIsNone(result)

    def test_get_or_create_discuss_hub_channel_returns_valid_channel(self):
        """Test that a valid active channel is returned when multiple exist."""
        # Create first channel
        channel1 = self.env["discuss.channel"].create(
            {
                "name": "Channel 1",
                "discuss_hub_connector": self.connector.id,
                "active": True,
            }
        )
        channel1.channel_partner_ids = [(4, self.standalone_partner.id)]

        # Create second channel
        channel2 = self.env["discuss.channel"].create(
            {
                "name": "Channel 2",
                "discuss_hub_connector": self.connector.id,
                "active": True,
            }
        )
        channel2.channel_partner_ids = [(4, self.standalone_partner.id)]

        # Call method
        result = self.standalone_partner.get_or_create_discuss_hub_channel()

        # Should return a valid action
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "mail.action_discuss")
        self.assertIn("channel_id", result["params"])

        # The returned channel should be one of the created channels
        returned_channel_id = result["params"]["channel_id"]
        self.assertIn(
            returned_channel_id,
            [channel1.id, channel2.id],
            "Should return one of the active channels with connector",
        )

        # Verify the returned channel is actually active
        returned_channel = self.env["discuss.channel"].browse(returned_channel_id)
        self.assertTrue(returned_channel.active)
        self.assertEqual(returned_channel.discuss_hub_connector, self.connector)


@tagged("discuss_hub", "res_partner", "bot")
class TestResPartnerBot(TransactionCase):
    """Test cases for res.partner bot relationship."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create bot manager
        cls.bot = cls.env["discuss_hub.bot_manager"].create(
            {
                "bot_type": "generic",
                "bot_url": "https://bot.example.com/webhook",
                "bot_api_key": "test_api_key",
                "active": True,
            }
        )

        # Create partner
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Partner with Bot",
                "phone": "+5511999999999",
            }
        )

    def test_partner_bot_assignment(self):
        """Test assigning bot to partner."""
        self.partner.bot = self.bot.id

        self.assertEqual(self.partner.bot, self.bot)
        self.assertIn(self.partner, self.bot.partner)

    def test_partner_bot_removal(self):
        """Test removing bot from partner."""
        self.partner.bot = self.bot.id
        self.assertEqual(self.partner.bot, self.bot)

        self.partner.bot = False
        self.assertFalse(self.partner.bot)

    def test_multiple_partners_same_bot(self):
        """Test multiple partners can share the same bot."""
        partner2 = self.env["res.partner"].create(
            {
                "name": "Another Partner",
                "phone": "+5511988888888",
            }
        )

        self.partner.bot = self.bot.id
        partner2.bot = self.bot.id

        self.assertEqual(self.partner.bot, self.bot)
        self.assertEqual(partner2.bot, self.bot)
        self.assertEqual(len(self.bot.partner), 2)
