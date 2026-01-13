import logging
import random

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class DiscussHubRoutingTeam(models.Model):
    _name = "discuss_hub.routing_team"
    _description = "Discuss Hub Routing Team"

    name = fields.Char(
        required=True,
        help="Name of the team to be used for routing.",
    )
    active = fields.Boolean(
        default=True,
        help="Indicates whether the routing team is active.",
    )
    # TODO: not sure if this is needed
    connector_id = fields.Many2one(
        comodel_name="discuss_hub.connector",
        required=False,
        help="Select the connector to use for routing.",
    )
    routing_strategy = fields.Selection(
        selection=[
            # ("least_busy", "Least Busy"),
            ("round_robin", "Round Robin"),
            ("random", "random"),
        ],
        required=True,
        default="round_robin",
        help="Select the routing strategy to be used.",
    )
    online_users_only = fields.Boolean(
        help="Limit the routing strategy to online users only", default=True
    )
    team_member_ids = fields.One2many(
        comodel_name="discuss_hub.routing_team_member",
        inverse_name="team_id",
        string="Team Members",
        help="Users that are part of this routing team.",
    )

    def available_users(self):
        """Returns a list of users that are part of the team and online"""
        self.ensure_one()
        users = self.team_member_ids.mapped("user_id")
        # get only active users
        users = self.env["res.users"].search(
            [
                ("id", "in", users.ids),
                ("active", "=", True),
            ]
        )
        if self.online_users_only:
            users = users.filtered(lambda u: u.partner_id.im_status == "online")
        _logger.info(
            f"Available users in team {self.name}: {[user.name for user in users]}"
        )
        return users

    def reset_team_member_counts(self):
        """Reset all counts from team members"""
        self.ensure_one()
        for member in self.team_member_ids:
            member.count = 0
        return True

    def get_next_team_member(self, connector=None):
        """Returns the next team member based on the routing strategy"""
        self.ensure_one()
        if self.routing_strategy == "least_busy":
            return self._get_least_busy_user(connector=connector)
        elif self.routing_strategy == "round_robin":
            return self._get_round_robin_user()
        elif self.routing_strategy == "random":
            return self._get_random_user()
        else:
            return None

    def _get_round_robin_user(self):
        # get the team members ordered by their order field
        # and ordered by their count field
        """Returns the next user in the team based on round robin strategy"""
        self.ensure_one()
        users = self.available_users()
        if not users:
            return None
        # get team members based on available users nd ordered
        next_team_member = self.env["discuss_hub.routing_team_member"].search(
            [("team_id", "=", self.id), ("user_id", "in", users.ids)],
            order="count asc, order asc",
            limit=1,
        )
        # increase the count of the team member
        if not next_team_member:
            return None
        # increment the team member count
        next_team_member.write({"count": next_team_member.count + 1})
        return next_team_member.user_id

    def _get_random_user(self):
        """Returns a random user from the team"""
        self.ensure_one()
        users = self.available_users()
        random_user = random.choice(users) if users else None
        if not users:
            return None
        return random_user

    def _get_least_busy_user(self, connector=None):
        """Returns the user in the team with the fewest active chats."""
        self.ensure_one()
        users = self.available_users()
        if not users:
            return None
        if connector:
            channel_filter = ("channel_id.connector_id", "=", connector.id)
        else:
            # if no channel is provided, consider all channels (global)
            channel_filter = ("channel_id.discuss_hub_connector", "!=", False)
        grouped_data = self.env["discuss.channel.member"].read_group(
            domain=[
                ("partner_id.user_ids", "in", users.ids),
                ("channel_id.discuss_hub_connector", "!=", False),
                ("channel_id.active", "=", True),
                # consider only from same channel
                channel_filter,
            ],
            fields=["partner_id", "create_date:max"],
            groupby=["partner_id"],
            orderby="create_date desc",
            limit=1,
        )
        if grouped_data:
            return grouped_data[0].get("partner_id")
        else:
            return None


class DiscussHubRoutingTeamMember(models.Model):
    _name = "discuss_hub.routing_team_member"
    _description = "Discuss Hub Routing Team Member"

    team_id = fields.Many2one(
        comodel_name="discuss_hub.routing_team",
        required=True,
        help="Select the team to which the user belongs.",
    )

    user_id = fields.Many2one(
        comodel_name="res.users",
        required=True,
        help="Select the user to be added to the team.",
        domain="[('partner_id', '!=', False)]",
    )
    order = fields.Integer(
        help="Order of the user in the team.",
    )
    count = fields.Integer(
        help="Number of active chats for the user.",
    )


# TRANSIENT MODEL TO FORWARD CHANNELS


class DiscussHubRoutingManager(models.TransientModel):
    _name = "discuss_hub.routing_manager"
    _description = "Discuss Hub Routing Manager"

    channel_ids = fields.Many2many(
        comodel_name="discuss.channel",
        string="Channels",
        readonly=True,
    )

    agent = fields.Many2one(
        comodel_name="res.users",
        required=False,
        help="Select the agent to forward the channel to.",
        domain="[('partner_id', '!=', False)]",
    )

    team = fields.Many2one(
        comodel_name="discuss_hub.routing_team",
        required=False,
        help="Select the team to which the agent belongs.",
        domain="[('active', '=', True)]",
    )

    note = fields.Text(help="Add a note for context when forwarding the channel.")

    @api.constrains("agent", "team")
    def _check_agent_or_team_selected(self):
        for record in self:
            if not record.agent and not record.team:
                raise ValidationError(_("You must select either an agent or a team."))

    def action_forward(self, from_partner=None):
        """Forward the channel to the selected agent"""

        self.ensure_one()  # Only one wizard record should be active

        selected_agent = self.agent.partner_id
        selected_team = self.team
        selected_note = self.note
        selected_actor = None
        user = self.env.user
        if from_partner and from_partner.user_ids:
            user = from_partner.user_ids[0]
        for channel in self.channel_ids:
            if selected_agent:
                selected_actor = selected_agent
                channel.with_user(user).add_members([selected_actor.id])
            if selected_team:
                selected_member = selected_team.get_next_team_member(
                    connector=channel.discuss_hub_connector
                )
                if selected_member:
                    selected_actor = selected_member.partner_id

                    # add the member as user
                    channel.with_user(user).add_members([selected_actor.id])
            # add note
            if selected_note and selected_actor:
                # run with sudo
                channel.sudo().message_post(
                    author_id=from_partner.id if from_partner else None,
                    body=selected_note,
                    message_type="notification",
                    partner_ids=[selected_actor.id],
                )
            # close the UI
            channel_member = self.env["discuss.channel.member"].search(
                [
                    ("partner_id", "=", self.env.user.partner_id.id),
                    ("channel_id", "=", channel.id),
                ],
                limit=1,
            )
            if channel_member:
                # In Odoo 19, unpinning is controlled by unpin_dt
                channel_member.write({"unpin_dt": fields.Datetime.now()})
            # leave the channel
            channel.with_user(user).action_unfollow()

        return {"type": "ir.actions.act_window_close"}

    @api.model
    def get_teams_and_users_status(self):
        """Returns CRM teams with users and their online status"""
        teams_data = []
        teams = self.env["crm.team"].search([])
        for team in teams:
            users_info = []
            for user in team.member_ids:
                users_info.append(
                    {
                        "user_id": user.id,
                        "name": user.name,
                        "online": user.partner_id.im_status == "online",
                    }
                )
            teams_data.append(
                {"team_id": team.id, "team_name": team.name, "users": users_info}
            )
        return teams_data

    @api.model
    def find_least_busy_user(self, team_id):
        """Returns the user in the team with the fewest active chats"""
        team = self.env["crm.team"].browse(team_id)
        if not team:
            return None

        min_user = None
        min_chats = float("inf")

        for user in team.member_ids:
            active_channels = self.env["mail.channel.partner"].search_count(
                [
                    ("partner_id", "=", user.partner_id.id),
                    ("channel_id.channel_type", "=", "chat"),
                    ("is_pinned", "=", True),
                ]
            )
            if active_channels < min_chats:
                min_user = user
                min_chats = active_channels

        if min_user:
            return {
                "user_id": min_user.id,
                "name": min_user.name,
                "active_chats": min_chats,
            }
        return None


class DiscussHubArchiveManager(models.TransientModel):
    _name = "discuss_hub.archive_manager"
    _description = "Discuss Hub Archive Manager"

    channel_ids = fields.Many2many(
        comodel_name="discuss.channel",
        string="Channels",
        readonly=True,
    )

    close_message = fields.Text(
        help="Message to be sent when archiving the channel.",
    )
    send_close_message = fields.Boolean(
        help="Send the close message when archiving the channel.",
        default=True,
    )

    def action_archive(self):
        self.ensure_one()  # Only one wizard record should be active
        for channel in self.channel_ids:
            channel_member = self.env["discuss.channel.member"].search(
                [
                    ("partner_id", "=", self.env.user.partner_id.id),
                    ("channel_id", "=", channel.id),
                ],
                limit=1,
            )

            if self.send_close_message and self.close_message:
                channel.message_post(
                    author_id=self.env.user.partner_id.id,
                    body=self.close_message,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
            # In Odoo 19, unpinning is controlled by unpin_dt
            channel_member.write({"unpin_dt": fields.Datetime.now()})
            # TODO: add internal note as option
            # TODO: add tags
            # TODO: close to all members
            channel.action_unfollow()
            channel.action_archive()

        return {"type": "ir.actions.act_window_close"}
