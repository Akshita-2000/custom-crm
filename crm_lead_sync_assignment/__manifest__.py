# -*- coding: utf-8 -*-
{
    'name': 'CRM Lead Synchronization & Standalone Auto Assignment',
    'version': '17.0.3.0.0',
    'category': 'Sales/CRM',
    'summary': 'Standalone CRM with automated Google Sheets lead sync, deduplication, and employee salesperson distribution.',
    'description': """
CRM Lead Synchronization & Standalone Auto Assignment (Odoo 17)
===============================================================
Key Features:
- Standalone CRM Pipeline (custom.crm.lead) with Employee & User assignment.
- Synchronize leads from multiple Google Sheets via Google Sheets API or Zero-Config Public CSV.
- Scheduled action (Cron job running every 5 minutes).
- Master Lead repository to store raw and deduplicated leads.
- Automatic Duplicate Detection (Phone priority, Email fallback).
- Interactive Lead Import Wizard for CRM Managers to distribute leads to Employees (hr.employee).
- Kanban Pipeline views with drag-and-drop stages (New, Contacted, In Progress, Won, Lost).
- Audit history logging for every import operation and synchronization batch.
    """,
    'author': 'Custom Odoo Development Team',
    'website': 'https://www.odoo.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'sales_team',
        'hr',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/cron_data.xml',
        'views/res_config_settings_views.xml',
        'views/master_lead_views.xml',
        'views/custom_crm_lead_views.xml',
        'views/sync_log_views.xml',
        'views/import_history_views.xml',
        'wizard/lead_import_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
