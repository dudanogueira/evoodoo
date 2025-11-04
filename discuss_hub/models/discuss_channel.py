from odoo import api, fields, models


class DiscussChannel(models.Model):
    """Chat Session
    Reprensenting a conversation between users.
    It extends the base method for anonymous usage.
    """

    _inherit = ["discuss.channel"]

    discuss_hub_connector = fields.Many2one(
        comodel_name="discuss_hub.connector",
        string="Connector",
        index="btree_not_null",
        auto_join=True,
        ondelete="set null",
    )
    discuss_hub_outgoing_destination = fields.Char(
        string="Discuss Hub Outgoing Destination for this channel"
    )
    is_current_user_member = fields.Boolean(
        compute="_compute_is_current_user_member",
        store=False,
    )

    @api.depends("channel_partner_ids")
    def _compute_is_current_user_member(self):
        """Check if current user is a member of this channel"""
        for channel in self:
            channel.is_current_user_member = (
                self.env.user.partner_id in channel.channel_partner_ids
            )

    def action_join_channel(self):
        """Join the current user to the channel"""
        self.ensure_one()
        if not self.is_current_user_member:
            self.add_members([self.env.user.partner_id.id])
        # Reload the kanban view to update button visibility
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def action_join_and_open_channel(self):
        """Join the current user to the channel and open it"""
        self.ensure_one()
        if not self.is_current_user_member:
            self.add_members([self.env.user.partner_id.id], open_chat_window=True)
        return {
            "type": "ir.actions.client",
            "tag": "mail.action_discuss",
            "params": {
                "channel_id": self.id,
            },
        }

    def action_leave_channel(self):
        """Remove the current user from the channel"""
        self.ensure_one()
        if self.is_current_user_member:
            self.action_unfollow()
        # Reload the kanban view to update button visibility
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def action_remove_member(self, partner_id):
        """Remove a specific partner from the channel"""
        self.ensure_one()
        partner = self.env["res.partner"].browse(partner_id)
        if partner in self.channel_partner_ids:
            # Use channel's remove_members method if available, otherwise unfollow
            member = self.env["discuss.channel.member"].search(
                [("channel_id", "=", self.id), ("partner_id", "=", partner_id)], limit=1
            )
            if member:
                member.unlink()
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_open_forward_wizard(self):
        """Open the forward/routing wizard"""
        self.ensure_one()
        return {
            "name": "Forward",
            "type": "ir.actions.act_window",
            "res_model": "discuss_hub.routing_manager",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {
                "default_channel_ids": [self.id],
            },
        }

    def action_open_archive_wizard(self):
        """Open the archive/close wizard"""
        self.ensure_one()
        return {
            "name": "Archive",
            "type": "ir.actions.act_window",
            "res_model": "discuss_hub.archive_manager",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {
                "default_channel_ids": [self.id],
            },
        }
