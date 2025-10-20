import base64
import logging
import uuid
from urllib.parse import urljoin, urlparse

import requests
from markupsafe import Markup

from odoo import fields, models
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class DiscussHubBotManager(models.Model):
    """
    base automation on model: Discuss Channel, event: incoming message
    domain: [("channel_partner_ids.bot", "!=", False)]
    partners_with_bot = record.channel_partner_ids.filtered(lambda p: p.bot)
    last_message = record.message_ids[0]
    for partner in partners_with_bot:
        partner.bot.outgo(last_message)
    """

    _name = "discuss_hub.bot_manager"
    _description = "Discuss Hub Bot Manager"

    active = fields.Boolean(
        default=True,
        help="Indicates whether the routing team is active.",
    )
    uuid = fields.Char(
        required=True,
        # Fixed: Use function call to avoid evaluation at import time
        default=lambda self: str(uuid.uuid4()),
    )
    partner = fields.One2many(
        comodel_name="res.partner",
        string="partner",
        required=True,
        help="User associated with the bot manager.",
        inverse_name="bot",
    )
    bot_type = fields.Selection(
        selection=[
            ("generic", "Generic"),
            ("typebot", "Typebot"),
        ],
        default="generic",
        required=True,
        help="Type of the bot.",
    )
    bot_url = fields.Char(
        required=True,
        help="URL of the bot.",
    )
    bot_api_key = fields.Char(
        required=True,
        help="API key for the bot.",
    )
    bot_url_timeout = fields.Integer(
        default=360, help="Timeout for the bot URL in seconds.", required=True
    )
    on_error_message = fields.Text(
        default="An error occurred while processing your request. "
        + "Please try again later.",
        help="Message to send when an error occurs while processing a request.",
    )

    def generic_handle(self, message, channel, partner):
        timed_out = False
        message_audio_base64 = None
        attachment_id = None
        request_data = None
        
        # Check for audio attachments
        if message.attachment_ids:
            for attachment in message.attachment_ids:
                if attachment.mimetype and attachment.mimetype.startswith("audio/"):
                    message_audio_base64 = attachment.datas.decode("utf-8") if isinstance(attachment.datas, bytes) else attachment.datas
                    attachment_id = attachment.id
                    break
        
        try:
            request_data = requests.post(
                self.bot_url,
                json={
                    "message_body": message.body,
                    "message_author_name": message.author_id.name,
                    "message_author_id": message.author_id.id,
                    "message_audio_base64": message_audio_base64,
                    "attachment_id": attachment_id,
                    "channel_id": channel.id,
                },
                timeout=self.bot_url_timeout,  # Set a timeout for the request
            )
        except requests.Timeout as e:
            _logger.error(f"Timeout while sending message to bot {self.bot_url}: {e}")
            timed_out = True

        if (
            timed_out
            or not request_data
            or request_data.status_code != 200
            or not request_data.content
        ):
            if request_data:
                _logger.error(
                    f"Failed to send message to bot {self}: {request_data.text}"
                )
            # sending default error message
            channel.with_context(discuss_hub_skip_bot=True).message_post(
                body=self.on_error_message,
                author_id=partner.id,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
            # Note: outgo_message is automatically called by message_post() hook
            # if the author has a system user (see discuss_channel.py)
            return True

        # Parse response data
        try:
            response_data = request_data.json()
        except ValueError as e:
            _logger.error(f"Failed to parse JSON response from bot {self}: {e}")
            return False

        # Normalize response to list format
        if isinstance(response_data, str):
            # If response is a simple string, convert to expected format
            response_data = [{"text": response_data}]
        elif isinstance(response_data, dict):
            # If response is a single dict, wrap in list
            response_data = [response_data]
        elif not isinstance(response_data, list):
            _logger.error(
                f"Unexpected response format from bot {self}: {type(response_data)}"
            )
            return False

        # for each message
        for received_message in response_data:
            # Ensure received_message is a dict
            if not isinstance(received_message, dict):
                _logger.warning(
                    f"Skipping non-dict message from bot {self}: {received_message}"
                )
                continue

            attachments = []
            # go thru each type, except text
            for content_type, content in received_message.items():
                if content_type != "text":
                    if content_type == "audio":
                        content_type = "audio.mp3"
                    elif content_type == "video":
                        content_type = "video.mp4"
                    elif content_type == "pdf":
                        content_type = "application.pdf"
                    try:
                        decoded_data = base64.b64decode(content)
                        attachments.append((content_type, decoded_data))
                    except ValueError as e:
                        _logger.warning(
                            f"""Failed to decode base64 content
                            {content_type}: {e}."""
                        )
                        pass
            new_message = channel.with_context(discuss_hub_skip_bot=True).message_post(
                body=received_message.get("text", ""),
                author_id=partner.id,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                attachments=attachments,
            )
            # Note: outgo_message is automatically called by message_post() hook
            # if the author has a system user (see discuss_channel.py)
            _logger.info(f"Bot message created: {new_message.id}")
        return True

    def typebot_get_latest_session(self, channel):
        latest_session = self.env["discuss_hub.bot_manager.session"].search(
            [
                ("bot_manager_id", "=", self.id),
                ("channel_id", "=", channel.id),
                ("expired", "=", False),
            ],
            order="id desc",
            limit=1,
        )
        return latest_session

    def typebot_start_chat(self, channel, payload):
        # add the necessary sub path
        # bot_url should be like: http://localhost:8081/api/v1/typebots/odoo/
        logging.info(
            f"BOTMANAGER - Starting chat with bot {self.id} and payload {payload}"
        )
        url = urljoin(self.bot_url, "startChat")
        request_data = requests.post(
            url,
            headers={"Authorization": "Bearer {self.bot_api_key}"},
            json=payload,
            timeout=self.bot_url_timeout,
        )
        return request_data

    def typebot_register_new_session(self, channel, session_id):
        # update all active sessions for the channel to expired
        self.env["discuss_hub.bot_manager.session"].search(
            [
                ("bot_manager_id", "=", self.id),
                ("channel_id", "=", channel.id),
                ("expired", "=", False),
            ]
        ).write({"expired": True})
        # create a new session
        new_session = self.env["discuss_hub.bot_manager.session"].create(
            {
                "bot_manager_id": self.id,
                "channel_id": channel.id,
                "session_id": session_id,
            }
        )
        return new_session

    def typebot_continue_chat(self, channel, session_id, payload):
        url = self.bot_url
        # Parse the URL
        parsed = urlparse(url)
        # clear the payload
        del payload["prefilledVariables"]
        # Extract base path up to /api/v1/
        # (split the path and rejoin only the first 3 segments)
        base_path = "/".join(parsed.path.strip("/").split("/")[:2])

        # Build new path
        new_path = f"{base_path}/sessions/{session_id}/continueChat"

        # Construct full URL
        new_url = f"{parsed.scheme}://{parsed.netloc}/{new_path}"
        request_data = requests.post(
            new_url,
            headers={"Authorization": "Bearer {self.bot_api_key}"},
            json=payload,
            timeout=self.bot_url_timeout,
        )
        logging.info(
            f"CONTINUING CHAT FOR {channel.id} bot {self.id} session: {session_id}"
            + f" with payload {payload}. Got response: {request_data.json()}"
        )
        return request_data

    def outgo(self, channel, partner):
        """
        Send a message to the bot.
        :param message: The message to send.
        :return: True if the message was sent successfully, False otherwise.
        """
        message = channel.message_ids[0]
        # Simulate sending a message to the bot
        _logger.info(
            f"Sending message to bot({self.bot_type}) {self.bot_url}: "
            f"{message} at {channel}"
        )
        message_audio_base64 = None
        attachment_id = None
        if message.attachment_ids and "audio" in message.attachment_ids[0].mimetype:
            attachment_id = message.attachment_ids[0].id
            message_audio_base64 = message.attachment_ids[0].datas.decode("utf-8")

        if self.bot_type == "generic":
            generic_handle = self.generic_handle(message, channel, partner)
            _logger.info(
                f"Message to bot({self.bot_type}) {self.bot_url}: "
                f"{message} at {channel} was sent: {generic_handle}"
            )
            _logger.info(f"Handling bot type {self.bot_type} for bot {self.id}")
            return True
        if self.bot_type == "typebot":
            # Handle typebot specific logic here
            # try to get the latest session for this channel
            # for this bot, and not expired
            session_id = None
            payload = {
                "message": {"type": "text", "text": html2plaintext(str(message.body))},
                "prefilledVariables": {
                    "message_body": html2plaintext(str(message.body)),
                    "message_author_name": message.author_id.name,
                    "message_author_id": message.author_id.id,
                    "message_audio_base64": message_audio_base64,
                    "attachment_id": attachment_id,
                    "channel_id": channel.id,
                },
                "textBubbleContentFormat": "markdown",
            }
            logging.info(
                f"Getting Latest session for bot {self} at channel {channel.id}..."
            )
            latest_session = self.typebot_get_latest_session(channel)
            new_session = None
            messages = []
            # no last session
            if not latest_session:
                logging.info(
                    f"BOTMANAGER: Session for {self} not found, "
                    + f"creating with payload {payload}"
                )
                try:
                    new_session = self.typebot_start_chat(channel, payload)
                    if new_session.status_code != 200 or not new_session.content:
                        logging.warning(
                            "BOTMANAGER: Failed to create "
                            + f"session for {self}: {new_session.json()}"
                        )
                        return False
                    else:
                        logging.info(
                            f"BOTMANAGER: new session for {self}: {new_session.json()}"
                        )
                        session_id = new_session.json().get("sessionId")
                        messages = new_session.json().get("messages", [])
                        self.typebot_register_new_session(channel, session_id)
                except Exception as e:
                    logging.error(
                        f"BOTMANAGER: Failed to create session for {self}: {e}"
                    )
            else:
                logging.info(
                    "BOTMANAGER: Found existing session for bot "
                    + f"{self.id}: {latest_session.session_id}. Continuing chat"
                )
                session_id = latest_session.session_id
                # previous session found, try to continue chat
                continue_chat = self.typebot_continue_chat(channel, session_id, payload)
                if continue_chat.ok:
                    messages = continue_chat.json().get("messages", [])
                # session is invalid, create new one
                elif continue_chat.status_code == 404:
                    new_session = self.typebot_start_chat(channel, payload)
                    messages = new_session.json().get("messages", [])
                    session_id = new_session.json().get("sessionId")
                    self.typebot_register_new_session(channel, session_id)
                else:
                    logging.warning(
                        f"BOTMANAGER: Failed to continue {self}: {continue_chat.json()}"
                    )

            for message in messages:
                body = ""
                attachments = []
                logging.info(
                    f"BOTMANAGER {self.id}, session_id:{session_id}, "
                    + f"Message from bot: {message}"
                )
                if message.get("type") == "text":
                    body = message.get("content", {}).get("markdown")
                # TODO: try to cache those files as they will be repeating
                if message.get("type") in ["image", "audio", "video", "file"]:
                    url = message.get("content", {}).get("url")
                    query = requests.get(url, timeout=self.bot_url_timeout)
                    if query.ok:
                        content_type = query.headers["Content-Type"]
                        if message.get("type") == "audio":
                            content_type = "audio.mp3"
                        if message.get("type") == "video":
                            content_type = "video.mp4"
                        attachments.append((content_type, query.content))
                    else:
                        logging.warning(
                            f"BOTMANAGER {self.id}, session_id:{session_id}, "
                            + f"Failed to download media: {query.status_code}"
                        )
                # handle typebot markdown. first, replace \n to <br>
                body = body.replace("\n", "<br>")
                channel.with_context(discuss_hub_skip_bot=True).message_post(
                    body=Markup(body),
                    author_id=partner.id,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                    attachments=attachments,
                )
                # Note: outgo_message is automatically called by message_post() hook
                # if the author has a system user (see discuss_channel.py)
        return True

    def process_payload(self, incoming_payload):
        """Process routing payload using DiscussHubRoutingManager"""
        try:
            # Extract required fields from payload
            action = incoming_payload.get("action")
            channel_id = incoming_payload.get("channel_id")
            team_id = incoming_payload.get("team_id")
            agent_id = incoming_payload.get("agent_id")
            note = incoming_payload.get("note")

            # Validate required fields
            if not action or not channel_id:
                return {"error": "Missing required fields: action, channel_id"}

            if action == "forward":
                # Get the channel
                channel = self.env["discuss.channel"].browse(channel_id)
                if not channel.exists():
                    return {"error": f"Channel {channel_id} not found"}

                # check if team is active
                if team_id:
                    team = self.env["discuss_hub.routing_team"].browse(team_id)
                    if not team.exists() or not team.active:
                        return {"error": f"Team {team_id} is not active or not found"}

                # Create transient routing manager record
                routing_manager = self.env["discuss_hub.routing_manager"].create(
                    {
                        "channel_ids": [(6, 0, [channel_id])],
                        "team": team_id if team_id else False,
                        "agent": agent_id if agent_id else False,
                        "note": note or None,
                    }
                )

                # Execute the forward action
                result = routing_manager.action_forward(from_partner=self.partner)

                return {
                    "success": True,
                    "action": action,
                    "channel_id": channel_id,
                    "result": result,
                }
            else:
                return {"error": f"Unknown action: {action}"}

        except Exception:
            raise
            # return {"error": str(e)}


class DiscussHubBotManagerSession(models.Model):
    """
    This model will host the session information for bot session.
    Some bot integrations will first get a bot session, and will use it.
    """

    _name = "discuss_hub.bot_manager.session"
    _description = "Discuss Hub Bot Manager Session"

    bot_manager_id = fields.Many2one(
        comodel_name="discuss_hub.bot_manager",
        string="Bot Manager",
        required=True,
        ondelete="cascade",
        help="Bot manager associated with the session.",
    )
    channel_id = fields.Many2one(
        comodel_name="discuss.channel",  # existing Odoo discuss channel model
        string="Channel",
        required=True,
        ondelete="cascade",
        help="Channel associated with the session.",
    )
    session_id = fields.Char(
        string="Session ID",
        required=True,
        index=True,
        help="Unique identifier for the session.",
    )
    expired = fields.Boolean(
        string="Expired or Inactive",
        default=False,
        help="Indicates if the session has expired.",
    )
