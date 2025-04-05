from odoo import api, fields, models, _

class Message(models.Model):
    """ Chat Session
        Reprensenting a conversation between users.
        It extends the base method for anonymous usage.
    """
    _inherit = ['mail.message']
    evo_message_id = fields.Char(
        string="Evo Message ID"
    )