import base64
import logging

import requests

from .base import Plugin as PluginBase

_logger = logging.getLogger(__name__)


class Plugin(PluginBase):
    plugin_name = "example"

    def __init__(self, connector):
        # Call the base PluginBase constructor
        super().__init__(Plugin)

        # Save custom parameter
        self.connector = connector
        # self.session = self.something_to_have_globally()
        # example payload for simple message
        self.payload = {
            "message_id": 4567,
            "message_type": "text",
            "message": "Hello World",
            "contact_name": "John Doe",
            "contact_identifier": "1234567890",
            "profile_picture": "https://cataas.com/cat",
        }
        # example payload for mark as read
        # self.payload_mark_as_read = {
        #     "message_type": "read",
        #     "message_id": 4567,
        # }

    def process_payload(self, payload):
        # Process the payload
        # get the message id
        message_id = self.get_message_id(payload)
        # get the contact name
        contact_name = self.get_contact_name(payload)
        # get the contact identifier
        contact_identifier = self.get_contact_identifier(payload)
        # get the profile picture
        profile_picture = self.get_profile_picture(payload)
        # get the channel name
        channel_name = self.get_channel_name(payload)
        # below are builtin methods, that you don't need to override
        partner = self.get_or_create_partner(
            payload=payload,
            update_profile_picture=True,
        )
        channel = self.get_or_create_channel(
            partner=partner,
            payload=payload,
        )
        # This will compose our response
        response = {
            "success": True,
            "status": "success",
            "payload": payload,
            "action": "process_payload",
            "message_id": message_id,
            "contact_name": contact_name,
            "contact_identifier": contact_identifier,
            "profile_picture": profile_picture,
            "channel_name": channel_name,
            "channel_id": channel.id,
            "partner_id": partner.id,
        }
        # now that we have the channel, we can send the message
        # we can find if the incoming message is quoting a previous message
        quoted_id = payload.get("quoted_id")
        quoted_message_id = None
        if quoted_id:
            quoted_messages = self.connector.env["mail.message"].search(
                [
                    ("discuss_hub_message_id", "=", quoted_id),
                ],
                order="create_date desc",
                limit=1,
            )
            quoted_message_id = quoted_messages.id

        if payload.get("message_type") == "text":
            # Post message
            # you can use a method, for example, _handle_text_message()
            author = partner.parent_id.id if partner.parent_id else partner.id
            new_message = channel.message_post(
                parent_id=quoted_message_id,  # this can be used for replies
                author_id=author,
                body=payload.get("message") or None,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                message_id=message_id,
            )
            response["new_message_id"] = new_message.id
            response["event"] = "messages.text.create"
            # now we need to register the discuss_hub_message_id on that message
            # Update message with reference
            new_message.write({"discuss_hub_message_id": message_id})

        elif payload.get("message_type") == "read":
            # Mark message as read
            return self.mark_last_read(payload)
        else:
            # Handle other message types
            _logger.warning(f"Unknown message type: {payload.get('message_type')}")
            return {
                "success": False,
                "action": "process_payload",
                "event": "uknown",
                "error": f"Unknown message type: {payload.get('message_type')}",
            }

        return response

    def get_message_id(self, payload=None):
        # Extract message ID from payload
        return payload.get("message_id")

    def get_contact_name(self, payload=None):
        # Extract contact name from payload
        return payload.get("contact_name", "John Doe")

    def get_contact_identifier(self, payload=None):
        # Extract unique identifier from payload
        return payload.get("contact_identifier", "1234567890")

    def get_profile_picture(self, payload=None):
        # Extract profile picture from payload
        image_base64 = None
        try:
            response = requests.get("https://cataas.com/cat", timeout=5)
            if response.status_code == 200:
                image_base64 = base64.b64encode(response.content).decode("utf-8")
        except requests.RequestException as e:
            _logger.error(f"Error downloading profile picture: {str(e)}")
        return image_base64

    def get_channel_name(self, payload=None):
        # Extract channel name from payload
        return (
            f"{self.get_contact_name(payload)}"
            + f"<{self.get_contact_identifier(payload)}>"
        )

    def get_status(self, payload=None):
        # Check connection status
        return {
            "status": "open",
            "has_restart": False,
            "has_close": False,
        }

    def mark_last_read(self, payload=None):
        # get the message to mark as read
        discuss_hub_message_id = payload.get("message_id")
        if discuss_hub_message_id:
            # search for the message in Odoo
            message = self.connector.env["mail.message"].search(
                [("discuss_hub_message_id", "=", discuss_hub_message_id)], limit=1
            )
            if not message:
                return {
                    "success": False,
                    "action": "process_payload",
                    "event": "messages.update.mark_read",
                    "error": f"Message {discuss_hub_message_id} not found",
                }
            # get the channel id
            channel_id = message.res_id
            # Get partner
            contact_identifier = self.get_contact_identifier(payload)
            partner = self.get_or_create_partner(
                payload,
                update_profile_picture=False,
                create_contact=False,
            )

            if not partner:
                _logger.info(
                    "action:process_payload"
                    + f"event:message.update.read({discuss_hub_message_id})"
                    + f" partner: not found for contact identifier {contact_identifier}"
                )
                return {
                    "success": False,
                    "action": "process_payload",
                    "event": "messages.update.mark_read",
                    "error": "Partner not found",
                }

            # Mark message as read
            channel_member = self.connector.env["discuss.channel.member"].search(
                [
                    ("channel_id", "=", channel_id),
                    ("partner_id", "=", partner.id),
                ],
                limit=1,
            )
            
            if not channel_member:
                _logger.info(
                    "action:process_payload"
                    + f"event:message.update.read({discuss_hub_message_id})"
                    + f" channel_member: not found for partner {partner.id} in channel {channel_id}"
                )
                return {
                    "success": False,
                    "action": "process_payload",
                    "event": "messages.update.mark_read",
                    "error": "Channel member not found",
                }
            
            channel_member._mark_as_read(message.id)

            return {
                "success": True,
                "action": "process_payload",
                "event": "messages.update.mark_read",
            }
        
        # If no message_id provided
        return {
            "success": False,
            "action": "process_payload",
            "event": "messages.update.mark_read",
            "error": "No message_id provided",
        }
