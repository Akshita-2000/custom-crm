# -*- coding: utf-8 -*-
from odoo import models, fields, api


class CrmLeadSyncLog(models.Model):
    _name = 'crm.lead.sync.log'
    _description = 'CRM Lead Synchronization Log'
    _order = 'sync_date desc, id desc'

    name = fields.Char(string="Log Reference", required=True, default=lambda self: self.env['ir.sequence'].next_by_code('crm.lead.sync.log') or 'SYNC-LOG')
    sync_date = fields.Datetime(string="Sync Date & Time", default=fields.Datetime.now, required=True)
    status = fields.Selection([
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('failed', 'Failed')
    ], string="Status", default='success', required=True)
    sheet1_records = fields.Integer(string="Sheet 1 Records", default=0)
    sheet2_records = fields.Integer(string="Sheet 2 Records", default=0)
    duplicates_found = fields.Integer(string="Duplicates Found", default=0)
    inserted_records = fields.Integer(string="Inserted Records", default=0)
    log_details = fields.Text(string="Log Details")
    triggered_by = fields.Selection([
        ('cron', 'Scheduled Action (Cron)'),
        ('manual', 'Manual Trigger')
    ], string="Triggered By", default='cron')
