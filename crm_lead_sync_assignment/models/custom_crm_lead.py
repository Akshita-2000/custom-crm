# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class CustomCrmLead(models.Model):
    _name = 'custom.crm.lead'
    _description = 'Custom CRM Lead & Pipeline Opportunity'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(string="Lead Title / Name", required=True, tracking=True, index=True)
    partner_name = fields.Char(string="Full Name", tracking=True)
    phone = fields.Char(string="Phone Number", tracking=True, index=True)
    mobile = fields.Char(string="WhatsApp / Mobile", tracking=True)
    email = fields.Char(string="Email Address", tracking=True, index=True)
    city = fields.Char(string="City")
    
    segment = fields.Char(string="Segment")
    equity = fields.Char(string="Equity / Capital")
    trading_experience = fields.Char(string="Trading Experience")
    
    platform = fields.Char(string="Platform")
    campaign_name = fields.Char(string="Campaign Name")
    ad_name = fields.Char(string="Ad Name")
    adset_name = fields.Char(string="Adset Name")
    inbox_url = fields.Char(string="Inbox URL")
    source_sheet = fields.Char(string="Source Sheet")
    
    employee_id = fields.Many2one('hr.employee', string="Assigned Salesperson", tracking=True, index=True)
    user_id = fields.Many2one('res.users', string="Assigned User", default=lambda self: self.env.user, tracking=True, index=True)
    
    stage = fields.Selection([
        ('new', 'New Lead'),
        ('contacted', 'Contacted'),
        ('not_pick_call', 'Not Pick Call'),
        ('followup', 'Followup'),
        ('in_progress', 'In Progress'),
        ('won', 'Won / Converted'),
        ('lost', 'Lost'),
        ('junk', 'Junk')
    ], string="Stage", default='new', required=True, tracking=True, index=True, group_expand='_read_group_stage_ids')
    
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Medium'),
        ('2', 'High'),
        ('3', 'Very High')
    ], string="Priority", default='0', tracking=True)

    master_lead_id = fields.Many2one('crm.master.lead', string="Master Lead Reference", ondelete='set null')
    description = fields.Html(string="Notes & Marketing Metadata")
    active = fields.Boolean(string="Active", default=True)
    color = fields.Integer(string="Color Index", default=0)

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """Ensures all kanban stages are always visible even if empty."""
        return ['new', 'contacted', 'not_pick_call', 'followup', 'in_progress', 'won', 'lost', 'junk']

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('employee_id') and not vals.get('user_id'):
                emp = self.env['hr.employee'].browse(vals['employee_id'])
                if emp and emp.user_id:
                    vals['user_id'] = emp.user_id.id
        return super(CustomCrmLead, self).create(vals_list)

    def write(self, vals):
        if 'employee_id' in vals and vals['employee_id'] and 'user_id' not in vals:
            emp = self.env['hr.employee'].browse(vals['employee_id'])
            if emp and emp.user_id:
                vals['user_id'] = emp.user_id.id
        return super(CustomCrmLead, self).write(vals)

    def action_set_won(self):
        self.write({'stage': 'won'})

    def action_set_lost(self):
        self.write({'stage': 'lost'})

    def init(self):
        """Runs on module load/upgrade to enforce strict record rules and auto-link employee users."""
        super(CustomCrmLead, self).init()
        try:
            # Update salesman rule in ir.rule
            rule_salesman = self.env.ref('crm_lead_sync_assignment.custom_crm_lead_salesman_rule', raise_if_not_found=False)
            if rule_salesman:
                rule_salesman.sudo().write({
                    'domain_force': "['|', ('employee_id.user_id', '=', user.id), ('user_id', '=', user.id)]",
                    'groups': [(6, 0, [self.env.ref('sales_team.group_sale_salesman').id])],
                    'active': True,
                })

            rule_manager = self.env.ref('crm_lead_sync_assignment.custom_crm_lead_manager_rule', raise_if_not_found=False)
            if rule_manager:
                rule_manager.sudo().write({
                    'domain_force': "[(1, '=', 1)]",
                    'groups': [(6, 0, [self.env.ref('sales_team.group_sale_manager').id])],
                    'active': True,
                })

            self._auto_fix_existing_lead_users()
        except Exception as e:
            _logger.error("Error updating custom_crm_lead rules in init: %s", str(e))

    @api.model
    def _auto_fix_existing_lead_users(self):
        """Fixes existing lead records so user_id matches employee_id.user_id and sanitizes salesman groups."""
        # 1. Sanitize security groups for regular salespeople (Sajid, Akshita, Suresh)
        group_manager = self.env.ref('sales_team.group_sale_manager', raise_if_not_found=False)
        group_all_leads = self.env.ref('sales_team.group_sale_salesman_all_leads', raise_if_not_found=False)
        group_salesman = self.env.ref('sales_team.group_sale_salesman', raise_if_not_found=False)

        regular_users = self.env['res.users'].search([
            ('id', '!=', 2),
            ('login', '!=', 'admin'),
            ('share', '=', False)
        ])
        for u in regular_users:
            if group_manager and group_manager in u.groups_id:
                u.sudo().write({'groups_id': [(3, group_manager.id)]})
            if group_all_leads and group_all_leads in u.groups_id:
                u.sudo().write({'groups_id': [(3, group_all_leads.id)]})
            if group_salesman and group_salesman not in u.groups_id:
                u.sudo().write({'groups_id': [(4, group_salesman.id)]})

        # 2. Fix lead assignments
        leads = self.search([('employee_id', '!=', False)])
        for lead in leads:
            emp = lead.employee_id
            if emp:
                if not emp.user_id:
                    matched_user = self.env['res.users'].search([
                        ('share', '=', False),
                        '|', ('name', '=ilike', emp.name), ('email', '=ilike', emp.work_email)
                    ], limit=1)
                    if matched_user:
                        emp.sudo().write({'user_id': matched_user.id})
                if emp.user_id and lead.user_id != emp.user_id:
                    lead.sudo().write({'user_id': emp.user_id.id})
