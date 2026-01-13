import importlib
import logging
import os
import sys
import uuid

from odoo import api, fields, models

from . import utils

_logger = logging.getLogger(__name__)


class DiscussHubConnector(models.Model):
    """
    TODO: allow templatable channel name
    TODO: implement optional composing
    TODO: option to ignore groups
    TODO: option to grab all participants of a group and show the participant
    name and photo instead
    of the participant name prepended
    TODO: something with statusbroadcast may be sending status as the remotejid
     at some point.
    TODO: Allow selection of partners to ignore
    TODO; auto add base automations
    """

    _name = "discuss_hub.connector"
    _description = "Discuss Hub Connector"

    enabled = fields.Boolean(default=True)
    import_contacts = fields.Boolean(default=True)
    name = fields.Char(required=True)
    uuid = fields.Char(
        required=True,
        # Fixed: Use function call to avoid evaluation at import time
        default=lambda self: str(uuid.uuid4()),
    )
    description = fields.Text()
    type = fields.Selection(
        [
            ("base", "Base Plugin"),
            ("example", "Example Plugin"),
            ("evolution", "Evolution"),
            ("notificame", "NotificaMe"),
            ("whatsapp_cloud", "Whatsapp Cloud"),
        ],
        default="evolution",
        required=True,
    )
    create_user_for_visitor = fields.Selection(
        selection=[
            ("none", "Do not Create User"),
            ("portal", "Create Portal User"),
            ("public", "Create Public User"),
        ],
        string="Create User for Visitor",
        default="none",
        help=(
            "Define if a user should be created for the visitor and what type of "
            "user will be created."
        ),
    )
    url = fields.Char(required=False)
    api_key = fields.Char(required=False)
    manager_channel = fields.Many2many(comodel_name="discuss.channel")
    automatic_added_partners = fields.Many2many(comodel_name="res.partner")
    automatic_added_teams = fields.Many2many(comodel_name="discuss_hub.routing_team")
    # Configuration options
    partner_contact_name = fields.Char(required=True, default="whatsapp")
    partner_contact_field = fields.Char(required=True, default="phone")
    reopen_last_archived_channel = fields.Boolean(default=False)
    always_update_profile_picture = fields.Boolean(default=False)
    show_read_receipts = fields.Boolean(default=True)
    notify_reactions = fields.Boolean(default=True)
    reproduce_notification_messages = fields.Boolean(
        default=False,
        help=(
            "If enabled, notification messages (system messages, automated messages, "
            "etc.) will be sent to the external channel. When disabled, only "
            "regular messages (comments) will be sent."
        ),
    )
    default_admin_partner_id = fields.Many2one(
        "res.partner",
        string="Default Admin Partner",
        default=lambda self: self.env["res.partner"].search([("id", "=", 1)], limit=1),
    )
    text_message_template = fields.Text(
        default="<p><b>[{{message.author_id.name}}]</b><br /><p>{{body}}</p></p>",
    )
    last_message_date = fields.Datetime(compute="_compute_last_message", store=False)
    channels_total = fields.Integer(
        string="Total Channels", compute="_compute_channels_total", store=False
    )
    # TODO: implement ignore partners
    ignore_partners = fields.Many2many(
        comodel_name="res.partner",
        help="Partners to ignore in the connector",
        relation="discuss_hub_connector_ignore_partners",
    )
    status = fields.Selection(
        [
            ("open", "Open"),
            ("closed", "Closed"),
            ("qr_code", "QR Code"),
            ("not_found", "Not Found"),
            ("unauthorized", "Unauthorized"),
            ("error", "Error"),
        ],
        compute="_compute_status",
        default="closed",
        required=False,
        store=False,
    )
    # EVOLUTION SPECIFIC PROPERTIES
    evolution_allow_broadcast_messages = fields.Boolean(
        default=True, string="Allow Status Broadcast Messages"
    )
    evolution_contact_queue = fields.Json()
    evolution_contacts_storage_count = fields.Integer(
        string="Contacts Storage Count",
        help="Number of contacts stored to sync in the connector",
        compute="_compute_evolution_sync_queue",
    )
    # WHATSAPP CLOUD SPECIFIC PROPERTIES
    verify_token = fields.Char(
        help="The challenge code for WhatsApp Cloud verification",
    )
    whatsapp_cloud_reengage_template = fields.Char(
        help="Template to use for re-engaging with users on after chat window",
    )
    # QR CODE BASE CONNECTORS
    qr_code_base64 = fields.Text(compute="_compute_status", store=False)

    def action_send_msg(self):
        """This function is called when the user clicks the
        'Send WhatsApp Message' button on a partner's form view. It opens a
         new wizard to compose and send a WhatsApp message."""
        return {
            "type": "ir.actions.act_window",
            "name": "Whatsapp Message",
            "res_model": "whatsapp.send.message",
            "target": "new",
            "view_mode": "form",
            "view_type": "form",
            "context": {"default_user_id": self.id},
        }

    def get_plugin(self):
        """Get the plugin class and instantiate for usage"""
        plugin_name = self.type
        # Dynamically import the module
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        module_path = f"plugins.{plugin_name}"  # adjust if your path is deeper

        # Import the module
        module = importlib.import_module(module_path)
        PluginClass = module.Plugin
        # Use it
        plugin_instance = PluginClass(self)
        # add utils
        plugin_instance.utils = utils
        return plugin_instance

    #
    # UI METHODS
    #
    # TODO: move this to plugin
    def action_open_start(self):
        """Opens an start content in a new wizard."""
        self.ensure_one()

        status = self.get_status()
        html_content = f"""
            <html>
            <head>
                <title>Connector Status</title>
            </head>
            <body>
                <h1>{self.name}</h1>
                <p>Status: {status.get("status")}</p>
                <p>QR Code:
                <img style="background-color:#71639e;" src="{status.get("qrcode")}" />
                </p>
            </body>
            </html>
        """

        return {
            "type": "ir.actions.act_window",
            "name": "Connector Status",
            "res_model": "discuss_hub.connector.status",
            "view_mode": "form",
            "target": "new",
            "context": {"default_html_content": html_content},
        }

    def _compute_last_message(self):
        for connector in self:
            last_message = self.env["discuss.channel"].search(
                [
                    ("discuss_hub_connector", "=", connector.id),
                ],
                order="write_date desc",
                limit=1,
            )
            connector.last_message_date = (
                last_message.write_date if last_message else None
            )

    def _compute_evolution_sync_queue(self):
        """Compute the number of contacts to sync in the evolution connector"""
        for connector in self:
            if connector.type == "evolution":
                # Get the count of contacts to sync
                connector.evolution_contacts_storage_count = len(
                    self.evolution_contact_queue
                    if connector.evolution_contact_queue
                    else []
                )
            else:
                connector.evolution_contacts_storage_count = 0

    def _compute_channels_total(self):
        for connector in self:
            connector.channels_total = self.env["discuss.channel"].search_count(
                [
                    ("discuss_hub_connector", "=", connector.id),
                ]
            )

    @api.depends("api_key", "url", "name")
    def _compute_status(self):
        for connector in self:
            status = connector.get_status()
            if status:
                _logger.debug("Connector status: %s", status)
                connector.status = status.get("status", "not_found")
                connector.qr_code_base64 = status.get("qr_code_base64", None)

    def open_status_modal(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Status Details",
            "view_mode": "form",
            "res_model": "discuss_hub.connector",
            "res_id": self.id,
            "target": "new",
        }

    def get_status(self):
        """Get the status of the connector"""
        plugin = self.get_plugin()
        return plugin.get_status()

    #
    # CONTROLLERS / BASE CLASS
    #
    def process_payload(self, payload):
        """
        Channel the incoming payload to the appropriate plugin handlers
        """
        plugin = self.get_plugin()
        return plugin.process_payload(payload)

    def restart_instance(self):
        """RESTART connector"""
        for record in self:
            _logger.info(f"action:restart_instance connector {record}")
            plugin = self.get_plugin()
            plugin.restart_instance()

    def logout_instance(self):
        """logout instance"""
        for record in self:
            _logger.info(f"action:logout_instance connector {record}")
            plugin = self.get_plugin()
            plugin.logout_instance()

    def outgo_message(self, channel, message):
        """
        This method will receive the channel and message
        from the channel base automation and pass it over to the connector
        """
        # Debug logging
        _logger.info(
            f"action:outgo_message called for connector:{self.name} "
            f"message_id:{message.id if message else 'None'} "
            f"message_type:{message.message_type if message else 'None'} "
            f"reproduce_notification_messages:{self.reproduce_notification_messages}"
        )
        
        if not self.enabled:
            _logger.warning(
                f"action:outgo_message connector {self.name} ID {self.id} "
                + "is not active or not found "
                f"for channel {channel.name if channel else 'None'} and message "
                f"{message.id if message else 'None'}"
            )
            return
        
        # Check if we should skip notification messages
        if (
            not self.reproduce_notification_messages
            and message.message_type == "notification"
        ):
            _logger.info(
                f"action:outgo_message SKIPPING notification message_id:{message.id} "
                f"message_type:{message.message_type} "
                f"connector:{self.name} (reproduce_notification_messages=False)"
            )
            return
        
        _logger.info(
            f"action:outgo_message SENDING message_id:{message.id} "
            f"message_type:{message.message_type} to connector:{self.name}"
        )
        
        plugin = self.get_plugin()
        return plugin.outgo_message(channel, message)

    def outgo_reaction(self, channel, message, reaction):
        """
        # DOMAIN FILTER FOR BASE AUTOMATION
        [("message_id.discuss_hub_message_id", "!=", "")]
        AUTOMATION BASE CODE FOR REACTION
        the code is available as a data import
        """
        if not self.enabled:
            _logger.warning(
                f"action:outgo_message.reaction connector {self} inactive or not found "
                f"for channel {channel.name if channel else 'None'} and message "
                f"{message.id if message else 'None'}"
            )
            return
        if not channel or not message or not reaction:
            _logger.error("Missing channel, message or reaction in outgo_reaction")
            return
        plugin = self.get_plugin()
        return plugin.outgo_reaction(channel, message, reaction)

    def sync_contacts(self):
        plugin = self.get_plugin()
        plugin.sync_contacts()

    # Routing

    def get_initial_routed_partners(self, connector=None):
        """
        Get the initial routed partners for a channel.
        This is used to determine which partners should be added to the channel
        when it is created.
        """
        partners = []
        for p in self.automatic_added_partners:
            partners.append(p)
        for team in self.automatic_added_teams:
            new_member = team.get_next_team_member(connector=connector)
            if new_member:
                partners.append(new_member)
        _logger.info(
            f"action:get_initial_routed_partners connector {self.name} "
            f"for channel {connector.name if connector else 'None'}: {partners}"
        )
        return set(partners)


class DiscussHubSocialNetworkeType(models.Model):
    _name = "discuss_hub.social_network_type"
    _description = "Social Network Types"

    name = fields.Char(required=True)
    # TODO ADD IMAGE TO SHOW ON CHANNEL


class DiscussHubConnectorStatus(models.TransientModel):
    _name = "discuss_hub.connector.status"
    _description = "Discuss Hub Connector Status"
    html_content = fields.Html("HTML Content", readonly=True)
