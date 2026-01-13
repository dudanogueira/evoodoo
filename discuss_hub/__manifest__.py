{
    "name": "discuss_hub",
    "summary": "Third Party Messsage integration for Odoo's Discuss Channel",
    "author": "Discuss Hub Community",
    "website": "https://github.com/discusshub/discuss_hub",
    "category": "marketing",
    "version": "19.0.0.0.11",
    "license": "AGPL-3",
    "application": True,
    "installable": True,
    # any module necessary for this one to work correctly
    "depends": ["base", "mail", "crm"],
    # always loaded
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/views.xml",
        "views/templates.xml",
        "views/res_partner_view.xml",
        # wizards
        "wizard/mail_discuss_channel_forward.xml",
        "wizard/mail_discuss_channel_archive.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "discuss_hub/static/src/js/discuss_channel_actions.esm.js",
        ],
    },
    # only loaded in demonstration mode
    "demo": [
        "demo/demo.xml",
    ],
}
