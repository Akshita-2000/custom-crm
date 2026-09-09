# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CrmLeadImportWizard(models.TransientModel):
    _name = 'crm.lead.import.wizard'
    _description = 'Wizard to Distribute and Import Master Leads into Custom CRM'

    total_unimported_leads = fields.Integer(
        string="Total Available Unimported Leads",
        readonly=True,
        help="Number of leads in Master Lead table ready for import."
    )
    total_assigned_count = fields.Integer(
        string="Total Allocated Leads",
        compute='_compute_total_assigned_count',
        store=False,
        help="Sum of lead counts entered for all salespeople."
    )
    is_premium = fields.Boolean(
        string="Is Premium Import",
        default=False,
        help="If set, imports from Master Premium Leads."
    )
    line_ids = fields.One2many(
        'crm.lead.import.wizard.line',
        'wizard_id',
        string="Salesperson Allocation Matrix"
    )

    @api.depends('line_ids.allocated_count')
    def _compute_total_assigned_count(self):
        for wizard in self:
            wizard.total_assigned_count = sum(wizard.line_ids.mapped('allocated_count'))

    @api.model
    def default_get(self, fields_list):
        res = super(CrmLeadImportWizard, self).default_get(fields_list)
        
        is_premium_flag = self._context.get('default_is_premium', False)
        res['is_premium'] = is_premium_flag

        # Load total unimported leads count based on premium flag
        unimported_leads = self.env['crm.master.lead'].search([
            ('is_imported', '=', False),
            ('is_premium', '=', is_premium_flag)
        ])
        res['total_unimported_leads'] = len(unimported_leads)

        # Load all active Employees (hr.employee)
        employees = self.env['hr.employee'].search([('active', '=', True)], order='name asc')

        lines = []
        if employees:
            for emp in employees:
                lines.append((0, 0, {
                    'employee_id': emp.id,
                    'allocated_count': 0
                }))
        else:
            # Fallback to users if no HR employees created yet
            users = self.env['res.users'].search([('share', '=', False), ('active', '=', True)], order='name asc')
            for u in users:
                lines.append((0, 0, {
                    'employee_id': False,
                    'user_id': u.id,
                    'allocated_count': 0
                }))

        res['line_ids'] = lines
        return res

    def action_import_and_assign_leads(self):
        """
        Executes validation, sequential distribution, custom.crm.lead record creation,
        master lead status updates, and history logging. Allows partial lead distribution.
        """
        self.ensure_one()

        unimported_leads = self.env['crm.master.lead'].search([
            ('is_imported', '=', False),
            ('is_premium', '=', self.is_premium)
        ], order='id asc')
        available_count = len(unimported_leads)

        if available_count == 0:
            raise UserError(_("There are no unimported leads available in the Master Lead table."))

        total_allocated = sum(self.line_ids.mapped('allocated_count'))

        if total_allocated <= 0:
            raise UserError(_("Please allocate at least 1 lead to a salesperson before importing."))

        if total_allocated > available_count:
            raise UserError(_(
                "Validation Error:\n"
                "Total Available Leads = %s\n"
                "Total Allocated = %s\n\n"
                "You cannot allocate more leads than available unimported leads."
            ) % (available_count, total_allocated))

        # Filter lines with allocated_count > 0 and valid employee_id or user_id
        allocation_lines = self.line_ids.filtered(lambda l: l.allocated_count > 0 and (l.employee_id or l.user_id))
        if not allocation_lines:
            raise UserError(_("Please assign at least 1 lead to an employee/salesperson."))

        lead_index = 0
        summary_lines = []
        history_line_vals = []

        crm_leads_created = self.env['custom.crm.lead']

        # Sequential Allocation Execution for total_allocated leads
        for line in allocation_lines:
            employee = line.employee_id

            # Auto-link employee.user_id if not set but a matching user exists
            if employee and not employee.user_id:
                matched_user = self.env['res.users'].search([
                    ('share', '=', False),
                    '|', ('name', '=ilike', employee.name), ('email', '=ilike', employee.work_email)
                ], limit=1)
                if matched_user:
                    employee.sudo().write({'user_id': matched_user.id})

            user = line.user_id or (employee.user_id if employee and employee.user_id else self.env.user)
            assign_name = employee.name if employee else user.name
            count_to_assign = line.allocated_count

            target_leads = unimported_leads[lead_index: lead_index + count_to_assign]
            lead_index += count_to_assign

            summary_lines.append(f"{assign_name}: {count_to_assign}")
            history_line_vals.append((0, 0, {
                'user_id': user.id,
                'allocated_count': count_to_assign
            }))

            for master_lead in target_leads:
                # Prepare description content
                desc_parts = [
                    f"<b>Source Sheet:</b> {master_lead.source_sheet or 'N/A'}",
                    f"<b>Platform:</b> {master_lead.platform or 'N/A'}",
                    f"<b>Campaign Name:</b> {master_lead.campaign_name or 'N/A'}",
                    f"<b>Ad Name:</b> {master_lead.ad_name or 'N/A'}",
                    f"<b>Adset Name:</b> {master_lead.adset_name or 'N/A'}",
                    f"<b>Segment:</b> {master_lead.segment or 'N/A'}",
                    f"<b>Equity:</b> {master_lead.equity or 'N/A'}",
                    f"<b>WhatsApp Number:</b> {master_lead.whatsapp_number or 'N/A'}",
                    f"<b>Trading Experience:</b> {master_lead.trading_experience or 'N/A'}",
                    f"<b>Inbox URL:</b> {master_lead.inbox_url or 'N/A'}",
                ]
                description_html = "<br/>".join(desc_parts)

                # Format phone with country code if needed
                formatted_phone = self.env['crm.master.lead']._format_phone_with_country_code(master_lead.phone or master_lead.whatsapp_number, master_lead.country_code)
                formatted_mobile = self.env['crm.master.lead']._format_phone_with_country_code(master_lead.whatsapp_number or master_lead.phone, master_lead.country_code)

                # Create Custom CRM Lead
                crm_lead_vals = {
                    'name': master_lead.name or f"Lead from {master_lead.source_sheet or 'Google Sheets'}",
                    'partner_name': master_lead.name,
                    'phone': formatted_phone,
                    'mobile': formatted_mobile,
                    'email': master_lead.email,
                    'city': master_lead.city,
                    'country_code': master_lead.country_code,
                    'is_premium': master_lead.is_premium,
                    'segment': master_lead.segment,
                    'equity': master_lead.equity,
                    'trading_experience': master_lead.trading_experience,
                    'platform': master_lead.platform,
                    'campaign_name': master_lead.campaign_name,
                    'ad_name': master_lead.ad_name,
                    'adset_name': master_lead.adset_name,
                    'inbox_url': master_lead.inbox_url,
                    'source_sheet': master_lead.source_sheet,
                    'employee_id': employee.id if employee else False,
                    'user_id': user.id,
                    'stage': 'new',
                    'master_lead_id': master_lead.id,
                    'description': description_html,
                }

                new_crm_lead = self.env['custom.crm.lead'].create(crm_lead_vals)
                crm_leads_created |= new_crm_lead

                # Update Master Lead
                master_lead.write({
                    'is_imported': True,
                    'is_assigned': True,
                    'assigned_user_id': user.id,
                    'crm_lead_id': new_crm_lead.id,
                    'lead_status': 'imported',
                })

        # Record History
        history_vals = {
            'total_leads': available_count,
            'imported_count': total_allocated,
            'duplicates_count': 0,
            'skipped_count': available_count - total_allocated,
            'assignment_summary': "\n".join(summary_lines),
            'line_ids': history_line_vals,
        }
        self.env['crm.lead.import.history'].create(history_vals)

        # Return action to display imported Custom CRM leads
        return {
            'type': 'ir.actions.act_window',
            'name': _('Imported CRM Pipeline Leads (%s)') % len(crm_leads_created),
            'res_model': 'custom.crm.lead',
            'view_mode': 'kanban,tree,form',
            'domain': [('id', 'in', crm_leads_created.ids)],
            'target': 'current',
        }


class CrmLeadImportWizardLine(models.TransientModel):
    _name = 'crm.lead.import.wizard.line'
    _description = 'Salesperson Allocation Line in Import Wizard'

    wizard_id = fields.Many2one('crm.lead.import.wizard', string="Wizard Reference", ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string="Employee / Salesperson")
    user_id = fields.Many2one('res.users', string="User Account")
    allocated_count = fields.Integer(string="Lead Count", default=0, required=True)
