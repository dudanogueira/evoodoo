import base64
import json
import logging
import os
import time
from urllib.parse import urljoin

import requests
from jinja2 import Template
from markupsafe import Markup

from .base import Plugin as PluginBase

_logger = logging.getLogger(__name__)


class Plugin(PluginBase):
    plugin_name = "evolution"

    def __init__(self, connector):
        # Call the base PluginBase constructor
        super().__init__(Plugin)

        # Save custom parameter
        self.connector = connector
        self.session = self.get_requests_session()
        self.evolution_url = self.get_evolution_url()

        # MANAGEMENT / HELPERS

    def get_status(self):
        """Get the status of the Evolution API connector instance.

        This method queries the Evolution API to check the current status of the
        WhatsApp connection. It handles various response scenarios including:
        - Instance not found (404): Attempts to create a new instance
          automatically
        - Authentication failure (401): Returns unauthorized status
        - Success (200): Processes response and may include a QR code
          for authentication

        Returns:
            dict: A status dictionary containing:
                - status (str): Current connection state. Examples: 'open',
                  'closed', 'not_found'
                - qrcode (str, optional): Base64 QR code for WhatsApp
                  authentication if needed
                - success (bool): Whether the status request was successful
                - plugin_name (str): Name of the plugin ('evolution')
                - connector (str): String representation of the connector

        Raises:
            No exceptions are propagated: errors are handled and logged
            internally.
        """
        url = f"{self.evolution_url}/instance/connect/{self.connector.name}"
        qrcode = None
        try:
            query = self.session.get(url, timeout=10)
            if query.status_code == 404:
                status = "not_found"
                # try to create
                # define the base_url if not provided
                if not os.getenv("DISCUSS_HUB_INTERNAL_HOST"):
                    base_url = (
                        self.connector.env["ir.config_parameter"]
                        .sudo()
                        .get_param("web.base.url")
                    )
                else:
                    # if DISCUSS_HUB_INTERNAL_HOST is set, use it
                    # this way, it will use the provided URL to add as the webhook
                    base_url = os.getenv("DISCUSS_HUB_INTERNAL_HOST")
                connector_url = urljoin(
                    base_url,
                    f"discuss_hub/connector/{self.connector.uuid}",
                )
                create_instance_url = f"{self.evolution_url}/instance/create"
                payload = {
                    "instanceName": self.connector.name,
                    "qrcode": True,
                    "rejectCall": False,
                    "groupsIgnore": False,
                    "alwaysOnline": True,
                    "readMessages": False,
                    "readStatus": True,
                    "syncFullHistory": True,
                    "integration": "WHATSAPP-BAILEYS",
                    "webhook": {
                        "url": connector_url,
                        "base64": True,
                        "events": [
                            "APPLICATION_STARTUP",
                            "CALL",
                            "CHATS_DELETE",
                            "CHATS_SET",
                            "CHATS_UPDATE",
                            "CHATS_UPSERT",
                            "CONNECTION_UPDATE",
                            "CONTACTS_SET",
                            "CONTACTS_UPDATE",
                            "CONTACTS_UPSERT",
                            "GROUP_PARTICIPANTS_UPDATE",
                            "GROUP_UPDATE",
                            "GROUPS_UPSERT",
                            # "LABELS_ASSOCIATION",
                            # "LABELS_EDIT",
                            "LOGOUT_INSTANCE",
                            "MESSAGES_DELETE",
                            "MESSAGES_SET",
                            "MESSAGES_UPDATE",
                            "MESSAGES_UPSERT",
                            # "PRESENCE_UPDATE",
                            "QRCODE_UPDATED",
                            "REMOVE_INSTANCE",
                            "SEND_MESSAGE",
                            # "TYPEBOT_CHANGE_STATUS",
                            # "TYPEBOT_START"
                        ],
                    },
                }
                create_query = self.session.post(
                    create_instance_url, json=payload, timeout=10
                )
                # retry the query
                if create_query.status_code == 200:
                    logging.info(
                        "EVOLUTION: Created instance after not found response:"
                        + f"{create_query.status_code} - {create_query.json()}"
                    )
                    return self.get_status()
                else:
                    logging.warning(
                        "EVOLUTION: Failed to create instance after not found "
                        + f" response: {create_query.status_code} - {create_query.text}"
                        + f" Payload: {json.dumps(payload)}"
                    )

            elif query.status_code == 401:
                status = "unauthorized"

            if query.status_code == 200:
                qrcode_base64 = query.json().get("base64")
                if qrcode_base64:
                    status = "qr_code"
                    qrcode = qrcode_base64
                status = query.json().get("instance", {}).get("state", "closed")
        except requests.RequestException as e:
            # Log specific error type for better troubleshooting
            error_type = type(e).__name__
            _logger.error(
                "Error getting status: %s: %s for connector %s",
                error_type,
                str(e),
                self.connector.name,
            )
            status = "error"
        except ValueError as e:
            # Handle JSON parsing errors separately
            _logger.error(
                "Invalid JSON response from Evolution API: %s for connector %s",
                str(e),
                self.connector.name,
            )
            status = "error"
        except Exception as e:
            # Catch-all for unexpected errors
            _logger.error(
                "Unexpected error in get_status: %s: %s for connector %s",
                type(e).__name__,
                str(e),
                self.connector.name,
            )
            status = "error"

        return {
            "status": status,
            "qrcode": qrcode,
            "success": True,  # Fixed typo: 'sucess' -> 'success'
            "plugin_name": self.plugin_name,
            "connector": str(self.connector),
        }

    def process_administrative_payload(self, payload):
        """Handle administrative events like QR code updates and
        connection status"""
        data = payload.get("data", {})
        event = payload.get("event")
        instance = payload.get("instance")

        # Early return if no manager channel is configured
        if not self.connector.manager_channel:
            return {
                "success": True,
                "action": "process_administrative_payload",
                "message": "No manager channel configured",
            }

        for channel in self.connector.manager_channel:
            attachments = None
            body = ""

            # QR code updated
            if event == "qrcode.updated" and data.get("qrcode", {}).get("base64"):
                qrcode_base64 = data.get("qrcode", {}).get("base64")
                base64_data = qrcode_base64.split(",")[1]
                decoded_data = base64.b64decode(base64_data)
                body = f"Instance: {instance}"
                attachments = [(f"QRCODE:{instance}", decoded_data)]

            # Connection update
            elif event == "connection.update":
                status = data.get("statusReason")
                status_emoji = "🟢" if status == 200 else "🔴"
                if data.get("state") == "connecting":
                    status_emoji = "🟡"
                body = (
                    f"Instance:{instance}:"
                    + f"<b>{data.get('state').upper()}</b>:{status_emoji}"
                )

            # Logout instance
            elif event == "logout.instance":
                body = f"Instance:{instance}:<b>LOGGED OUT:🔴</b>"

            # Send message if body is not empty
            if body:
                channel.message_post(
                    author_id=self.connector.default_admin_partner_id.id,
                    body=Markup(body),
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                    attachments=attachments,
                )

        # Remove QR codes when connected
        if event == "connection.update" and data.get("state") == "open":
            attachments = self.connector.env["ir.attachment"].search(
                [
                    ("name", "=", f"QRCODE:{instance}"),
                    ("res_model", "=", "discuss.channel"),
                ]
            )
            if attachments:
                attachments.unlink()
        return {"success": True, "action": "process_administrative_payload"}

    def get_requests_session(self):
        """Get a requests session with the connector's API key"""
        session = requests.Session()
        apikey = os.getenv("DISCUSS_HUB_EVOLUTION_APIKEY")
        if self.connector.api_key:
            apikey = self.connector.api_key
        session.headers.update({"apikey": apikey})
        return session

    def get_evolution_url(self):
        """Get the evolution URL"""
        if self.connector.url:
            evolution_url = self.connector.url
        else:
            evolution_url = os.getenv(
                "DISCUSS_HUB_EVOLUTION_URL", "http://evolution:8080"
            )
        return evolution_url

    def get_message_by_id(self, payload):
        """Get message by ID"""
        message_id = payload.get("data", {}).get("keyId")
        if not message_id:
            return False

        image_url_api = f"{self.evolution_url}/chat/findMessages/{self.connector.name}"
        payload_to_send = {"where": {"key": {"id": message_id}}}
        response = self.session.post(
            image_url_api,
            json=payload_to_send,
            timeout=5,
        )
        records = (
            response.json()
            .get("messages", {})
            .get(
                "records",
            )
        )
        return records or False

    def restart_instance(self):
        """restart connector"""
        url = f"{self.evolution_url}/instance/restart/{self.connector.name}"
        try:
            query = self.session.post(url, timeout=10)
            if query.status_code == 404:
                status = "not_found"
            else:
                status = query.json().get("instance", {}).get("state", "closed")
        except requests.RequestException as e:
            _logger.error(f"Error getting status: {str(e)} connector {self.connector}")
            status = "error"
        # wait for the instance to restart
        _logger.info(f"RESTART FOR INSTANCE {self}: {status}")
        time.sleep(5)

    def logout_instance(self):
        """Get the status of the connector"""
        url = f"{self.evolution_url}/instance/logout/{self.connector.name}"
        try:
            query = self.session.delete(url, timeout=10)
            if query.status_code == 404:
                status = "not_found"
            else:
                status = query.json().get("instance", {}).get("state", "closed")
        except requests.RequestException as e:
            _logger.error(f"Error getting status: {str(e)} connector {self.connector}")
            status = "error"
        # wait for the instance to restart
        _logger.info(f"LOUGOUT STATS FOR INSTANCE {self}: {status}. query: {query}")
        time.sleep(5)

    def outgo_message(self, channel, message):
        """
        This method will receive the channel and message
        from the channel base automation
        with the below filter and code:
            the code is available as a data import
        """
        sent_message_id = None
        # Send text message
        if message.body:
            sent_message = self.send_text_message(channel, message)
            sent_message_id = sent_message.json().get("key", {}).get("id")

        # Send attachments
        if message.attachment_ids:
            sent_message = self.send_attachments(channel, message)
            if sent_message:
                sent_message_id = sent_message.json().get("key", {}).get("id")
                if sent_message_id:
                    message.write({"discuss_hub_message_id": sent_message_id})

    def outgo_reaction(self, channel, message, reaction):
        """
        # DOMAIN FILTER FOR BASE AUTOMATION
        [("message_id.discuss_hub_message_id", "!=", "")]
        AUTOMATION BASE CODE FOR REACTION
        the code is available as a data import
        """
        payload = {
            "key": {
                "remoteJid": channel.discuss_hub_outgoing_destination,
                # message.discuss_hub_message_id != message.message_id,
                # this can be used to check if the message is from me
                "fromMe": False,
                "id": message.discuss_hub_message_id,
            },
            "reaction": reaction.content,
        }
        name = channel.discuss_hub_connector.name
        url = f"{self.evolution_url}/message/sendReaction/{name}"

        try:
            response = self.session.post(url, json=payload, timeout=10)
            _logger.info(
                f"action:outgo_reaction channel:{channel} reaction:{reaction}"
                + f"payload:{payload} response:{response.status_code}"
            )
        except requests.RequestException as e:
            _logger.error(f"Error sending reaction: {str(e)}")

    def get_contact_name(self, payload):
        """Get the contact name from the payload"""
        pushname = payload.get("data", {}).get("pushName", False)
        if not pushname:
            pushname = payload.get("pushName", False)
            if not pushname:
                pushname = self.get_contact_identifier(payload)
        return pushname

    def get_contact_identifier(self, payload):
        """Get the contact identifier from the payload"""
        remote_jid = payload.get("data", {}).get("key", {}).get("remoteJid")
        if not remote_jid:
            remote_jid = payload.get("data", {}).get("remoteJid")
            if not remote_jid:
                # this could be contacts upsert
                remote_jid = payload.get("remoteJid")

        whatsapp_number = remote_jid.split("@")[0].split(":")[0]

        # Format Brazilian mobile numbers
        if whatsapp_number.startswith("55") and len(whatsapp_number) == 12:
            whatsapp_number = f"{whatsapp_number[:4]}9{whatsapp_number[4:]}"

        return whatsapp_number

    def get_channel_name(self, payload):
        # TODO: add templated channel name here
        remote_jid = payload.get("data", {}).get("key", {}).get("remoteJid")
        contact_identifier = self.get_contact_identifier(payload)
        contact_name = self.get_contact_name(payload)
        if remote_jid.endswith("@g.us"):
            name = f"WGROUP: <{contact_identifier}>"
        else:
            name = f"Whatsapp: {contact_name} <{contact_identifier}>"
        return name

    def sync_contacts(self, update_profile_picture=True):
        """Sync contacts from Evolution API"""
        # if json_storage evolution_contacts_upsert is empty, set it:
        if not self.connector.evolution_contact_queue:
            url = urljoin(
                self.evolution_url, f"/chat/findContacts/{self.connector.name}"
            )
            contacts_request = self.session.post(url)
            if contacts_request.status_code == 200:
                self.connector.evolution_contact_queue = contacts_request.json()
                # Não usar commit direto - o Odoo gerencia as transações automaticamente
                # self.connector.env.cr.commit()

        for contact in self.connector.evolution_contact_queue:
            # get or create partner
            self.get_or_create_partner(
                payload=contact, update_profile_picture=update_profile_picture
            )
            # remove from storage
            current_state = self.connector.evolution_contact_queue
            current_state.remove(contact)
            self.connector.evolution_contact_queue = current_state
            # Não usar commit direto - o Odoo gerencia as transações automaticamente
            # self.connector.env.cr.commit()
        return True

    # OUTCOMING

    def format_message_before_send(self, message):
        body = (
            message.body.unescape()
            if hasattr(message.body, "unescape")
            else message.body
        )

        # load template
        template_content = self.connector.text_message_template
        if not template_content:
            template_content = "<p>{{message.author_id.name}}<br /><p>{{body}}</p></p>"

        # Define context explicitly
        context = {
            "message": message,
            "body": body,
        }

        # Create and render the Jinja2 template
        template = Template(template_content)
        body = template.render(context)

        # Convert HTML to WhatsApp formatting
        body = self.utils.html_to_whatsapp(body)

        return body

    def send_text_message(self, channel, message):
        """Send text message to WhatsApp"""

        body = self.format_message_before_send(message)

        payload = {"number": channel.discuss_hub_outgoing_destination, "text": body}
        if message.parent_id:
            quoted_message = self.connector.env["mail.message"].search(
                [("id", "=", message.parent_id.id)], limit=1
            )
            quoted = None
            if quoted_message.discuss_hub_message_id:
                quoted = {
                    "key": {"id": quoted_message.discuss_hub_message_id},
                }
                payload["quoted"] = quoted
        base_url = self.evolution_url
        url = f"{base_url}/message/sendText/{channel.discuss_hub_connector.name}"

        try:
            response = self.session.post(url, json=payload, timeout=10)

            if response.status_code == 201:
                sent_message_id = response.json().get("key", {}).get("id")
                message.write({"discuss_hub_message_id": sent_message_id})
                _logger.info(
                    f"action:outgo_message channel:{channel} message:{message}"
                    + f"got message_id: {sent_message_id}"
                )
                return response
            else:
                _logger.error(
                    f"Failed to send text message: {response.status_code} - "
                    + f"{response.text}; Payload: {payload}"
                )
                return False
        except requests.RequestException as e:
            _logger.error(f"Error sending text message: {str(e)}")
            return False

    def send_attachments(self, channel, message):
        """Send message attachments to WhatsApp"""
        base_url = self.evolution_url
        url = f"{base_url}/message/sendMedia/{channel.discuss_hub_connector.name}"

        for attachment in message.attachment_ids:
            # Determine media type
            if attachment.index_content in ["image", "video", "audio"]:
                mediatype = attachment.index_content
                filename = "audio.ogg" if mediatype == "audio" else attachment.name
            else:
                mediatype = "document"
                filename = attachment.name

            payload = {
                "number": channel.discuss_hub_outgoing_destination,
                "mediatype": mediatype,
                "mimetype": attachment.mimetype,
                "media": attachment.datas.decode("utf-8"),
                "fileName": filename,
            }

            try:
                response = self.session.post(url, json=payload, timeout=30)
                if response.status_code == 201:
                    sent_message_id = response.json().get("key", {}).get("id")
                    _logger.info(
                        f"action:outgo_message.with_attachment message:{message} "
                        + f"got message_id:{sent_message_id}"
                    )
                    return response
                else:
                    _logger.error(
                        "Failed to send attachment: "
                        + f"{response.status_code} - {response.text}"
                    )
                    return False
            except requests.RequestException as e:
                _logger.error(f"Error sending attachment: {str(e)}")
                return False

    # INCOMING

    def process_payload(self, payload):
        # TODO: if configured, check for the bearer token on auth headers
        # EVOLUTION can configure a header, so we can add this option here and return
        # unauthorized if the token is not present or different from configured
        event = payload.get("event")
        response = {
            "success": False,
            "action": "process_payload",
            "event": "did nothing",
        }

        # Administrative messages
        if event in ["qrcode.updated", "connection.update", "logout.instance"]:
            response = self.process_administrative_payload(payload)

        # New Message
        elif event in ["messages.upsert"]:
            response = self.process_messages_upsert(payload)

        # Messages update
        elif event in ["messages.update"]:
            response = self.process_messages_update(payload)

        elif event in ["messages.delete"]:
            response = self.process_messages_delete(payload)

        # Contacts Upsert after connection
        elif event in ["contacts.upsert"]:
            if self.connector.import_contacts:
                response = self.process_contacts_upsert(payload)

        return response

    def process_contacts_upsert(self, payload):
        """Process contacts upsert events"""
        # Optimize by processing contacts in batches

        contacts = payload.get("data", [])
        processed_count = 0

        for contact in contacts:
            self.get_or_create_partner(contact, payload.get("instance"))
            processed_count += 1

        return {
            "success": True,
            "action": "process_contacts_upsert",
            "contacts": processed_count,
        }

    def get_message_id(self, payload):
        """Get message ID from payload"""
        message_id = payload.get("data", {}).get("keyId")
        if not message_id:
            return payload.get("data", {}).get("key", {}).get("id")
        # Check if the message ID is a list
        if isinstance(message_id, list):
            message_id = message_id[0]

        return message_id

    def process_messages_upsert(self, payload):
        """Process new incoming messages"""
        data = payload.get("data", {})
        remote_jid = data.get("key", {}).get("remoteJid")
        message_id = self.get_message_id(payload)

        if not remote_jid:
            return {
                "success": False,
                "action": "process_payload",
                "event": "messages.upsert",
                "error": "No remoteJid",
            }

        # Handle Status Broadcast
        if remote_jid == "status@broadcast":
            if not self.connector.evolution_allow_broadcast_messages:
                return {
                    "success": False,
                    "action": "process_payload",
                    "event": "messages.upsert_status@broadcast",
                    "message": "Broadcast messages disabled",
                }

            remote_jid = data.get("key", {}).get("participant")
            _logger.info(
                f"action:process_payload event:message.upsert({message_id}) "
                + f"status@broadcast message from participant {remote_jid}"
            )

        # Get or create partner
        partner = self.get_or_create_partner(payload)

        # Handle multiple partners (using first one)
        if isinstance(partner, list) and len(partner) > 1:
            _logger.info(f"Found multiple partners for {remote_jid}, using first one")
            partner = partner[0]

        if not partner:
            _logger.error(
                f"action:process_payload event:message.upsert({message_id})"
                + f"could not create partner for remote_jid:{remote_jid}"
            )
            return {
                "success": False,
                "action": "process_payload",
                "event": "messages.upsert",
                "error": "Partner creation failed",
            }

        # Find or create channel
        channel = self.get_or_create_channel(partner, payload)
        if not channel:
            return {
                "success": False,
                "action": "process_payload",
                "event": "messages.upsert",
                "error": "Channel creation failed",
            }

        response = {
            "success": False,
            "action": "process_payload",
            "event": "messages.upsert",
        }

        # if the message is from me (sent by the connected number)
        # use the default admin partner id
        if data.get("key", {}).get("fromMe"):
            partner = self.connector.default_admin_partner_id

        # Process different message types
        message = data.get("message", {})
        if message.get("conversation"):
            response = self.handle_text_message(payload, channel, partner)

        elif message.get("reactionMessage"):
            response = self.handle_reaction_message(data, channel, partner, message_id)

        elif message.get("imageMessage") or message.get("stickerMessage"):
            response = self.handle_image_message(data, channel, partner, message_id)

        elif message.get("videoMessage"):
            response = self.handle_video_message(data, channel, partner, message_id)

        elif message.get("audioMessage"):
            response = self.handle_audio_message(data, channel, partner, message_id)

        elif message.get("locationMessage"):
            response = self.handle_location_message(data, channel, partner, message_id)

        elif message.get("documentMessage"):
            response = self.handle_document_message(data, channel, partner, message_id)

        elif message.get("contactMessage"):
            response = self.handle_contact_message(data, channel, partner, message_id)

        return response

    def get_profile_picture(self, payload):
        """Update profile picture for the contact"""
        image_base64 = None
        # First try to get profile URL from contact data
        image_url = payload.get("data", {}).get("profilePicUrl")
        contact_identifier = self.get_contact_identifier(payload)
        # If not available, fetch from API
        if not image_url:
            try:
                image_url_api = f"{self.evolution_url}/chat/fetchProfilePictureUrl/"
                image_url_api += self.connector.name
                response = self.session.post(
                    image_url_api,
                    json={"number": contact_identifier},
                    timeout=5,
                )

                if response.status_code == 200:
                    image_url = response.json().get("profilePictureUrl")
            except (requests.RequestException, ValueError) as e:
                _logger.error(f"Error fetching profile picture URL: {str(e)}")

        # Download and save profile picture
        _logger.debug(
            f"Getting profile picture base64 for {contact_identifier} at {image_url}"
        )
        if image_url:
            try:
                response = requests.get(image_url, timeout=5)
                if response.status_code == 200:
                    image_base64 = base64.b64encode(response.content).decode("utf-8")
            except requests.RequestException as e:
                _logger.error(f"Error downloading profile picture: {str(e)}")

        return image_base64

    def handle_text_message(self, payload, channel, partner, parent_message_id=None):
        """Handle text messages"""
        data = payload.get("data", {})
        body = data.get("message", {}).get("conversation")
        message_id = self.get_message_id(payload)

        # if the channel is a group, prepend the name of the participant
        if data.get("key", {}).get("remoteJid").endswith("@g.us"):
            push_name = data.get("pushName")
            body = f"{push_name}: {body}"

        # Determine author - use parent contact if available
        # TODO: this can be changed to reflect a pre ingested partner
        author = partner.parent_id.id if partner.parent_id else partner.id

        # Check if message is a reply
        if data.get("contextInfo", False):
            quote = data.get("contextInfo", {}).get("quotedMessage")
        else:
            quote = None
        quoted_message = None

        if quote:
            quoted_id = data.get("contextInfo", {}).get("stanzaId")
            quoted_messages = self.connector.env["mail.message"].search(
                [
                    ("discuss_hub_message_id", "=", quoted_id),
                ],
                order="create_date desc",
                limit=1,
            )

            if quoted_messages:
                quoted_message = quoted_messages[0]

        # Post message
        message = channel.message_post(
            parent_id=quoted_message.id if quoted_message else None,
            author_id=author,
            body=body or None,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            message_id=message_id,
        )

        # Update message with reference
        message.write({"discuss_hub_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert.text({message_id})  "
            + f"{channel} for connector {self} and "
            + f"contact_identifier:{self.get_contact_identifier(payload)}: {message}"
        )

        return {
            "action": "process_payload",
            "event": "messages.upsert.conversation",
            "success": True,
            "text_message": message.id,
        }

    def handle_reaction_message(self, data, channel, partner, message_id):
        """Handle message reactions"""
        reaction_data = data.get("message", {}).get("reactionMessage", {})
        original_message_id = reaction_data.get("key").get("id")
        # Find original message
        messages = self.connector.env["mail.message"].search(
            [
                ("discuss_hub_message_id", "=", original_message_id),
            ],
            order="create_date desc",
            limit=1,
        )

        if not messages:
            return {
                "success": False,
                "event": "messages.upsert.reactionMessage",
                "error": "Original message not found",
            }

        message = messages[0]
        reaction_emoji = reaction_data.get("text")

        # get partner or parent
        partner = partner.parent_id if partner.parent_id else partner

        # Create reaction
        self.connector.env["mail.message.reaction"].create(
            {
                "message_id": message.id,
                "partner_id": partner.id,
                "content": reaction_emoji,
            }
        )

        # Notify about reaction if enabled
        if self.connector.notify_reactions:
            notification = channel.message_post(
                author_id=partner.id,
                body=f"Reaction: {reaction_emoji}",
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                parent_id=message.id,
            )
            notification.write({"discuss_hub_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert({message_id}) reaction to "
            + f"message {original_message_id} at {channel}"
        )

        return {
            "action": "process_payload",
            "event": "messages.upsert.reactionMessage",
            "success": True,
            "reaction_message": message.id,
        }

    def handle_image_message(self, data, channel, partner, message_id):
        """Handle image messages"""
        image_base64 = data.get("message", {}).get("base64", {})
        caption = data.get("message", {}).get("imageMessage", {}).get("caption", "")

        # Process image
        decoded_data = base64.b64decode(image_base64)
        attachments = [(caption or "image.jpg", decoded_data)]

        # Post message
        message = channel.message_post(
            author_id=partner.id,
            body=caption,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            attachments=attachments,
            message_id=message_id,
        )
        message.write({"discuss_hub_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert.image({message_id}) "
            + f"image message at {channel}"
        )

        return {
            "action": "process_payload",
            "event": "messages.upsert.imageMessage",
            "success": True,
            "image_message": message.id,
        }

    def handle_video_message(self, data, channel, partner, message_id):
        """Handle video messages"""
        content_base64 = data.get("message", {}).get("base64", {})
        caption = data.get("message", {}).get("videoMessage", {}).get("caption", "")
        file_name = (
            data.get("message", {}).get("videoMessage", {}).get("title", message_id)
            + ".mp4"
        )

        # define the partner
        partner = partner.parent_id if partner.parent_id else partner

        # Process video
        decoded_data = base64.b64decode(content_base64)
        attachments = [(file_name, decoded_data)]

        # Post message
        message = channel.message_post(
            author_id=partner.id,
            body=caption,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            attachments=attachments,
            message_id=message_id,
        )
        message.write({"discuss_hub_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert.video({message_id}) "
            + f"videoMessage at {channel}"
        )

        return {
            "action": "process_payload",
            "event": "messages.upsert.videoMessage",
            "success": True,
            "video_message": message.id,
        }

    def handle_audio_message(self, data, channel, partner, message_id):
        """Handle audio messages"""
        content_base64 = data.get("message", {}).get("base64", {})
        decoded_data = base64.b64decode(content_base64)
        file_name = "audio.ogg"

        # Create attachment
        attachments = [(file_name, decoded_data)]

        # define the partner
        partner = partner.parent_id if partner.parent_id else partner

        # Post message
        message_text = "audio"
        message = channel.message_post(
            author_id=partner.id,
            body=message_text,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            attachments=attachments,
            message_id=message_id,
        )
        message.write({"discuss_hub_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert.audio({message_id}) "
            + "audioMessage at {channel}"
        )

        return {
            "action": "process_payload",
            "event": "messages.upsert.audioMessage",
            "success": True,
            "audio_message": message.id,
        }

    def handle_location_message(self, data, channel, partner, message_id):
        """Handle location messages"""
        location_data = data.get("message", {}).get("locationMessage", {})
        thumb = location_data.get("jpegThumbnail", "")
        decoded_data = base64.b64decode(thumb) if thumb else None
        lat = location_data.get("degreesLatitude", 0)
        lon = location_data.get("degreesLongitude", 0)

        # Prepare attachments
        attachments = [("location.jpeg", decoded_data)] if decoded_data else []
        # define the partner
        partner = partner.parent_id if partner.parent_id else partner
        # Post message
        message = channel.message_post(
            author_id=partner.id,
            body=Markup(
                f'<a href="https://maps.google.com/?q={lat},{lon}">📍{lat}, {lon}</a>'
            ),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            attachments=attachments,
            body_is_html=True,
            message_id=message_id,
        )
        message.write({"discuss_hub_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert.location({message_id}) "
            + f"locationMessage at {channel}"
        )

        return {
            "action": "process_payload",
            "event": "messages.upsert.locationMessage",
            "success": True,
            "location_message": message.id,
        }

    def handle_document_message(self, data, channel, partner, message_id):
        """Handle document messages"""
        document_data = data.get("message", {}).get("documentMessage", {})
        caption = document_data.get("caption", "")
        file_name = document_data.get("title", message_id)
        content_base64 = data.get("message", {}).get("base64", {})
        # Process document
        decoded_data = base64.b64decode(content_base64)
        attachments = [(file_name, decoded_data)]
        # define the partner
        partner = partner.parent_id if partner.parent_id else partner
        # Post message
        message = channel.message_post(
            author_id=partner.id,
            body=caption,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            attachments=attachments,
            message_id=message_id,
        )
        message.write({"discuss_hub_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert.document({message_id})"
            + f"documentMessage at {channel}"
        )

        return {
            "action": "process_payload",
            "event": "messages.upsert.documentMessage",
            "success": True,
            "document_message": message.id,
        }

    def handle_contact_message(self, data, channel, partner, message_id):
        # Determine author - use parent contact if available
        author = partner.parent_id.id if partner.parent_id else partner.id
        # define the partner
        partner = partner.parent_id if partner.parent_id else partner
        quoted_message = None
        # Check if message is a reply
        if data.get("contextInfo", {}) and data.get("contextInfo", {}).get(
            "quotedMessage"
        ):
            quote = data.get("contextInfo", {}).get("quotedMessage")
            quoted_message = None

            if quote:
                quoted_id = data.get("contextInfo", {}).get("stanzaId")
                quoted_messages = self.connector.env["mail.message"].search(
                    [
                        ("discuss_hub_message_id", "=", quoted_id),
                    ],
                    order="create_date desc",
                    limit=1,
                )

                if quoted_messages:
                    quoted_message = quoted_messages[0]

        # parse vcard
        # vcard = data.get("message", {}).get("contactMessage", {}).get("vcard")
        # if vcard:
        #    vcard = vobject.readOne(vcard)
        #    #body = vcard.prettyPrint()
        #    body = vcard

        # Post message
        message = channel.message_post(
            parent_id=quoted_message.id if quoted_message else None,
            author_id=author,
            body=data.get("message", {}).get("contactMessage", {}).get("vcard"),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            message_id=message_id,
        )

        # Update message with reference
        message.write({"discuss_hub_message_id": message_id})

        _logger.info(
            f"action:process_payload"
            f" event:message.upsert.contact({message_id}) new message"
            + f" at {channel} for connector {self}"
            + f" and remote_jid:{data.get('key', {}).get('remoteJid')}: {message}"
        )

        return {
            "action": "process_payload",
            "event": "messages.upsert.contactMessage",
            "success": True,
            "text_message": message.id,
        }

    def process_messages_update(self, payload):
        """Process message updates like read status"""
        discuss_hub_message_id = payload.get("data", {}).get("keyId", {})
        # Handle read status
        if payload.get("data", {}).get("status") == "READ":
            # Skip if read receipts are disabled
            if not self.connector.show_read_receipts:
                return {
                    "success": True,
                    "action": "process_payload",
                    "event": "messages.update.mark_read",
                    "message": "Read receipts disabled",
                }

            message = self.connector.env["mail.message"].search(
                [("discuss_hub_message_id", "=", discuss_hub_message_id)], limit=1
            )

            if not message:
                return {
                    "success": False,
                    "action": "process_payload",
                    "event": "messages.update.mark_read",
                    "error": "Message not found",
                }

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
            if channel_member and message:
                channel_member._mark_as_read(message.id, sync=True)

            _logger.info(
                "action:process_payload"
                + f"event:message.update.read({discuss_hub_message_id})"
                + f" partner:{partner} channel_membership:{channel_member}"
            )

            return {
                "action": "process_payload",
                "event": "messages.update.mark_read",
                "success": True,
                "read_message": message.id,
                "read_partner": partner.parent_id.id,
            }
        elif payload.get("data", {}).get("status") == "DELETED":
            # TODO: NOT WORKING.
            # CHECK HERE: https://github.com/EvolutionAPI/evolution-api/issues/1266
            # message was edited
            _logger.info(
                f"action:process_payload event:message.update({discuss_hub_message_id})"
                + " editting message"
            )
            # get the message content
            message_records = self.get_message_by_id(payload)
            if message_records:
                _logger.info(f"Message for editing found {payload} {message_records}")
                # emulate a new payload here, and call _process_messages_upsert
                emulated_payload = {
                    "event": "messages.upsert",
                    "instance": self.connector.name,
                    "data": message_records[0],
                }
                # TODO: optionally return edit as new message here
                emulated_payload["data"]["contextInfo"] = {
                    "stanzaId": discuss_hub_message_id,
                    "quotedMessage": {
                        "conversation": "aaaaaaaaaa",
                        "messageContextInfo": {},
                    },
                }
                _logger.info(
                    "Emulated payload generated for editing message:"
                    + f" {json.dumps(emulated_payload)}"
                )
                response = self.process_payload(emulated_payload)
                response["edited_message"] = True
                return response
                # or update the message content, and no new messages

        return {
            "success": False,
            "action": "process_payload",
            "event": "messages.update",
            "message": "Unhandled update type",
        }

    def process_messages_delete(self, payload):
        discuss_hub_message_id = payload.get("data", {}).get("id", {})
        # find deleted message
        message = self.connector.env["mail.message"].search(
            [("discuss_hub_message_id", "=", discuss_hub_message_id)], limit=1
        )

        if not message:
            return {
                "success": False,
                "action": "process_payload",
                "event": "messages.delete",
                "message": "Message Not Found",
            }
        # update the message content
        updated_body = self.utils.add_strikethrough_to_paragraphs(message.body)
        message.write({"body": updated_body})
        # add new message alerting of the delete
        # TODO: make this optional
        channel_id = message.res_id
        channel = self.connector.env["discuss.channel"].browse(channel_id)
        # create a new message, using message as parent,
        # saying this message was deleted
        # TODO: make this configurable
        body = "This message was deleted by the user"
        new_message = channel.message_post(
            author_id=self.connector.default_admin_partner_id.id,
            parent_id=message[0].id,
            body=body,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        return {
            "success": True,
            "action": "process_payload",
            "event": "messages.delete",
            "message": f"deletion was alerted by message id {new_message.id}",
        }
