# -*- coding: utf-8 -*-
{
    'name': 'Voiso Click-to-Call Telephony Integration',
    'version': '17.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Voiso API v4 Click-to-Call integration for Odoo CRM & Contacts with auto-user mapping.',
    'description': """
Voiso Click-to-Call Telephony Integration (Odoo 17)
===================================================
Features:
- Seamless Click-to-Call integration with Voiso API v4.
- Works on Custom CRM Leads (custom.crm.lead), standard Odoo Leads (crm.lead), and Contacts (res.partner).
- Automatic Voiso User ID mapping for Odoo users based on Name/Email matching from Voiso GET /users API.
- Phone number normalization (preserves country code, cleans spaces and special characters).
- Secure backend API requests (API keys are never exposed to browser JS).
- Automatic logging of Call IDs in Chatter (mail.thread).
    """,
    'author': 'Custom Odoo Development Team',
    'website': 'https://wekotrade.voiso.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'crm',
        'crm_lead_sync_assignment',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/res_users_views.xml',
        'views/custom_crm_lead_views.xml',
        'views/crm_lead_views.xml',
        'views/res_partner_views.xml',
        'wizard/voiso_active_call_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
