"""Tests for discuss.channel model extensions."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("discuss_hub", "discuss_channel")
class TestDiscussChannel(TransactionCase):
    """Test suite for discuss.channel integration with discuss_hub."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a test connector
        cls.connector = cls.env["discuss_hub.connector"].create(
            {
                "name": "Test Connector",
                "type": "base",
                "enabled": True,
                "uuid": "test-channel-uuid",
            }
        )

        # Create test users
        cls.user1 = cls.env["res.users"].create(
            {
                "name": "Test User 1",
                "login": "testuser1",
                "email": "testuser1@example.com",
            }
        )
        cls.user2 = cls.env["res.users"].create(
            {
                "name": "Test User 2",
                "login": "testuser2",
                "email": "testuser2@example.com",
            }
        )

        # Create a test channel
        cls.channel = cls.env["discuss.channel"].create(
            {
                "name": "Test Channel",
                "discuss_hub_connector": cls.connector.id,
            }
        )

    def test_compute_is_current_user_member_true(self):
        """Test that is_current_user_member is True when user is a member."""
        # Add current user to channel
        self.channel.add_members([self.env.user.partner_id.id])

        # Trigger compute
        self.channel._compute_is_current_user_member()

        # Verify
        self.assertTrue(self.channel.is_current_user_member)

    def test_compute_is_current_user_member_false(self):
        """Test that is_current_user_member is False when user is not a member."""
        # Ensure current user is not a member
        member = self.env["discuss.channel.member"].search(
            [
                ("channel_id", "=", self.channel.id),
                ("partner_id", "=", self.env.user.partner_id.id),
            ]
        )
        if member:
            member.unlink()

        # Trigger compute
        self.channel._compute_is_current_user_member()

        # Verify
        self.assertFalse(self.channel.is_current_user_member)

    def test_action_join_channel(self):
        """Test joining a channel."""
        # Ensure user is not a member
        member = self.env["discuss.channel.member"].search(
            [
                ("channel_id", "=", self.channel.id),
                ("partner_id", "=", self.env.user.partner_id.id),
            ]
        )
        if member:
            member.unlink()

        # Join the channel
        result = self.channel.action_join_channel()

        # Verify user is now a member
        self.assertTrue(
            self.env.user.partner_id in self.channel.channel_partner_ids,
            "Current user should be a member after joining",
        )

        # Verify return value
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "reload")

    def test_action_join_channel_already_member(self):
        """Test joining a channel when already a member."""
        # Add user as member
        self.channel.add_members([self.env.user.partner_id.id])

        # Try to join again
        result = self.channel.action_join_channel()

        # Verify still a member (no error)
        self.assertTrue(self.env.user.partner_id in self.channel.channel_partner_ids)

        # Verify return value
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "reload")

    def test_action_join_and_open_channel(self):
        """Test joining and opening a channel."""
        # Ensure user is not a member
        member = self.env["discuss.channel.member"].search(
            [
                ("channel_id", "=", self.channel.id),
                ("partner_id", "=", self.env.user.partner_id.id),
            ]
        )
        if member:
            member.unlink()

        # Join and open the channel
        result = self.channel.action_join_and_open_channel()

        # Verify user is now a member
        self.assertTrue(self.env.user.partner_id in self.channel.channel_partner_ids)

        # Verify return value
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "mail.action_discuss")
        self.assertEqual(result["params"]["channel_id"], self.channel.id)

    def test_action_leave_channel(self):
        """Test leaving a channel."""
        # Add user as member
        self.channel.add_members([self.env.user.partner_id.id])

        # Verify user is a member
        self.assertTrue(self.env.user.partner_id in self.channel.channel_partner_ids)

        # Leave the channel
        result = self.channel.action_leave_channel()

        # Verify user is no longer a member
        self.assertFalse(
            self.env.user.partner_id in self.channel.channel_partner_ids,
            "Current user should not be a member after leaving",
        )

        # Verify return value
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "reload")

    def test_action_leave_channel_not_member(self):
        """Test leaving a channel when not a member."""
        # Ensure user is not a member
        member = self.env["discuss.channel.member"].search(
            [
                ("channel_id", "=", self.channel.id),
                ("partner_id", "=", self.env.user.partner_id.id),
            ]
        )
        if member:
            member.unlink()

        # Try to leave
        result = self.channel.action_leave_channel()

        # Should not raise error
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "reload")

    def test_action_remove_member(self):
        """Test removing a specific member from a channel."""
        # Add user2 to the channel
        self.channel.add_members([self.user2.partner_id.id])

        # Verify user2 is a member
        self.assertTrue(self.user2.partner_id in self.channel.channel_partner_ids)

        # Remove user2
        result = self.channel.action_remove_member(self.user2.partner_id.id)

        # Verify user2 is no longer a member
        self.assertFalse(
            self.user2.partner_id in self.channel.channel_partner_ids,
            "User2 should not be a member after removal",
        )

        # Verify return value
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "reload")

    def test_action_remove_member_not_in_channel(self):
        """Test removing a member that is not in the channel."""
        # Ensure user2 is not a member
        member = self.env["discuss.channel.member"].search(
            [
                ("channel_id", "=", self.channel.id),
                ("partner_id", "=", self.user2.partner_id.id),
            ]
        )
        if member:
            member.unlink()

        # Try to remove user2
        result = self.channel.action_remove_member(self.user2.partner_id.id)

        # Should not raise error
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "reload")

    def test_action_open_forward_wizard(self):
        """Test opening the forward/routing wizard."""
        result = self.channel.action_open_forward_wizard()

        # Verify return value structure
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "discuss_hub.routing_manager")
        self.assertEqual(result["name"], "Forward")
