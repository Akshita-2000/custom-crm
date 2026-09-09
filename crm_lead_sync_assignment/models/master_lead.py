# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.parser import parse as parse_date
import pytz

_logger = logging.getLogger(__name__)


class CrmMasterLead(models.Model):
    _name = 'crm.master.lead'
    _description = 'Master Lead Synchronization Repository'
    _order = 'create_date desc, id desc'

    name = fields.Char(string="Full Name", required=True, index=True)
    phone = fields.Char(string="Phone Number", index=True)
    whatsapp_number = fields.Char(string="WhatsApp Number", index=True)
    email = fields.Char(string="Email Address", index=True)
    city = fields.Char(string="City")
    country_code = fields.Char(string="Country Code", index=True)
    is_premium = fields.Boolean(string="Is Premium Lead", default=False, index=True)
    
    segment = fields.Char(string="Segment")
    equity = fields.Char(string="Equity / Capital")
    trading_experience = fields.Char(string="Trading Experience")
    
    platform = fields.Char(string="Platform")
    campaign_name = fields.Char(string="Campaign Name")
    ad_name = fields.Char(string="Ad Name")
    adset_name = fields.Char(string="Adset Name")
    form_name = fields.Char(string="Form Name")
    inbox_url = fields.Char(string="Inbox URL")
    
    source_sheet = fields.Char(string="Source Sheet", index=True)
    raw_created_time = fields.Char(string="Raw Created Time")
    created_time = fields.Datetime(string="Created Time")
    sync_time = fields.Datetime(string="Sync Time", default=fields.Datetime.now)
    
    is_imported = fields.Boolean(string="Imported to CRM", default=False, index=True)
    is_assigned = fields.Boolean(string="Assigned", default=False, index=True)
    
    assigned_employee_id = fields.Many2one('hr.employee', string="Assigned Salesperson", tracking=True)
    assigned_user_id = fields.Many2one('res.users', string="Assigned User Account", tracking=True)
    crm_lead_id = fields.Many2one('custom.crm.lead', string="Imported CRM Lead", ondelete='set null')
    
    lead_status = fields.Selection([
        ('new', 'New / Unassigned'),
        ('assigned', 'Assigned'),
        ('imported', 'Imported to CRM'),
        ('duplicate', 'Duplicate Skipped')
    ], string="Lead Status", default='new', index=True, required=True)

    def init(self):
        """Auto-heal master leads missing CRM lead pipeline records on module upgrade."""
        super(CrmMasterLead, self).init()
        try:
            self._auto_heal_master_leads()
            self._auto_format_existing_phones()
        except Exception as e:
            _logger.error("Error in CrmMasterLead init auto heal: %s", str(e))

    @api.model
    def _format_phone_with_country_code(self, raw_phone, country_code=None):
        if not raw_phone:
            return ''
        p_str = str(raw_phone).strip()
        if not p_str:
            return ''
            
        if 'e' in p_str.lower():
            try:
                p_str = str(int(float(p_str)))
            except Exception:
                pass

        if p_str.startswith('p:') or p_str.startswith('+'):
            return p_str

        cc_str = ''
        if country_code:
            import re
            cc_str = re.sub(r'\D', '', str(country_code))

        if cc_str:
            if not p_str.startswith(cc_str):
                p_str = f"{cc_str}{p_str}"
            return f"p:+{p_str}"
        else:
            import re
            digits = re.sub(r'\D', '', p_str)
            if len(digits) == 10:
                return f"p:+91{digits}"
            elif len(digits) > 10:
                return f"p:+{digits}"
            return p_str

    @api.model
    def _auto_format_existing_phones(self):
        """Auto-formats existing master lead and custom CRM lead phone numbers with country code prefix."""
        for lead in self.search([('phone', '!=', False)]):
            if lead.phone and not (lead.phone.startswith('p:') or lead.phone.startswith('+')):
                new_phone = self._format_phone_with_country_code(lead.phone, lead.country_code)
                new_wa = self._format_phone_with_country_code(lead.whatsapp_number or lead.phone, lead.country_code)
                lead.sudo().write({'phone': new_phone, 'whatsapp_number': new_wa})
                if lead.crm_lead_id:
                    lead.crm_lead_id.sudo().write({'phone': new_phone, 'mobile': new_wa})

        crm_leads = self.env['custom.crm.lead'].search([('phone', '!=', False)])
        for clead in crm_leads:
            if clead.phone and not (clead.phone.startswith('p:') or clead.phone.startswith('+')):
                new_phone = self._format_phone_with_country_code(clead.phone, clead.country_code)
                new_mob = self._format_phone_with_country_code(clead.mobile or clead.phone, clead.country_code)
                clead.sudo().write({'phone': new_phone, 'mobile': new_mob})

    @api.model
    def _auto_heal_master_leads(self):
        """Finds master leads with assigned_employee_id but missing crm_lead_id, and creates custom.crm.lead."""
        missing_leads = self.search([('assigned_employee_id', '!=', False), ('crm_lead_id', '=', False)])
        if missing_leads:
            missing_leads.action_create_crm_lead()

    def action_create_crm_lead(self):
        """Manually creates/assigns Custom CRM Lead pipeline record for selected master leads."""
        created_crm_leads = self.env['custom.crm.lead']
        for master in self:
            employee = master.assigned_employee_id
            user = master.assigned_user_id or (employee.user_id if employee and employee.user_id else self.env.user)

            # Auto-link employee user if needed
            if employee and not employee.user_id:
                matched_user = self.env['res.users'].search([
                    ('share', '=', False),
                    '|', ('name', '=ilike', employee.name), ('email', '=ilike', employee.work_email)
                ], limit=1)
                if matched_user:
                    employee.sudo().write({'user_id': matched_user.id})
                    user = matched_user

            if master.crm_lead_id:
                # If CRM lead already exists, update salesperson assignment
                master.crm_lead_id.write({
                    'employee_id': employee.id if employee else False,
                    'user_id': user.id,
                })
                created_crm_leads |= master.crm_lead_id
                master.write({
                    'is_imported': True,
                    'is_assigned': True,
                    'assigned_user_id': user.id,
                    'assigned_employee_id': employee.id if employee else False,
                    'lead_status': 'imported',
                })
                continue

            # Build HTML Description
            desc_parts = [
                f"<b>Source Sheet:</b> {master.source_sheet or 'N/A'}",
                f"<b>Platform:</b> {master.platform or 'N/A'}",
                f"<b>Campaign Name:</b> {master.campaign_name or 'N/A'}",
                f"<b>Ad Name:</b> {master.ad_name or 'N/A'}",
                f"<b>Adset Name:</b> {master.adset_name or 'N/A'}",
                f"<b>Segment:</b> {master.segment or 'N/A'}",
                f"<b>Equity:</b> {master.equity or 'N/A'}",
                f"<b>WhatsApp Number:</b> {master.whatsapp_number or 'N/A'}",
                f"<b>Trading Experience:</b> {master.trading_experience or 'N/A'}",
                f"<b>Inbox URL:</b> {master.inbox_url or 'N/A'}",
            ]
            description_html = "<br/>".join(desc_parts)

            formatted_phone = self._format_phone_with_country_code(master.phone or master.whatsapp_number, master.country_code)
            formatted_mobile = self._format_phone_with_country_code(master.whatsapp_number or master.phone, master.country_code)

            crm_lead_vals = {
                'name': master.name or f"Lead from {master.source_sheet or 'Google Sheets'}",
                'partner_name': master.name,
                'phone': formatted_phone,
                'mobile': formatted_mobile,
                'email': master.email,
                'city': master.city,
                'country_code': master.country_code,
                'is_premium': master.is_premium,
                'segment': master.segment,
                'equity': master.equity,
                'trading_experience': master.trading_experience,
                'platform': master.platform,
                'campaign_name': master.campaign_name,
                'ad_name': master.ad_name,
                'adset_name': master.adset_name,
                'inbox_url': master.inbox_url,
                'source_sheet': master.source_sheet,
                'employee_id': employee.id if employee else False,
                'user_id': user.id,
                'stage': 'new',
                'master_lead_id': master.id,
                'description': description_html,
            }

            crm_lead = self.env['custom.crm.lead'].create(crm_lead_vals)
            created_crm_leads |= crm_lead

            master.write({
                'is_imported': True,
                'is_assigned': True,
                'assigned_user_id': user.id,
                'assigned_employee_id': employee.id if employee else False,
                'crm_lead_id': crm_lead.id,
                'lead_status': 'imported',
            })

        if created_crm_leads:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Assigned CRM Pipeline Leads (%s)') % len(created_crm_leads),
                'res_model': 'custom.crm.lead',
                'view_mode': 'kanban,tree,form',
                'domain': [('id', 'in', created_crm_leads.ids)],
                'target': 'current',
            }

    @api.model
    def _parse_datetime_str(self, date_str):
        """Helper to parse raw date/time string into naive Odoo Datetime."""
        if not date_str:
            return fields.Datetime.now()
        try:
            parsed_dt = parse_date(str(date_str))
            if parsed_dt.tzinfo is not None:
                parsed_dt = parsed_dt.astimezone(pytz.utc).replace(tzinfo=None)
            return parsed_dt
        except Exception:
            return fields.Datetime.now()

    @api.model
    def _sync_leads_from_google_sheets(self, triggered_by='cron'):
        """Synchronization entry point for cron and manual triggers."""
        _logger.info("Starting Google Sheet Sync triggered by %s", triggered_by)
        
        params = self.env['ir.config_parameter'].sudo()
        sp1_id = params.get_param('crm_lead_sync.spreadsheet_1_id')
        sheet1_name = params.get_param('crm_lead_sync.sheet_1_name', default='Sheet1')
        sp2_id = params.get_param('crm_lead_sync.spreadsheet_2_id')
        sheet2_name = params.get_param('crm_lead_sync.sheet_2_name', default='Sheet1')
        premium_sp_id = params.get_param('crm_lead_sync.premium_spreadsheet_id')
        premium_sheet_name = params.get_param('crm_lead_sync.premium_sheet_name', default='Sheet1')
        json_credentials = params.get_param('crm_lead_sync.service_account_json', default='')

        from .google_service import GoogleSheetsServiceHelper

        inserted_count = 0
        duplicate_count = 0
        sheet1_count = 0
        sheet2_count = 0
        premium_sheet_count = 0
        error_msg = None
        status = 'success'

        records_to_process = []

        if sp1_id:
            try:
                raw_recs = GoogleSheetsServiceHelper.fetch_sheet_values(sp1_id, sheet1_name, json_credentials)
                sheet1_count = len(raw_recs)
                for r in raw_recs:
                    r['_source_sheet_label'] = 'Sheet 1'
                    r['_is_premium'] = False
                records_to_process.extend(raw_recs)
            except Exception as e:
                _logger.error("Sync Error for Sheet 1: %s", str(e))
                status = 'warning' if records_to_process else 'failed'
                error_msg = f"Sheet 1 Error: {str(e)}"

        if sp2_id:
            try:
                raw_recs = GoogleSheetsServiceHelper.fetch_sheet_values(sp2_id, sheet2_name, json_credentials)
                sheet2_count = len(raw_recs)
                for r in raw_recs:
                    r['_source_sheet_label'] = 'Sheet 2'
                    r['_is_premium'] = False
                records_to_process.extend(raw_recs)
            except Exception as e:
                _logger.error("Sync Error for Sheet 2: %s", str(e))
                status = 'warning' if (records_to_process or sheet1_count > 0) else 'failed'
                error_msg = (error_msg + f"\nSheet 2 Error: {str(e)}") if error_msg else f"Sheet 2 Error: {str(e)}"

        if premium_sp_id:
            try:
                raw_recs = GoogleSheetsServiceHelper.fetch_sheet_values(premium_sp_id, premium_sheet_name, json_credentials)
                premium_sheet_count = len(raw_recs)
                for r in raw_recs:
                    r['_source_sheet_label'] = 'Premium Sheet'
                    r['_is_premium'] = True
                records_to_process.extend(raw_recs)
            except Exception as e:
                _logger.error("Sync Error for Premium Sheet: %s", str(e))
                status = 'warning' if (records_to_process or sheet1_count > 0 or sheet2_count > 0) else 'failed'
                error_msg = (error_msg + f"\nPremium Sheet Error: {str(e)}") if error_msg else f"Premium Sheet Error: {str(e)}"

        vals_to_create = []

        for rec in records_to_process:
            full_name = rec.get('Name') or rec.get('screen_0_name_0') or rec.get('full_name') or rec.get('Full Name') or rec.get('name') or 'Lead'
            raw_phone = rec.get('Phone') or rec.get('phone_number') or rec.get('Phone Number') or rec.get('phone') or ''
            country_code = str(rec.get('CountryCode') or rec.get('country_code') or rec.get('Country Code') or '').strip()
            if country_code.endswith('.0'):
                country_code = country_code[:-2]

            phone = self._format_phone_with_country_code(raw_phone, country_code)
            raw_wa = rec.get('share_your_whatsapp_number') or rec.get('whatsapp_number') or rec.get('WhatsApp Number') or ''
            whatsapp = self._format_phone_with_country_code(raw_wa, country_code) if raw_wa else phone

            email = str(rec.get('screen_0_email_1') or rec.get('email') or rec.get('Email') or '').strip()
            is_premium_lead = bool(rec.get('_is_premium', False))

            check_phone = phone or whatsapp
            is_dup = False

            if check_phone:
                existing_phone = self.search(['|', ('phone', '=', check_phone), ('whatsapp_number', '=', check_phone)], limit=1)
                if existing_phone:
                    is_dup = True

            if not is_dup and email:
                existing_email = self.search([('email', '=', email)], limit=1)
                if existing_email:
                    is_dup = True

            if is_dup:
                duplicate_count += 1
                continue

            segment = rec.get('in_which_segment_do_you_work') or rec.get('segment') or rec.get('Segment') or rec.get('market_interest') or ''
            equity = rec.get('how_much_your_equity') or rec.get('how_much_your_equ!ty') or rec.get('equity') or rec.get('Equity') or ''
            trading_exp = rec.get('trading_experience') or rec.get('do_you_have_any_trading_experience?') or ''
            raw_time = rec.get('CreatedDate') or rec.get('created_time') or rec.get('Created Time') or ''

            master_vals = {
                'name': full_name,
                'phone': phone,
                'country_code': country_code,
                'whatsapp_number': whatsapp,
                'email': email,
                'city': rec.get('city') or rec.get('City') or '',
                'segment': segment,
                'equity': equity,
                'trading_experience': trading_exp,
                'platform': rec.get('platform') or rec.get('Platform') or rec.get('ig') or '',
                'campaign_name': rec.get('campaign_name') or rec.get('Campaign Name') or '',
                'ad_name': rec.get('ad_name') or rec.get('Ad Name') or rec.get('ctig_ad_id') or '',
                'adset_name': rec.get('adset_name') or rec.get('Adset Name') or '',
                'form_name': rec.get('form_name') or rec.get('Form Name') or '',
                'inbox_url': rec.get('inbox_url') or rec.get('Inbox URL') or rec.get('source_url') or '',
                'source_sheet': rec.get('_source_sheet_label', 'Google Sheet'),
                'is_premium': is_premium_lead,
                'raw_created_time': raw_time,
                'created_time': self._parse_datetime_str(raw_time),
                'sync_time': fields.Datetime.now(),
                'lead_status': 'new',
            }
            vals_to_create.append(master_vals)

        if vals_to_create:
            created_records = self.create(vals_to_create)
            inserted_count = len(created_records)

        self.env['crm.lead.sync.log'].create({
            'sync_date': fields.Datetime.now(),
            'triggered_by': triggered_by,
            'status': status,
            'sheet1_records': sheet1_count,
            'sheet2_records': sheet2_count,
            'inserted_records': inserted_count,
            'duplicates_found': duplicate_count,
            'log_details': (error_msg or 'Sync completed with zero errors.') + f"\nPremium Sheet Records Processed: {premium_sheet_count}",
        })

        return {
            'inserted': inserted_count,
            'duplicates': duplicate_count,
            'status': status,
        }
