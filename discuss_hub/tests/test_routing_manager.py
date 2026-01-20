from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("discuss_hub", "routing_manager")
class TestBasePlugin(HttpCase):
    @classmethod
    def setUpClass(self):
        # add env on cls and many other things
        super().setUpClass()
        # create a connector
        self.connector = self.env["discuss_hub.connector"].create(
            {
                "name": "test_connector",
                "type": "base",
                "enabled": True,
                "uuid": "11111111-1111-1111-1111-111111111111",
                "url": "http://evolution:8080",
                "api_key": "1234567890",
            }
        )
        self.plugin = self.connector.get_plugin()

    def test_routing_manager_round_robin_strategy(self):
        """
        Test the round robin strategy of the routing manager
        """
        # Create a team 1 team with round robin strategy
        team = self.env["discuss_hub.routing_team"].create(
            {
                "name": "Test Team",
                "routing_strategy": "round_robin",
                "connector_id": self.connector.id,
                "online_users_only": False,
            }
        )
        # create 3 users
        users = self.env["res.users"].create(
            [
                {"name": f"User {i}", "login": f"user{i}", "active": True}
                for i in range(1, 4)
            ]
        )
        # add users to the team
        first_partner = users[0].partner_id
        self.env["discuss_hub.routing_team_member"].create(
            {
                "team_id": team.id,
                "user_id": users[0].id,
                "count": 0,
                "order": 1,
            }
        )
        # add second user to team
        second_partner = users[1].partner_id
        self.env["discuss_hub.routing_team_member"].create(
            {
                "team_id": team.id,
                "user_id": users[1].id,
                "count": 0,
                "order": 2,
            }
        )
        # add third user to team
        third_partner = users[2].partner_id
        self.env["discuss_hub.routing_team_member"].create(
            {
                "team_id": team.id,
                "user_id": users[2].id,
                "count": 0,
                "order": 3,
            }
        )
        # first run, first user
        first_run = team.get_next_team_member()
        assert (
            first_run.partner_id.id == first_partner.id
        ), f"Expected {first_run.partner_id.id}, got {first_partner.id}"
        # second run, second user
        second_run = team.get_next_team_member()
        assert (
            second_run.partner_id.id == second_partner.id
        ), f"Expected {second_run.partner_id.id}, got {second_partner.id}"
        # third run, third user
        third_run = team.get_next_team_member()
        assert (
            third_run.partner_id.id == third_partner.id
        ), f"Expected {third_partner.partner_id.id}, got {third_run.id}"
        # fourth run, first user again
        fourth_run = team.get_next_team_member()
        assert (
            fourth_run.partner_id.id == first_partner.id
        ), f"Expected {first_partner.id}, got {fourth_run.id}"

    def test_routing_manager_random_strategy(self):
        """Test the random strategy of the routing manager."""
        # Create a team with random strategy
        team = self.env["discuss_hub.routing_team"].create(
            {
                "name": "Random Team",
                "routing_strategy": "random",
                "connector_id": self.connector.id,
                "online_users_only": False,
            }
        )

        # Create 3 users
        users = self.env["res.users"].create(
            [
                {"name": f"Random User {i}", "login": f"randomuser{i}", "active": True}
                for i in range(1, 4)
            ]
        )

        # Add users to the team
        for i, user in enumerate(users):
            self.env["discuss_hub.routing_team_member"].create(
                {
                    "team_id": team.id,
                    "user_id": user.id,
                    "count": 0,
                    "order": i + 1,
                }
            )

        # Get a random user - should be one of the users in the team
        random_user = team.get_next_team_member()
        self.assertIn(
            random_user.id,
            users.ids,
            f"Random user {random_user.id} should be in team users {users.ids}",
        )

    def test_routing_manager_available_users_online_only(self):
        """Test that only online users are returned when online_users_only is True."""
        # Create a team with online_users_only=True
        team = self.env["discuss_hub.routing_team"].create(
            {
                "name": "Online Only Team",
                "routing_strategy": "round_robin",
                "connector_id": self.connector.id,
                "online_users_only": True,
            }
        )

        # Create users
        user1 = self.env["res.users"].create(
            {"name": "Online User", "login": "onlineuser", "active": True}
        )
        user2 = self.env["res.users"].create(
            {"name": "Offline User", "login": "offlineuser", "active": True}
        )

        # Set online status
        user1.partner_id.im_status = "online"
        user2.partner_id.im_status = "offline"

        # Add users to the team
        self.env["discuss_hub.routing_team_member"].create(
            [
                {"team_id": team.id, "user_id": user1.id, "count": 0, "order": 1},
                {"team_id": team.id, "user_id": user2.id, "count": 0, "order": 2},
            ]
        )

        # Get available users
        available = team.available_users()

        # Should only return online user
        self.assertIn(user1.id, available.ids)
        self.assertNotIn(user2.id, available.ids)

    def test_routing_manager_available_users_all(self):
        """Test that all active users are returned when online_users_only is False."""
        # Create a team with online_users_only=False
        team = self.env["discuss_hub.routing_team"].create(
            {
                "name": "All Users Team",
                "routing_strategy": "round_robin",
                "connector_id": self.connector.id,
                "online_users_only": False,
            }
        )

        # Create users
        user1 = self.env["res.users"].create(
            {"name": "User 1", "login": "alluser1", "active": True}
        )
        user2 = self.env["res.users"].create(
            {"name": "User 2", "login": "alluser2", "active": True}
        )

        # Set different online statuses
        user1.partner_id.im_status = "online"
        user2.partner_id.im_status = "offline"

        # Add users to the team
        self.env["discuss_hub.routing_team_member"].create(
            [
                {"team_id": team.id, "user_id": user1.id, "count": 0, "order": 1},
                {"team_id": team.id, "user_id": user2.id, "count": 0, "order": 2},
            ]
        )

        # Get available users
        available = team.available_users()

        # Should return both users
        self.assertIn(user1.id, available.ids)
        self.assertIn(user2.id, available.ids)

    def test_routing_manager_reset_team_member_counts(self):
        """Test resetting team member counts."""
        # Create a team
        team = self.env["discuss_hub.routing_team"].create(
            {
                "name": "Reset Team",
                "routing_strategy": "round_robin",
                "connector_id": self.connector.id,
                "online_users_only": False,
            }
        )

        # Create users and team members with counts
        users = self.env["res.users"].create(
            [
                {"name": f"Reset User {i}", "login": f"resetuser{i}", "active": True}
                for i in range(1, 4)
            ]
        )

        members = self.env["discuss_hub.routing_team_member"].create(
            [
                {
                    "team_id": team.id,
                    "user_id": user.id,
                    "count": 5,
                    "order": i + 1,
                }
                for i, user in enumerate(users)
            ]
        )

        # Verify counts are set
        for member in members:
            self.assertEqual(member.count, 5)

        # Reset counts
        team.reset_team_member_counts()

        # Verify all counts are 0
        for member in members:
            self.assertEqual(member.count, 0)

    def test_routing_manager_round_robin_no_available_users(self):
        """Test round robin returns None when no users are available."""
        # Create a team with online_users_only=True
        team = self.env["discuss_hub.routing_team"].create(
            {
                "name": "No Users Team",
                "routing_strategy": "round_robin",
                "connector_id": self.connector.id,
                "online_users_only": True,
            }
        )

        # Create offline user
        user = self.env["res.users"].create(
            {"name": "Offline User", "login": "offlineonly", "active": True}
        )
        user.partner_id.im_status = "offline"

        # Add user to team
        self.env["discuss_hub.routing_team_member"].create(
            {"team_id": team.id, "user_id": user.id, "count": 0, "order": 1}
        )

        # Get next team member - should be None
        next_member = team.get_next_team_member()
        self.assertIsNone(next_member)

    def test_routing_manager_random_no_available_users(self):
        """Test random returns None when no users are available."""
        # Create a team with online_users_only=True
        team = self.env["discuss_hub.routing_team"].create(
            {
                "name": "No Random Users Team",
                "routing_strategy": "random",
                "connector_id": self.connector.id,
                "online_users_only": True,
            }
        )

        # Create offline user
        user = self.env["res.users"].create(
            {"name": "Offline User", "login": "randomoffline", "active": True}
        )
        user.partner_id.im_status = "offline"

        # Add user to team
        self.env["discuss_hub.routing_team_member"].create(
            {"team_id": team.id, "user_id": user.id, "count": 0, "order": 1}
        )

        # Get next team member - should be None
        next_member = team.get_next_team_member()
        self.assertIsNone(next_member)

    def test_routing_manager_action_forward_with_agent(self):
        """Test forwarding a channel to a specific agent."""
        # Create an agent user
        agent_user = self.env["res.users"].create(
            {"name": "Agent User", "login": "agentuser", "active": True}
        )

        # Create a channel
        channel = self.env["discuss.channel"].create(
            {
                "name": "Test Channel",
                "channel_type": "channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        # Add current user as member
        channel.add_members([self.env.user.partner_id.id])

        # Create routing manager wizard
        wizard = self.env["discuss_hub.routing_manager"].create(
            {
                "channel_ids": [(6, 0, [channel.id])],
                "agent": agent_user.id,
            }
        )

        # Execute forward action
        result = wizard.action_forward()

        # Verify agent was added to channel
        member_ids = channel.channel_member_ids.mapped("partner_id.id")
        self.assertIn(
            agent_user.partner_id.id,
            member_ids,
            "Agent should be added as channel member",
        )

        # Verify action returned close window
        self.assertEqual(result.get("type"), "ir.actions.act_window_close")

    def test_routing_manager_action_forward_with_team(self):
        """Test forwarding a channel to a team using round robin strategy."""
        # Create a routing team
        team = self.env["discuss_hub.routing_team"].create(
            {
                "name": "Forward Team",
                "routing_strategy": "round_robin",
                "connector_id": self.connector.id,
                "online_users_only": False,
            }
        )

        # Create team members
        users = self.env["res.users"].create(
            [
                {
                    "name": f"Team Member {i}",
                    "login": f"teammember{i}",
                    "active": True,
                }
                for i in range(1, 3)
            ]
        )

        # Add users to team
        for i, user in enumerate(users):
            self.env["discuss_hub.routing_team_member"].create(
                {
                    "team_id": team.id,
                    "user_id": user.id,
                    "count": 0,
                    "order": i + 1,
                }
            )

        # Create a channel
        channel = self.env["discuss.channel"].create(
            {
                "name": "Team Channel",
                "channel_type": "channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        # Add current user as member
        channel.add_members([self.env.user.partner_id.id])

        # Create routing manager wizard with team
        wizard = self.env["discuss_hub.routing_manager"].create(
            {
                "channel_ids": [(6, 0, [channel.id])],
                "team": team.id,
            }
        )

        # Execute forward action
        result = wizard.action_forward()

        # Verify first team member was added to channel
        member_ids = channel.channel_member_ids.mapped("partner_id.id")
        self.assertIn(
            users[0].partner_id.id,
            member_ids,
            "First team member should be added as channel member",
        )

        # Verify action returned close window
        self.assertEqual(result.get("type"), "ir.actions.act_window_close")

    def test_routing_manager_action_forward_with_note(self):
        """Test forwarding a channel with a note message."""
        # Create an agent user
        agent_user = self.env["res.users"].create(
            {"name": "Agent With Note", "login": "agentnote", "active": True}
        )

        # Create a channel
        channel = self.env["discuss.channel"].create(
            {
                "name": "Note Channel",
                "channel_type": "channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        # Add current user as member
        channel.add_members([self.env.user.partner_id.id])

        # Create routing manager wizard with note
        note_text = "This is an important context note for the agent"
        wizard = self.env["discuss_hub.routing_manager"].create(
            {
                "channel_ids": [(6, 0, [channel.id])],
                "agent": agent_user.id,
                "note": note_text,
            }
        )

        # Execute forward action
        result = wizard.action_forward()

        # Verify note was posted as notification
        messages = channel.message_ids.filtered(
            lambda m: m.message_type == "notification"
        )
        self.assertTrue(messages, "A notification message should be posted")
        self.assertIn(
            note_text,
            messages[0].body,
            "Note text should be in the message body",
        )

        # Verify action returned close window
        self.assertEqual(result.get("type"), "ir.actions.act_window_close")

    def test_routing_manager_constraint_agent_or_team_required(self):
        """Test ValidationError when neither agent nor team is selected."""
        # Create a channel
        channel = self.env["discuss.channel"].create(
            {
                "name": "Constraint Channel",
                "channel_type": "channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        # Create wizard first (fields are optional initially)
        wizard = self.env["discuss_hub.routing_manager"].create(
            {
                "channel_ids": [(6, 0, [channel.id])],
            }
        )

        # Try to call action_forward without agent or team - should fail at constraint
        # But constraint only checks on write/create with values
        # Let's verify the constraint works by writing False values
        with self.assertRaises(
            ValidationError, msg="Should raise ValidationError when no agent/team"
        ):
            wizard.write({"agent": False, "team": False})

    def test_archive_manager_action_archive(self):
        """Test archiving a channel with a close message."""
        # Create a channel
        channel = self.env["discuss.channel"].create(
            {
                "name": "Archive Channel",
                "channel_type": "channel",
                "discuss_hub_connector": self.connector.id,
            }
        )

        # Add current user as member
        channel.add_members([self.env.user.partner_id.id])

        # Verify channel is active
        self.assertTrue(channel.active, "Channel should be active initially")

        # Create archive manager wizard
        close_msg = "Thank you for contacting us. This conversation is now closed."
        wizard = self.env["discuss_hub.archive_manager"].create(
            {
                "channel_ids": [(6, 0, [channel.id])],
                "close_message": close_msg,
                "send_close_message": True,
            }
        )

        # Execute archive action
        result = wizard.action_archive()

        # Verify close message was posted
        messages = channel.message_ids.filtered(lambda m: m.message_type == "comment")
        self.assertTrue(messages, "A comment message should be posted")
        self.assertIn(close_msg, messages[0].body, "Close message should be posted")

        # Verify channel was archived
        self.assertFalse(channel.active, "Channel should be archived")

        # Verify action returned close window
        self.assertEqual(result.get("type"), "ir.actions.act_window_close")
