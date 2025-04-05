# -*- coding: utf-8 -*-
{
    'name': "evo",

    'summary': "WhatsApp and Other channels integrated in Odoo",

    'description': """
    Odoo and Evolution integration done right. Whatsapp, Instagram, Facebook
    """,

    'author': "Duda Nogueira",
    'website': "https://www.dudatende.com.br",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'marketing',
    'version': '0.1',
    'application': True,
    'installable': True,

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'base_automation'],

    # always loaded
    'data': [
        #'security/security.xml',
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        # initial base_automation
        'datas/base_automation.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

