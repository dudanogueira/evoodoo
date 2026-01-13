import logging

from odoo import api, fields, models
from odoo.tools import config

_logger = logging.getLogger(__name__)

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    """Chat Session
    Reprensenting a conversation between users.
    It extends the base method for anonymous usage.
    """

    _inherit = "discuss.channel"

    discuss_hub_connector = fields.Many2one(
        comodel_name="discuss_hub.connector",
        string="Connector",
        index="btree_not_null",
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

    def message_post(self, **kwargs):
        """
        Override message_post to handle outgoing messages to external connectors.
        This replaces the base automation for outgoing messages.

        Only sends messages to external platforms when:
        - Channel has a discuss_hub_connector
        - Message was created successfully
        - Message author is an INTERNAL user (not portal/public/external)
        """
        # Call the parent method first to create the message
        message = super().message_post(**kwargs)

        # Handle outgoing message to connector (replaces base automation)
        # Only send if message is from an internal user
        if self.discuss_hub_connector and message and message.author_id:
            # Check if message author has an internal user
            # (not portal, not public, not external partner)
            author_user = self.env["res.users"].search(
                [("partner_id", "=", message.author_id.id)], limit=1
            )

            # Only send if user exists and is internal (has base.group_user)
            is_internal_user = False
            if author_user:
                # Check if user has internal user group (not portal/public)
                is_internal_user = author_user.has_group("base.group_user")

            if is_internal_user:
                try:
                    _logger.info(
                        f"discuss_channel.message_post: sending outgoing message "
                        f"({message}) from internal user {message.author_id.name} "
                        f"to {self}"
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
                    f"({message}) - author {message.author_id.name} is not "
                    f"internal user (portal/public/external)"
                )

        return message

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        """
        Override _notify_thread to handle bot automation for incoming messages.
        This replaces the base automation for bot outgoing.

        Only processes bot automation when:
        - Message author is NOT an internal user (not base.group_user), OR
        - Message author IS an internal user BUT channel is type 'chat' (direct message)
        - This prevents infinite loops in group channels while allowing DMs to bots
        - Portal/public users WILL trigger the bot (they are customers)

        Bot processing is done with auto-commit to ensure the incoming message
        is saved and visible before the bot processes it.
        """
        # Call parent method
        result = super()._notify_thread(message, msg_vals=msg_vals, **kwargs)

        # Skip bot processing if explicitly disabled in context
        if self.env.context.get("discuss_hub_skip_bot"):
            return result

        # Check if message author is an internal user (base.group_user)
        # Internal users are agents/employees who should NOT trigger bots in groups
        # BUT can trigger bots in direct messages (channel_type='chat')
        is_internal_user = False
        if message.author_id:
            author_user = self.env["res.users"].search(
                [("partner_id", "=", message.author_id.id)], limit=1
            )
            if author_user:
                # Check if user has internal user group (base.group_user)
                is_internal_user = author_user.has_group("base.group_user")

        # Determine if we should process bot automation
        # Process bot if:
        # 1. User is NOT internal (external/portal/public), OR
        # 2. User IS internal BUT channel is direct message (chat)
        should_process_bot = False

        if not is_internal_user:
            # Non-internal users always trigger bot
            should_process_bot = True
        elif self.channel_type == "chat":
            # Internal users trigger bot only in direct messages
            should_process_bot = True
            author_name = message.author_id.name
            _logger.info(
                f"discuss_channel._notify_thread: internal user {author_name} "
                f"in direct message channel - bot will be processed"
            )

        if should_process_bot:
            # Handle bot automation (replaces base automation)
            # Check if channel has partners with bots
            partners_with_bot = self.channel_partner_ids.filtered(lambda p: p.bot)

            # If internal user in direct message, filter bots that allow this
            if is_internal_user and self.channel_type == "chat":
                partners_with_bot = partners_with_bot.filtered(
                    lambda p: p.bot.respond_to_internal_direct_messages
                )
                if not partners_with_bot:
                    _logger.debug(
                        f"discuss_channel._notify_thread: skipping bot processing "
                        f"- internal user {message.author_id.name} in DM but no bots "
                        f"configured to respond to internal direct messages"
                    )

            _logger.info(
                f"discuss_channel._notify_thread: checking bot automation "
                f"for {self.name} - channel has {len(self.channel_partner_ids)} "
                f"partners, {len(partners_with_bot)} with bot configured"
            )

            if partners_with_bot:
                try:
                    partner_names = partners_with_bot.mapped("name")
                    _logger.info(
                        f"discuss_channel._notify_thread: processing bot for "
                        f"{len(partners_with_bot)} partners: {partner_names}"
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
            # Bot not processed
            if is_internal_user and self.channel_type != "chat":
                author_name = message.author_id.name if message.author_id else "Unknown"
                _logger.debug(
                    f"discuss_channel._notify_thread: skipping bot processing "
                    f"- message from internal user {author_name} "
                    f"in group channel (type={self.channel_type})"
                )

        return result
