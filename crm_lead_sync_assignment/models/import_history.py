# -*- coding: utf-8 -*-
from odoo import models, fields, api


class CrmLeadImportHistory(models.Model):
    _name = 'crm.lead.import.history'
    _description = 'CRM Lead Import & Distribution History'
    _order = 'import_date desc, id desc'

    name = fields.Char(string="Import Reference", required=True, default=lambda self: self.env['ir.sequence'].next_by_code('crm.lead.import.history') or 'IMPORT-HIST')
    import_date = fields.Datetime(string="Import Date", default=fields.Datetime.now, required=True)
    user_id = fields.Many2one('res.users', string="Imported By", default=lambda self: self.env.user, required=True)
    total_leads = fields.Integer(string="Total Leads Selected", default=0)
    imported_count = fields.Integer(string="Successfully Imported", default=0)
    duplicates_count = fields.Integer(string="Duplicates Skipped", default=0)
    skipped_count = fields.Integer(string="Other Skipped", default=0)
    assignment_summary = fields.Text(string="Assignment Summary")
    line_ids = fields.One2many('crm.lead.import.history.line', 'history_id', string="Allocation Details")


class CrmLeadImportHistoryLine(models.Model):
    _name = 'crm.lead.import.history.line'
    _description = 'CRM Lead Import History Allocation Line'

    history_id = fields.Many2one('crm.lead.import.history', string="Import History", ondelete='cascade')
    user_id = fields.Many2one('res.users', string="Salesperson", required=True)
    allocated_count = fields.Integer(string="Allocated Lead Count", required=True, default=0)
