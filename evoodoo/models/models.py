# -*- coding: utf-8 -*-
import logging
import uuid
import base64
import time
import re
import html
import requests
from jinja2 import Template
import vobject
from markupsafe import Markup
from odoo import models, fields, Command, api
import os
_logger = logging.getLogger(__name__)


class EvoConnector(models.Model):
    '''
    TODO: allow templatable channel name
    TODO: implement optional composing
    TODO: option to ignore groups
    TODO: option to grab all participants of a group and show the participant name and photo instead of the participant name prepended
    TODO: something with statusbroadcast may be sending status as the remotejid at some point.
    TODO: Allow selection of partners to ignore
    TODO; auto add base automations
    '''

    # TODO: change model name... to evo.connector. Not sure why I did this hehehee
    _name = 'evo_connector'
    _description = 'WhatsApp Integration Connector'

    enabled = fields.Boolean(default=True)
    import_contacts = fields.Boolean(default=True)
    name = fields.Char(required=True)
    uuid = fields.Char(
        required=True,
        # Fixed: Use function call to avoid evaluation at import time
        default=lambda self: str(uuid.uuid4())
    )
    description = fields.Text()
    type = fields.Selection([
        ('evolution', 'Evolution'),
    ], default='evolution', required=True)
    url = fields.Char(required=True)
    api_key = fields.Char(required=True)
    manager_channel = fields.Many2many(
        comodel_name="discuss.channel",
        string="Channel Manager"
    )
    automatic_added_partners = fields.Many2many(
        comodel_name="res.partner",
        string="Automatic Added Partners",
    )
    # Configuration options
    allow_broadcast_messages = fields.Boolean(
        default=True, string="Allow Status Broadcast Messages")
    reopen_last_archived_channel = fields.Boolean(
        default=False, string="Reopen Last Archived Channel")
    always_update_profile_picture = fields.Boolean(
        default=False, string="Always Update Profile Pictures")
    show_read_receipts = fields.Boolean(
        default=True, string="Show Read Receipts")
    notify_reactions = fields.Boolean(
        default=True, string="Notify Message Reactions")
    default_admin_partner_id = fields.Many2one(
        'res.partner', string="Default Admin Partner", default=lambda self: self.env['res.partner'].search([('id', '=', 1)], limit=1))
    text_message_template = fields.Text(
        string="Text Message Template", default="<p><b>[{{message.author_id.name}}]</b><br /><p>{{body}}</p></p>"
    )
    
    last_message_date = fields.Datetime(
        string="Last Message Date",
        compute='_compute_last_message',
        store=False
    )
    channels_total = fields.Integer(
        string="Total Channels",
        compute='_compute_channels_total',
        store=False
    )    
    status = fields.Selection(
        [
            ('open', 'Open'),
            ('closed', 'Closed'),
            ('not_found', 'Not Found'),
             ('unauthorized', 'Unauthorized'),
            ('error', 'Error'),
        ],
        compute='_compute_status',
        default='closed', 
        required=False,
        store=False
    )
    qr_code_base64 = fields.Text(
        compute='_compute_status',
        store=False
    )

    @api.model
    def action_new_connector():
        """Decides whether to open a modal or regular form based on env variables"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'New Connector',
            'res_model': 'evo_connector',
            'view_mode': 'form',
            'target': 'new',  # Opens as a modal
        }        
        if os.getenv("ODOO_CONNECTOR_MODAL") and os.getenv("EVOLUTION_API_KEY") and os.getenv("EVOLUTION_ODOO_URL"):
            return {
                'type': 'ir.actions.act_window',
                'name': 'New Connector',
                'res_model': 'evo_connector',
                'view_mode': 'form',
                'target': 'new',  # Opens as a modal
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'New Connector',
                'res_model': 'evo_connector',
                'view_mode': 'form',
                'target': 'current',  # Opens as a regular form
            }

    def action_open_html(self):
        """Opens an HTML content in a new wizard."""
        self.ensure_one()

        status, qr_code_base64 = self._get_status()
        html_content = f"""
            <html>
            <head>
                <title>Connector Statuss</title>
            </head>
            <body>
                <h1>{self.name}</h1>
                <p>Status: {status}</p>
                <p>QR Code: 
                <img style="background-color:#71639e;" src="{qr_code_base64}" />
                </p>
            </body>
            </html>
        """

        return {
            'type': 'ir.actions.act_window',
            'name': 'Connector Status',
            'res_model': 'evo_connector_status',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_html_content': html_content},
        }

    def _compute_last_message(self):
        for connector in self:
            last_message = self.env['discuss.channel'].search([
                ('evo_connector', '=', connector.id),
            ], order="write_date desc", limit=1)

            #connector.last_message = last_message.body if last_message else "No messages yet"
            connector.last_message_date = last_message.write_date if last_message else None

    def _compute_channels_total(self):
        for connector in self:
            connector.channels_total = self.env['discuss.channel'].search_count([
                ('evo_connector', '=', connector.id),
            ])

    @api.depends("api_key", "url", "name")
    def _compute_status(self):
        for connector in self:
            status, qr_code_base64 = connector._get_status()
            connector.status = status
            connector.qr_code_base64 = qr_code_base64
    #
    # UI METHODS
    #

    def open_status_modal(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Status Details',
            'view_mode': 'form',
            'res_model': 'evo_connector',
            'res_id': self.id,
            'target': 'new',
        }

    def _get_status(self):
        '''Get the status of the connector'''
        headers = {'apikey': self.api_key}
        url = f"{self.url}/instance/connect/{self.name}"
        qrcode = None
        try:
            query = requests.get(url, headers=headers, timeout=10)
            if query.status_code == 404:
                status = "not_found"
            elif query.status_code == 401:
                status = "unauthorized"
            else:
                qrcode_base64 = query.json().get("base64", None)
                if qrcode_base64:
                    status = "qr_code"
                    qrcode = qrcode_base64  
                status = query.json().get("instance", {}).get("state", "closed")
        except requests.RequestException as e:
            _logger.error(f"Error getting status: {str(e)} connector {self}")
            status = "error"
        return status, qrcode

    def process_payload(self, payload):
        '''
        Process the payload from the evolution server for this connector
        '''
        event = payload.get("event")
        response = {"success": False,
                    "action": "process_payload", "event": "did nothing"}

        # Administrative messages
        if event in ["qrcode.updated", "connection.update", "logout.instance"]:
            response = self._process_administrative_payload(payload)

        # New Message
        elif event in ["messages.upsert"]:
            response = self._process_messages_upsert(payload)

        # Messages update
        elif event in ["messages.update"]:
            response = self._process_messages_update(payload)

        # Contacts Upsert after connection
        elif event in ["contacts.upsert"] and self.import_contacts:
            response = self._process_contacts_upsert(payload)

        return response

    def _process_administrative_payload(self, payload):
        '''Handle administrative events like QR code updates and connection status'''
        data = payload.get("data", {})
        event = payload.get("event")
        instance = payload.get("instance")

        # Early return if no manager channel is configured
        if not self.manager_channel:
            return {"success": True, "action": "process_administrative_payload", "message": "No manager channel configured"}

        for channel in self.manager_channel:
            attachments = None
            body = ""

            # QR code updated
            if event == "qrcode.updated" and data.get("qrcode", {}).get("base64"):
                qrcode_base64 = data.get("qrcode", {}).get("base64")
                base64_data = qrcode_base64.split(",")[1]
                decoded_data = base64.b64decode(base64_data)
                body = f"Instance: {instance}"
                attachments = [(f'QRCODE:{instance}', decoded_data)]

            # Connection update
            elif event == "connection.update":
                status = data.get("statusReason")
                status_emoji = "🟢" if status == 200 else "🔴"
                if data.get("state") == "connecting":
                    status_emoji = "🟡"
                body = f"Instance:{instance}:<b>{data.get('state').upper()}</b>:{status_emoji}"

            # Logout instance
            elif event == "logout.instance":
                body = f"Instance:{instance}:<b>LOGGED OUT:🔴</b>"

            # Send message if body is not empty
            if body:
                channel.message_post(
                    author_id=self.default_admin_partner_id.id,
                    body=Markup(body),
                    message_type="comment",
                    subtype_xmlid='mail.mt_comment',
                    attachments=attachments
                )

        # Remove QR codes when connected
        if event == "connection.update" and data.get("state") == "open":
            attachments = self.env['ir.attachment'].search([
                ('name', '=', f'QRCODE:{instance}'),
                ('res_model', '=', 'discuss.channel'),
            ])
            if attachments:
                attachments.unlink()

        self.env.cr.commit()
        return {"success": True, "action": "process_administrative_payload"}

    def _process_messages_upsert(self, payload):
        '''Process new incoming messages'''
        data = payload.get("data", {})
        remote_jid = data.get("key", {}).get("remoteJid")
        message_id = data.get("key", {}).get("id")
        name = data.get("pushName")

        if not remote_jid:
            return {"success": False, "action": "process_payload", "event": "messages.upsert", "error": "No remoteJid"}

        # Handle Status Broadcast
        if remote_jid == "status@broadcast":
            if not self.allow_broadcast_messages:
                return {"success": False, "action": "process_payload", "event": "messages.upsert_status@broadcast", "message": "Broadcast messages disabled"}

            remote_jid = data.get("key", {}).get("participant")
            _logger.info(
                f"action:process_payload event:message.upsert({message_id}) status@broadcast message from participant {remote_jid}")

        # Get or create partner
        contact = {"remoteJid": remote_jid, "pushName": name}
        partner = self.get_or_create_partner(
            contact, instance=payload.get("instance")
        )
        

        # Handle multiple partners (using first one)
        if isinstance(partner, list) and len(partner) > 1:
            _logger.info(
                f"Found multiple partners for {remote_jid}, using first one")
            partner = partner[0]

        if not partner:
            _logger.error(
                f"action:process_payload event:message.upsert({message_id}) could not create partner for remote_jid:{remote_jid}")
            return {"success": False, "action": "process_payload", "event": "messages.upsert", "error": "Partner creation failed"}

        # Find or create channel
        channel = self._find_or_create_channel(
            partner, remote_jid, name, message_id
        )
        if not channel:
            return {"success": False, "action": "process_payload", "event": "messages.upsert", "error": "Channel creation failed"}

        response = {"success": False, "action": "process_payload",
                    "event": "messages.upsert"}

        # if the message is from me (sent by the connected number)
        # use the default admin partner id
        if data.get("key", {}).get("fromMe"):
            partner = self.default_admin_partner_id


        # Process different message types
        if data.get("message", {}).get("conversation"):
            response = self._handle_text_message(
                data, channel, partner, message_id
            )

        elif data.get("message", {}).get("reactionMessage"):
            response = self._handle_reaction_message(
                data, channel, partner, message_id)

        elif data.get("message", {}).get("imageMessage"):
            response = self._handle_image_message(
                data, channel, partner, message_id)

        elif data.get("message", {}).get("videoMessage"):
            response = self._handle_video_message(
                data, channel, partner, message_id)

        elif data.get("message", {}).get("audioMessage"):
            response = self._handle_audio_message(
                data, channel, partner, message_id)

        elif data.get("message", {}).get("locationMessage"):
            response = self._handle_location_message(
                data, channel, partner, message_id)

        elif data.get("message", {}).get("documentMessage"):
            response = self._handle_document_message(
                data, channel, partner, message_id)

        elif data.get("message", {}).get("contactMessage"):
            response = self._handle_contact_message(
                data, channel, partner, message_id)

        # Commit changes
        self.env.cr.commit()
        return response

    def _find_or_create_channel(self, partner, remote_jid, name, message_id):
        '''Find existing channel or create a new one for the partner'''
        # Check if we have an unarchived channel for this connector and partner as member
        membership = self.env['discuss.channel.member'].search([
            # ('channel_id.active', '=', True),
            ('channel_id.evo_connector', '=', self.id),
            ('partner_id', '=', partner.id)
        ],
            order='create_date desc',
            limit=1
        )

        # define parters to auto add
        # TODO: here we can add some logic for agent distribution
        partners_to_add = [Command.link(p.id)
                           for p in self.automatic_added_partners]
        partners_to_add.append(Command.link(partner.id))

        # Return existing channel if found and active
        if membership:
            if membership.channel_id.active:
                channel = membership.channel_id
                _logger.info(
                    f"action:process_payload event:message.upsert({message_id}) found channel {channel} for connector {self} and remote_jid:{remote_jid}. REUSING CHANNEL.")
                return channel
            # or reopen if that's the configuration
            else:
                if self.reopen_last_archived_channel:
                    membership.channel_id.action_unarchive()
                    _logger.info(
                        f"action:process_payload event:message.upsert({message_id}) reactivated channel {membership.channel_id} for connector {self} and remote_jid:{remote_jid}. REOPENING CHANNEL")
                    return membership.channel_id
        # create new channel
        _logger.info(
            f'''action:process_payload event:message.upsert({message_id}) 
            active channel membership not found for connector {self} and
              remote_jid:{remote_jid}. CREATING CHANNEL.'''
        )
        # TODO: add templated channel name here
        if remote_jid.endswith("@g.us"):
            channel_name = f'WGROUP: <{remote_jid}>'
        else:    
            channel_name = f'Whatsapp: {name} <{remote_jid}>'

        # Create channel
        channel = self.env['discuss.channel'].create({
            'evo_connector': self.id,
            'evo_outgoing_destination': remote_jid,
            'name': channel_name,
            'channel_partner_ids': partners_to_add,
            'image_128': partner.image_128,
            'channel_type': 'group',
        })

        return channel

    def _handle_text_message(self, data, channel, partner, message_id):
        '''Handle text messages'''
        body = data.get("message", {}).get("conversation")

        # if the channel is a group, prepend the name of the participant
        if data.get("key", {}).get("remoteJid").endswith("@g.us"):
            body = f"{data.get("pushName")}: {body}"

        # Determine author - use parent contact if available
        # TODO: this can be changed to reflect a pre ingested partner
        author = partner.parent_id.id if partner.parent_id else partner.id

        # Check if message is a reply
        quote = data.get("contextInfo", {}).get("quotedMessage")
        quoted_message = None

        if quote:
            quoted_id = data.get("contextInfo", {}).get("stanzaId")
            quoted_messages = self.env['mail.message'].search([
                ('evo_message_id', '=', quoted_id),
            ], order='create_date desc', limit=1)

            if quoted_messages:
                quoted_message = quoted_messages[0]

        # Post message
        message = channel.message_post(
            parent_id=quoted_message.id if quoted_message else None,
            author_id=author,
            body=body or None,
            message_type="comment",
            subtype_xmlid='mail.mt_comment',
            message_id=message_id
        )

        # Update message with reference
        message.write({"evo_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert({message_id}) new message at {channel} for connector {self} and remote_jid:{data.get('key', {}).get('remoteJid')}: {message}")

        return {
            "action": "process_payload",
            "event": "messages.upsert.conversation",
            "success": True,
            "text_message": message.id
        }

    def _handle_reaction_message(self, data, channel, partner, message_id):
        '''Handle message reactions'''
        reaction_data = data.get("message", {}).get("reactionMessage", {})
        original_message_id = reaction_data.get("key").get("id")
        # Find original message
        messages = self.env['mail.message'].search([
            ('evo_message_id', '=', original_message_id),
        ], order='create_date desc', limit=1)

        if not messages:
            return {"success": False, "event": "messages.upsert.reactionMessage", "error": "Original message not found"}

        message = messages[0]
        reaction_emoji = reaction_data.get("text")

        # Create reaction
        self.env['mail.message.reaction'].create({
            'message_id': message.id,
            'partner_id': partner.id,
            'content': reaction_emoji,
        })
        self.env.cr.commit()

        # Notify about reaction if enabled
        if self.notify_reactions:
            notification = channel.message_post(
                author_id=partner.id,
                body=f"Reaction: {reaction_emoji}",
                message_type="comment",
                subtype_xmlid='mail.mt_comment',
                parent_id=message.id,
            )
            notification.write({"evo_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert({message_id}) reaction to message {original_message_id} at {channel}")

        return {
            "action": "process_payload",
            "event": "messages.upsert.reactionMessage",
            "success": True,
            "reaction_message": message.id
        }

    def _handle_image_message(self, data, channel, partner, message_id):
        '''Handle image messages'''
        image_base64 = data.get("message", {}).get("base64", {})
        caption = data.get("message", {}).get(
            "imageMessage", {}).get("caption", '')

        # Process image
        decoded_data = base64.b64decode(image_base64)
        attachments = [(caption or "image.jpg", decoded_data)]

        # Post message
        message = channel.message_post(
            author_id=partner.id,
            body=caption,
            message_type="comment",
            subtype_xmlid='mail.mt_comment',
            attachments=attachments,
            message_id=message_id
        )
        message.write({"evo_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert({message_id}) image message at {channel}")

        return {
            "action": "process_payload",
            "event": "messages.upsert.imageMessage",
            "success": True,
            "image_message": message.id
        }

    def _handle_video_message(self, data, channel, partner, message_id):
        '''Handle video messages'''
        content_base64 = data.get("message", {}).get("base64", {})
        caption = data.get("message", {}).get(
            "videoMessage", {}).get("caption", '')
        file_name = data.get("message", {}).get(
            "videoMessage", {}).get("title", message_id) + ".mp4"

        # Process video
        decoded_data = base64.b64decode(content_base64)
        attachments = [(file_name, decoded_data)]

        # Post message
        message = channel.message_post(
            author_id=partner.id,
            body=caption,
            message_type="comment",
            subtype_xmlid='mail.mt_comment',
            attachments=attachments,
            message_id=message_id
        )
        message.write({"evo_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert({message_id}) videoMessage at {channel}")

        return {
            "action": "process_payload",
            "event": "messages.upsert.videoMessage",
            "success": True,
            "video_message": message.id
        }

    def _handle_audio_message(self, data, channel, partner, message_id):
        '''Handle audio messages'''
        content_base64 = data.get("message", {}).get("base64", {})
        decoded_data = base64.b64decode(content_base64)
        file_name = "audio.ogg"

        # Create attachment
        attachments = [(file_name, decoded_data)]

        # Post message
        message = channel.message_post(
            author_id=partner.id,
            body='Audio message',
            message_type="comment",
            subtype_xmlid='mail.mt_comment',
            attachments=attachments,
            message_id=message_id
        )
        message.write({"evo_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert({message_id}) audioMessage at {channel}")

        return {
            "action": "process_payload",
            "event": "messages.upsert.audioMessage",
            "success": True,
            "audio_message": message.id
        }

    def _handle_location_message(self, data, channel, partner, message_id):
        '''Handle location messages'''
        location_data = data.get("message", {}).get("locationMessage", {})
        thumb = location_data.get("jpegThumbnail", "")
        decoded_data = base64.b64decode(thumb) if thumb else None
        lat = location_data.get("degreesLatitude", 0)
        lon = location_data.get("degreesLongitude", 0)

        # Prepare attachments
        attachments = [("location.jpeg", decoded_data)] if decoded_data else []

        # Post message
        message = channel.message_post(
            author_id=partner.id,
            body=Markup(
                f'<a href="https://maps.google.com/?q={lat},{lon}">📍{lat}, {lon}</a>'),
            message_type="comment",
            subtype_xmlid='mail.mt_comment',
            attachments=attachments,
            body_is_html=True,
            message_id=message_id
        )
        message.write({"evo_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert({message_id}) locationMessage at {channel}")

        return {
            "action": "process_payload",
            "event": "messages.upsert.locationMessage",
            "success": True,
            "location_message": message.id
        }

    def _handle_document_message(self, data, channel, partner, message_id):
        '''Handle document messages'''
        document_data = data.get("message", {}).get("documentMessage", {})
        caption = document_data.get("caption", "")
        file_name = document_data.get("title", message_id)
        content_base64 = data.get("message", {}).get("base64", {})
        # Process document
        decoded_data = base64.b64decode(content_base64)
        attachments = [(file_name, decoded_data)]

        # Post message
        message = channel.message_post(
            author_id=partner.id,
            body=caption,
            message_type="comment",
            subtype_xmlid='mail.mt_comment',
            attachments=attachments,
            message_id=message_id
        )
        message.write({"evo_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert({message_id}) documentMessage at {channel}")

        return {
            "action": "process_payload",
            "event": "messages.upsert.documentMessage",
            "success": True,
            "document_message": message.id
        }

    def _handle_contact_message(self, data, channel, partner, message_id):
        # Determine author - use parent contact if available
        author = partner.parent_id.id if partner.parent_id else partner.id

        quoted_message = None
        # Check if message is a reply
        if data.get("contextInfo", {}) and data.get("contextInfo", {}).get("quotedMessage"):
            quote = data.get("contextInfo", {}).get("quotedMessage")
            quoted_message = None

            if quote:
                quoted_id = data.get("contextInfo", {}).get("stanzaId")
                quoted_messages = self.env['mail.message'].search([
                    ('evo_message_id', '=', quoted_id),
                ], order='create_date desc', limit=1)

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
            body=data.get("message", {}).get(
                "contactMessage", {}).get("vcard"),
            message_type="comment",
            subtype_xmlid='mail.mt_comment',
            message_id=message_id
        )

        # Update message with reference
        message.write({"evo_message_id": message_id})

        _logger.info(
            f"action:process_payload event:message.upsert({message_id}) new message at {channel} for connector {self} and remote_jid:{data.get('key', {}).get('remoteJid')}: {message}")

        return {
            "action": "process_payload",
            "event": "messages.upsert.contactMessage",
            "success": True,
            "text_message": message.id
        }
        # else:
        #     return {
        #         "success": False,
        #         "action": "process_payload",
        #         "event": "messages.upsert.contactMessage.Failed",
        #     }

    def _process_messages_update(self, payload):
        '''Process message updates like read status'''
        # Skip if read receipts are disabled
        if not self.show_read_receipts and payload.get("data", {}).get("status") == "READ":
            return {"success": True, "action": "process_payload", "event": "messages.update.mark_read", "message": "Read receipts disabled"}

        # Handle read status
        if payload.get("data", {}).get("status") == "READ":
            evo_message_id = payload.get("data", {}).get("keyId", {})
            message = self.env['mail.message'].search(
                [('evo_message_id', '=', evo_message_id)], limit=1)

            if not message:
                return {"success": False, "action": "process_payload", "event": "messages.update.mark_read", "error": "Message not found"}

            channel_id = message.res_id

            # Get partner
            participant_id = payload.get("data", {}).get(
                "participant", {}).split("@")[0].split(":")[0]
            contact = {"remoteJid": participant_id}
            partner = self.get_or_create_partner(
                contact=contact,
                instance=payload.get("instance"),
                update_profile_picture=False,
                create_contact=False,
            )

            if not partner or not partner.parent_id:
                return {"success": False, "action": "process_payload", "event": "messages.update.mark_read", "error": "Partner not found"}

            # Mark message as read
            channel_member = self.env["discuss.channel.member"].search([
                ("channel_id", "=", channel_id),
                ("partner_id", "=", partner.id)
            ], limit=1)
            channel_member._mark_as_read(message.id, sync=True)

            _logger.info(
                f"action:process_payload event:message.update.read({evo_message_id}) partner:{partner} channel_membership:{channel_member}")

            return {
                "action": "process_payload",
                "event": "messages.update.mark_read",
                "success": True,
                "read_message": message.id,
                "read_partner": partner.parent_id.id
            }

        return {"success": False, "action": "process_payload", "event": "messages.update", "message": "Unhandled update type"}

    def _process_contacts_upsert(self, payload):
        '''Process contacts upsert events'''
        # Optimize by processing contacts in batches
        contacts = payload.get("data", [])
        processed_count = 0

        for contact in contacts:
            self.get_or_create_partner(contact, payload.get("instance"))
            processed_count += 1

            # Commit in batches to avoid long transactions
            if processed_count % 50 == 0:
                self.env.cr.commit()

        self.env.cr.commit()

        return {
            "success": True,
            "action": "process_contacts_upsert",
            "contacts": processed_count
        }

    def get_or_create_partner(self, contact, instance=None, update_profile_picture=True, create_contact=True):
        '''Get or create partner for WhatsApp contact'''
        if not contact.get("remoteJid"):
            return False

        whatsapp_number = contact.get("remoteJid").split("@")[0]

        # Format Brazilian mobile numbers
        if whatsapp_number.startswith("55") and len(whatsapp_number) == 12:
            whatsapp_number = f"{whatsapp_number[:4]}9{whatsapp_number[4:]}"

        # Search for existing partner
        partner = self.env['res.partner'].search([
            ('name', '=', "whatsapp"),
            ('phone', '=', whatsapp_number),
            ('parent_id', '!=', False),
        ], order='create_date desc')

        if not create_contact:
            return partner[0] if partner else False

        # Create partner if not found
        if not partner:
            # Create parent partner
            parent_partner = self.env['res.partner'].create({
                'name': contact.get("pushName") or whatsapp_number,
                'phone': whatsapp_number,
            })

            # Create contact partner
            partner_contact = self.env['res.partner'].create({
                'name': "whatsapp",
                'phone': whatsapp_number,
                'parent_id': parent_partner.id,
            })

            self.env.cr.commit()
            partner = partner_contact
        else:
            # We already have the partner
            partner_contact = partner[0]
            parent_partner = partner_contact.parent_id

        # Update profile picture if enabled
        if update_profile_picture and (not partner.image_128 or self.always_update_profile_picture):
            self._update_profile_picture(
                partner_contact, parent_partner, whatsapp_number, contact, instance)

        return partner_contact

    def _update_profile_picture(self, partner_contact, parent_partner, whatsapp_number, contact, instance):
        '''Update profile picture for the contact'''
        # First try to get profile URL from contact data
        image_url = contact.get("profilePicUrl")

        # If not available, fetch from API
        if not image_url and instance:
            try:
                headers = {'apikey': self.api_key}
                image_url_api = f"{self.url}/chat/fetchProfilePictureUrl/{instance}"
                response = requests.post(
                    image_url_api,
                    json={"number": whatsapp_number},
                    headers=headers,
                    timeout=5
                )

                if response.status_code == 200:
                    image_url = response.json().get("profilePictureUrl")
            except (requests.RequestException, ValueError) as e:
                _logger.error(f"Error fetching profile picture URL: {str(e)}")

        # Download and save profile picture
        if image_url:
            try:
                response = requests.get(image_url, timeout=5)
                if response.status_code == 200:
                    image_base64 = base64.b64encode(
                        response.content).decode('utf-8')
                    parent_partner.write({'image_1920': image_base64})
                    partner_contact.write({'image_128': image_base64})
                    self.env.cr.commit()
            except requests.RequestException as e:
                _logger.error(f"Error downloading profile picture: {str(e)}")

    def _format_message_before_send(self, message):
        body = message.body.unescape() if hasattr(
            message.body, 'unescape') else message.body

        # load template
        template_content = self.text_message_template
        if not template_content:
            template_content = "<p>{{message.author_id.name}}<br /><p>{{body}}</p></p>"

        # Define context explicitly
        context = {
            'message': message,
            'body': body,
        }

        # Create and render the Jinja2 template
        template = Template(template_content)
        body = template.render(context)

        # Convert HTML to WhatsApp formatting
        body = html_to_whatsapp(body)

        return body

    def _send_text_message(self, channel, message, headers):
        '''Send text message to WhatsApp'''

        body = self._format_message_before_send(message)

        payload = {
            "number": channel.evo_outgoing_destination,
            "text": body
        }
        if message.parent_id:
            quoted_message = self.env['mail.message'].search(
                [('id', '=', message.parent_id.id)], limit=1)
            quoted = None
            if quoted_message.evo_message_id:
                quoted = {
                    "key": {
                        "id": quoted_message.evo_message_id
                    },
                }
                payload["quoted"] = quoted

        url = f"{self.url}/message/sendText/{channel.evo_connector.name}"

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=10)

            if response.status_code == 201:
                sent_message_id = response.json().get("key", {}).get("id")
                message.write({"evo_message_id": sent_message_id})
                _logger.info(
                    f"action:outgo_message channel:{channel} message:{message} got message_id: {sent_message_id}")
                return response
            else:
                _logger.error(
                    f"Failed to send text message: {response.status_code} - {response.text}; Payload: {payload}")
                return False
        except requests.RequestException as e:
            _logger.error(f"Error sending text message: {str(e)}")
            return False

    def _send_attachments(self, channel, message, headers):
        '''Send message attachments to WhatsApp'''
        url = f"{self.url}/message/sendMedia/{channel.evo_connector.name}"

        for attachment in message.attachment_ids:
            # Determine media type
            if attachment.index_content in ["image", "video", "audio"]:
                mediatype = attachment.index_content
                filename = "audio.ogg" if mediatype == "audio" else attachment.name
            else:
                mediatype = "document"
                filename = attachment.name

            payload = {
                "number": channel.evo_outgoing_destination,
                "mediatype": mediatype,
                "mimetype": attachment.mimetype,
                "media": attachment.datas.decode('utf-8'),
                "fileName": filename
            }

            try:
                response = requests.post(
                    url, json=payload, headers=headers, timeout=30
                )
                if response.status_code == 201:
                    sent_message_id = response.json().get("key", {}).get("id")
                    attachment.write({
                        "evo_remote_message_id": sent_message_id,
                        "evo_local_message_id": message.id
                    })
                    _logger.info(
                        f"action:outgo_message.with_attachment message:{message} got message_id:{sent_message_id}")
                    return response
                else:
                    _logger.error(
                        f"Failed to send attachment: {response.status_code} - {response.text}")
                    return False
            except requests.RequestException as e:
                _logger.error(f"Error sending attachment: {str(e)}")
                return False



    def restart_instance(self):
        '''Get the status of the connector'''
        for record in self:
            headers = {'apikey': record.api_key}
            url = f"{record.url}/instance/restart/{record.name}"
            try:
                query = requests.post(url, headers=headers, timeout=10)
                if query.status_code == 404:
                    status = "not_found"
                else:
                    status = query.json().get("instance", {}).get("state", "closed")
            except requests.RequestException as e:
                _logger.error(f"Error getting status: {str(e)} connector {record}")
                status = "error"
        # wait for the instance to restart
        time.sleep(5)

    def logout_instance(self):
        '''Get the status of the connector'''
        for record in self:
            headers = {'apikey': record.api_key}
            url = f"{record.url}/instance/logout/{record.name}"
            try:
                query = requests.delete(url, headers=headers, timeout=10)
                if query.status_code == 404:
                    status = "not_found"
                else:
                    status = query.json().get("instance", {}).get("state", "closed")
            except requests.RequestException as e:
                _logger.error(f"Error getting status: {str(e)} connector {record}")
                status = "error"
        # wait for the instance to restart
        time.sleep(5)


    def outgo_message(self, channel, message):
        '''
        This method will receive the channel and message from the channel base automation
        with the below filter and code:
            
            domain filter:
            [("evo_connector", "!=", False)]

            code:
last_message = record.message_ids[0]
_logger.info(f"automation_base: running outgo message ({last_message}) to {record}")
record.evo_connector.outgo_message(channel=record, message=last_message)
        '''
        if not self.enabled:
            # improve log saying channel and message
            _logger.warning(
                f"action:outgo_message connector {self} is not active"
            )
            return
        if not channel or not message:
            _logger.error("Missing channel or message in outgo_message")
            return

        headers = {'apikey': self.api_key}

        # Send text message
        if message.body:
            sent_message = self._send_text_message(channel, message, headers)
            sent_message_id = sent_message.json().get("key", {}).get("id")

        # Send attachments
        if message.attachment_ids:
            sent_message = self._send_attachments(channel, message, headers)
            sent_message_id = sent_message.json().get("key", {}).get("id")
        message.write({
            "evo_message_id": sent_message_id
        })
        self.env.cr.commit()

    def outgo_reaction(self, channel, message, reaction):
        '''
            # DOMAIN FILTER FOR BASE AUTOMATION
            [("message_id.evo_message_id", "!=", "")]
            AUTOMATION BASE CODE FOR REACTION
channel = env['discuss.channel'].search([('id', '=', record.message_id.res_id)])
channel.evo_connector.outgo_reaction(channel, record.message_id, record)
_logger.info(f"automation_base: connector:{channel.evo_connector} channel:{channel} reaction {record} to message {record.message_id}")
        '''
        if not self.enabled:
            # improve log saying channel and message
            _logger.warning(
                f"action:outgo_message connector {self} is not active"
            )
            return
        if not channel or not message or not reaction:
            _logger.error(
                f"Missing channel, message or reaction in outgo_reaction"
            )
            return

        headers = {'apikey': self.api_key}

        payload = {
            "key": {
                "remoteJid": channel.evo_outgoing_destination,
                "fromMe": message.evo_message_id != message.message_id,
                "id": message.evo_message_id
            },
            "reaction": reaction.content
        }

        url = f"{self.url}/message/sendReaction/{channel.evo_connector.name}"

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=10)
            _logger.info(
                f"action:outgo_reaction channel:{channel} reaction:{reaction} payload:{payload} response:{response.status_code}")
        except requests.RequestException as e:
            _logger.error(f"Error sending reaction: {str(e)}")


class EvoSocialNetworkeType(models.Model):
    _name = 'evo_social_network_type'
    _description = 'Social Network Types'

    name = fields.Char(required=True)


def html_to_whatsapp(html_text):
    """
    Converts basic HTML to WhatsApp formatting.
    """
    if not html_text:
        return ""

    # Basic formatting
    conversions = [
        (r'<b>(.*?)</b>', r'*\1*'),
        (r'<strong>(.*?)</strong>', r'*\1*'),
        (r'<i>(.*?)</i>', r'_\1_'),
        (r'<em>(.*?)</em>', r'_\1_'),
        (r'<s>(.*?)</s>', r'~\1~'),
        (r'<strike>(.*?)</strike>', r'~\1~'),
        (r'<del>(.*?)</del>', r'~\1~'),
        (r'<u>(.*?)</u>', r'_\1_'),
        (r'<br\s*/?>', '\n'),
        (r'<p>(.*?)</p>', r'\1\n\n')
    ]

    text = html_text
    for pattern, replacement in conversions:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Remove remaining HTML tags
    text = re.sub(r'<[^>]*>', '', text)

    # Decode HTML entities
    text = html.unescape(text)

    return text.strip()


# # create a transient model for ConnectorStatus
# # it will have the status and possible the qrcode to connect
# class EvoConnectorStatus(models.TransientModel):
#     _name = 'evo_connector_status'
#     _description = 'Evo Connector Status'

#     status = fields.Char(string='Status', readonly=True)
#     qrcode = fields.Binary(string='QR Code', readonly=True)
#     qrcode_filename = fields.Char(string='QR Code Filename', readonly=True)

#     def action_close(self):
#         self.ensure_one()
#         return {'type': 'ir.actions.act_window_close'}


class HtmlDisplay(models.TransientModel):
    _name = 'evo_connector_status'
    html_content = fields.Html('HTML Content', readonly=True)