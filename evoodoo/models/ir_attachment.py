from odoo import api, fields, models, _

class IrAttachment(models.Model):
    """ Chat Session
        Reprensenting a conversation between users.
        It extends the base method for anonymous usage.
    """
    _inherit = ['ir.attachment']
    # To use when user react or reply to a MediaMessa
    evo_remote_message_id = fields.Char(
        string="Evo Remote Message ID"
    )
    # To store the message that originated this attachment"
    evo_local_message_id = fields.Integer(
        string="Evo Local Message ID"
    )