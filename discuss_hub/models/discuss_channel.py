import logging

from odoo import api, fields, models
from odoo.tools import config

_logger = logging.getLogger(__name__)


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

    @api.returns("mail.message", lambda value: value.id)
    def message_post(self, **kwargs):
        """
        Override message_post to handle outgoing messages to external connectors.
        This replaces the base automation for outgoing messages.

        Only sends messages to external platforms when:
        - Channel has a discuss_hub_connector
        - Message was created successfully
        - Message author is a partner with a system user (internal user)
        """
        # Call the parent method first to create the message
        message = super().message_post(**kwargs)

        # Handle outgoing message to connector (replaces base automation)
        # Only send if message is from a partner with a system user (not external/bot)
        if self.discuss_hub_connector and message:
            # Check if message author has a system user
            has_system_user = False
            if message.author_id:
                has_system_user = bool(
                    self.env["res.users"].search(
                        [("partner_id", "=", message.author_id.id)], limit=1
                    )
                )

            if has_system_user:
                try:
                    _logger.info(
                        f"discuss_channel.message_post: sending outgoing message "
                        f"({message}) from user {message.author_id.name} to {self}"
                    )
                    self.discuss_hub_connector.outgo_message(
                        channel=self, message=message
                    )
                except Exception as e:
                    _logger.error(
                        f"Error sending outgoing message to connector: {e}",
                        exc_info=True,
                    )
            else:
                _logger.debug(
                    f"discuss_channel.message_post: skipping outgoing message "
                    f"({message}) - author "
                    f"{message.author_id.name if message.author_id else 'N/A'} "
                    f"has no system user"
                )

        return message

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        """
        Override _notify_thread to handle bot automation for incoming messages.
        This replaces the base automation for bot outgoing.

        Only processes bot automation when:
        - Message author is NOT a bot (does not have a system user)
        - This prevents infinite loops where bot responses trigger the bot again

        Bot processing is done with auto-commit to ensure the incoming message
        is saved and visible before the bot processes it.
        """
        # Call parent method
        result = super()._notify_thread(message, msg_vals=msg_vals, **kwargs)

        # Skip bot processing if explicitly disabled in context
        if self.env.context.get("discuss_hub_skip_bot"):
            return result

        # Check if message author is a bot/system user
        # If author has a system user, skip bot processing to avoid loops
        is_system_user = False
        if message.author_id:
            is_system_user = bool(
                self.env["res.users"].search(
                    [("partner_id", "=", message.author_id.id)], limit=1
                )
            )

        # Only process bot automation for messages from external users (no system user)
        if not is_system_user:
            # Handle bot automation (replaces base automation)
            # Check if channel has partners with bots
            partners_with_bot = self.channel_partner_ids.filtered(lambda p: p.bot)
            if partners_with_bot:
                try:
                    _logger.info(
                        f"discuss_channel._notify_thread: processing bot for "
                        f"{len(partners_with_bot)} partners"
                    )

                    # Commit the transaction to ensure message is visible immediately
                    # This allows the user to see their message before bot responds
                    # Skip commit during tests (will raise AssertionError in test mode)
                    # pylint: disable=invalid-commit
                    if not config.get("test_enable"):
                        self.env.cr.commit()

                    # Process bot in a new cursor context
                    for partner in partners_with_bot:
                        partner.bot.outgo(self, partner)

                except Exception as e:
                    _logger.error(
                        f"Error processing bot automation: {e}", exc_info=True
                    )
        else:
            _logger.debug(
                f"discuss_channel._notify_thread: skipping bot processing "
                f"- message from system user {message.author_id.name}"
            )

        return result
