from odoo import fields, models


class MailMessage(models.Model):
    """Chat Session
    Reprensenting a conversation between users.
    It extends the base method for anonymous usage.
    """

    _inherit = "mail.message"
    discuss_hub_message_id = fields.Char(string="Discuss Hub Message ID", index=True)
