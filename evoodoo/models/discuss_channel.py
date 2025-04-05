from odoo import api, fields, models, _

class DiscussChannel(models.Model):
    """ Chat Session
        Reprensenting a conversation between users.
        It extends the base method for anonymous usage.
    """
    _inherit = ['discuss.channel']

    evo_connector = fields.Many2one(
        comodel_name='evo_connector', 
        string='Connector', 
        index='btree_not_null', 
        auto_join=True, ondelete='set null',
    )
    evo_outgoing_destination = fields.Char(
        string="Evo Outgoing Destination for this channel"
    )