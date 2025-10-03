import logging
import os

from odoo import Command

_logger = logging.getLogger(__name__)

DEFAULT_UPDATE_PROFILE_PICS = ["image_1920", "image_128"]


class Plugin:
    """Base class for all plugins.
    create a basic class that will be inherited by other classes
    this be initiated with a connector object, and based on the type of the connector
    it will load the approriate plugin with the same name in this folder
    """

    name = os.path.basename(__file__).split(".")[0]

    def __str__(self):
        return f"<DiscussHubPlugin: {self.name}: {self.connector}>"

    def __init__(self, connector):
        self.connector = connector
        _logger.debug(f"Loaded plugin {self.name} for connector: {self.connector}")

    def process_payload(self):
        # raise not implemented error
        raise NotImplementedError(
            f"Plugin {self.name} does not implemented process_payload()"
        )

    def get_message_id(self, payload):
        # raise not implemented error
        raise NotImplementedError(
            f"Plugin {self.name} does not implemented get_message_id()"
        )

    def get_status(self):
        # raise not implemented error
        raise NotImplementedError(
            f"Plugin {self.name} does not implemented get_status()"
        )

    def get_contact_name(self, payload=None):
        raise NotImplementedError(
            f"Plugin {self.name} does not implemented get_contact_name()"
        )

    def get_contact_identifier(self, payload):
        raise NotImplementedError(
            f"Plugin {self.name} does not implemented get_contact_identifier()"
        )

    def get_channel_name(self, payload):
        """Get the channel name"""
        raise NotImplementedError(
            f"Plugin {self.name} does not implemented get_channel_name()"
        )

    def restart_instance(self, payload=None):
        """Restart the instance"""
        # raise not implemented error
        raise NotImplementedError(
            f"Plugin {self.name} does not implemented restart_instance()"
        )

    def outgo_reaction(self, channel, message, reaction):
        """Send a reaction to a message"""
        # raise not implemented error
        raise NotImplementedError(
            f"Plugin {self.name} does not implemented outgo_reaction()"
        )

    def logout_instance(self, payload=None):
        """Logout the instance"""
        # raise not implemented error
        raise NotImplementedError(
            f"Plugin {self.name} does not implemented logout_instance()"
        )

    def get_or_create_channel(self, partner, payload):
        """Find existing channel or create a new one for the partner"""
        # get message id
        message_id = self.get_message_id(payload)
        # Check if we have an active channel
        # for this connector and partner as member
        channel = self.connector.env["discuss.channel"].search(
            [
                ("discuss_hub_connector", "=", self.connector.id),
                ("channel_partner_ids.id", "=", partner.parent_id.id),
                ("active", "=", True),
            ],
            order="id desc",
            limit=1,
        )
        if channel:
            _logger.info(
                f"action:process_payload event:message.upsert({message_id}) "
                + f"found channel {channel} for connector {self.connector} "
                + "REUSING CHANNEL."
            )
            return channel

        # Check if we have an archived channel to potentially reopen
        archived_channel = self.connector.env["discuss.channel"].search(
            [
                ("discuss_hub_connector", "=", self.connector.id),
                ("channel_partner_ids.id", "=", partner.parent_id.id),
                ("active", "=", False),
            ],
            order="id desc",
            limit=1,
        )
        if archived_channel:
            if self.connector.reopen_last_archived_channel:
                archived_channel.action_unarchive()
                partners_to_add = self.connector.get_initial_routed_partners(
                    connector=self.connector
                )
                _logger.info(
                    f"action:process_payload event:message.upsert({message_id}) "
                    + f"reactivated channel {archived_channel} for connector "
                    + "REOPENING CHANNEL"
                )
                archived_channel.add_members(
                    partner_ids=[p.id for p in partners_to_add],
                    open_chat_window=True,
                )
                # broadcast as new channel
                archived_channel._broadcast(
                    archived_channel.channel_member_ids.partner_id.ids
                )
                return archived_channel
        # create new channel
        _logger.info(
            f"action:process_payload get_or_create channel ({message_id}) "
            f"for partner {partner} "
            + f"active channel membership not found for connector {self.connector} "
            + "CREATING CHANNEL!"
        )
        partners_to_add = self.connector.get_initial_routed_partners(
            connector=self.connector
        )
        # add default partners
        partners_to_add = [Command.link(p.id) for p in partners_to_add]
        # add visitor partner
        partners_to_add.append(Command.link(partner.parent_id.id))
        channel_name = self.get_channel_name(payload=payload)
        # Create channel
        channel = self.connector.env["discuss.channel"].create(
            {
                "discuss_hub_connector": self.connector.id,
                "discuss_hub_outgoing_destination": self.get_contact_identifier(
                    payload
                ),
                "name": channel_name,
                "channel_partner_ids": partners_to_add,
                "image_128": partner.image_128,
                "channel_type": "group",
            }
        )
        # alert bus of new group
        channel._broadcast(channel.channel_member_ids.partner_id.ids)
        # open the chat for members
        # TODO: Make it optional
        for member in channel.channel_member_ids:
            member._channel_fold("open", 1)
        return channel

    def get_or_create_partner(
        self, payload, update_profile_picture=True, create_contact=True
    ):
        """Get or create partner from using a contact identifier"""

        contact_identifier = self.get_contact_identifier(payload)
        # Search for existing partner
        partner = self.connector.env["res.partner"].search(
            [
                ("name", "=", self.connector.partner_contact_name),
                (self.connector.partner_contact_field, "=", contact_identifier),
                ("parent_id", "!=", False),
            ],
            order="create_date desc",
            limit=1,
        )
        _logger.info(
            "action:get_or_create_partner "
            + f"for message_id ({self.get_message_id(payload)}) "
            + f"found partner {partner} for connector {self.connector} "
            + f"and contact identifier :{contact_identifier}"
        )

        if not create_contact:
            return partner[0].parent_id if partner else False

        # Create partner if not found
        if not partner:
            # Create parent partner
            parent_partner = self.connector.env["res.partner"].create(
                {
                    "name": self.get_contact_name(payload) or contact_identifier,
                    self.connector.partner_contact_field: contact_identifier,
                }
            )

            # Create contact partner
            partner_contact = self.connector.env["res.partner"].create(
                {
                    "name": self.connector.partner_contact_name,
                    self.connector.partner_contact_field: contact_identifier,
                    "parent_id": parent_partner.id,
                }
            )
            partner = partner_contact
            _logger.info(
                f"action:created partner for payload {payload}"
                + f"created partner {partner_contact} for connector {self.connector} "
                + f"and contact identifier :{contact_identifier}"
                + f" with parent {parent_partner}"
            )
        else:
            # We already have the partner
            partner_contact = partner[0]
            parent_partner = partner_contact.parent_id

        # TODO: Update contact name if changed

        # Update profile picture if enabled
        if update_profile_picture and (
            not partner.image_128 or self.connector.always_update_profile_picture
        ):
            imagebase64 = self.get_profile_picture(payload)
            if imagebase64:
                # TODO: option to not add profile for partner_contact to save resources
                partners_to_update = [
                    partner_contact,
                    parent_partner,
                ]
                # Update profile picture for partners
                for partner_update in partners_to_update:
                    self.update_profile_picture(partner_update, imagebase64)
                    _logger.info(
                        f"Updated profile picture for partner {partner_update} "
                    )
        return partner

    def update_profile_picture(self, partner, imagebase64, images=None):
        """Update the profile picture of the partner"""
        # Validate imagebase64 is not empty or whitespace-only
        if not imagebase64 or not imagebase64.strip():
            _logger.warning(
                f"Skipping profile picture update for partner {partner.id}: "
                "empty or invalid image data"
            )
            return False

        if not images:
            images = DEFAULT_UPDATE_PROFILE_PICS
        _logger.info(f"Updating profile pic: ({partner.id}) of images {images}")
        try:
            for image in images:
                partner.write({image: imagebase64})
            return True
        except Exception as e:
            _logger.error(
                f"Error updating profile picture for partner {partner.id}: {e}"
            )
            return False
