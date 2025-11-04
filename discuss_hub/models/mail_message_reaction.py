import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class MailMessageReaction(models.Model):
    """
    Override mail.message.reaction to handle outgoing reactions to external connectors.
    This replaces the base automation for outgoing reactions.
    """

    _inherit = "mail.message.reaction"

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to handle outgoing reactions.
        This replaces the base automation trigger on_create_or_write.
        """
        # Call parent method to create the reaction(s)
        reactions = super().create(vals_list)

        # Process each reaction for connector notification
        for reaction in reactions:
            # Check if message has discuss_hub_message_id (external message)
            if reaction.message_id and reaction.message_id.discuss_hub_message_id:
                try:
                    # Find the channel for this message
                    channel = self.env["discuss.channel"].search(
                        [("id", "=", reaction.message_id.res_id)], limit=1
                    )

                    if channel and channel.discuss_hub_connector:
                        _logger.info(
                            f"mail_message_reaction.create: "
                            f"connector:{channel.discuss_hub_connector} "
                            f"channel:{channel} reaction {reaction} "
                            f"to message {reaction.message_id}"
                        )
                        channel.discuss_hub_connector.outgo_reaction(
                            channel, reaction.message_id, reaction
                        )
                except Exception as e:
                    _logger.error(
                        f"Error sending outgoing reaction to connector: {e}",
                        exc_info=True,
                    )

        return reactions

    def write(self, vals):
        """
        Override write to handle reaction updates.
        This replaces the base automation trigger on_create_or_write.
        """
        # Call parent method
        result = super().write(vals)

        # Process each reaction for connector notification
        for reaction in self:
            # Check if message has discuss_hub_message_id (external message)
            if reaction.message_id and reaction.message_id.discuss_hub_message_id:
                try:
                    # Find the channel for this message
                    channel = self.env["discuss.channel"].search(
                        [("id", "=", reaction.message_id.res_id)], limit=1
                    )

                    if channel and channel.discuss_hub_connector:
                        _logger.info(
                            f"mail_message_reaction.write: "
                            f"connector:{channel.discuss_hub_connector} "
                            f"channel:{channel} reaction {reaction} "
                            f"to message {reaction.message_id}"
                        )
                        channel.discuss_hub_connector.outgo_reaction(
                            channel, reaction.message_id, reaction
                        )
                except Exception as e:
                    _logger.error(
                        f"Error sending outgoing reaction update to connector: {e}",
                        exc_info=True,
                    )

        return result
