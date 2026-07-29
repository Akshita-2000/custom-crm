# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    google_spreadsheet_1_id = fields.Char(
        string="Google Spreadsheet 1 ID",
        config_parameter='crm_lead_sync.spreadsheet_1_id',
        help="Spreadsheet ID for Document 1."
    )
    google_sheet_1_name = fields.Char(
        string="Sheet 1 Tab Name",
        default="Sheet1",
        config_parameter='crm_lead_sync.sheet_1_name',
        help="Tab name for Document 1."
    )
    google_spreadsheet_2_id = fields.Char(
        string="Google Spreadsheet 2 ID",
        config_parameter='crm_lead_sync.spreadsheet_2_id',
        help="Spreadsheet ID for Document 2."
    )
    google_sheet_2_name = fields.Char(
        string="Sheet 2 Tab Name",
        default="Sheet1",
        config_parameter='crm_lead_sync.sheet_2_name',
        help="Tab name for Document 2."
    )
    google_service_account_json = fields.Text(
        string="Google Service Account JSON",
        help="Paste the full Google Service Account private key JSON contents here."
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            google_service_account_json=params.get_param('crm_lead_sync.service_account_json', default='')
        )
        return res

    def set_values(self):
        # Auto-clean spreadsheet IDs before saving to config parameters
        from .google_service import GoogleSheetsServiceHelper
        if self.google_spreadsheet_1_id:
            self.google_spreadsheet_1_id = GoogleSheetsServiceHelper._clean_spreadsheet_id(self.google_spreadsheet_1_id)
        if self.google_spreadsheet_2_id:
            self.google_spreadsheet_2_id = GoogleSheetsServiceHelper._clean_spreadsheet_id(self.google_spreadsheet_2_id)
            
        super(ResConfigSettings, self).set_values()
        param = self.env['ir.config_parameter'].sudo()
        param.set_param('crm_lead_sync.service_account_json', self.google_service_account_json or '')

    def action_test_google_connection(self):
        """Action button to validate Google API credentials & test reading configured sheet headers."""
        self.ensure_one()
        # Ensure latest form inputs are cleaned and persisted
        self.set_values()

        from .google_service import GoogleSheetsServiceHelper

        sp1_id = GoogleSheetsServiceHelper._clean_spreadsheet_id(self.google_spreadsheet_1_id)
        sheet1_name = self.google_sheet_1_name
        sp2_id = GoogleSheetsServiceHelper._clean_spreadsheet_id(self.google_spreadsheet_2_id)
        sheet2_name = self.google_sheet_2_name
        json_credentials = self.google_service_account_json

        if not sp1_id and not sp2_id:
            raise UserError(_("Please fill in at least one Google Spreadsheet ID."))

        msg_parts = []
        has_success = False

        if sp1_id:
            try:
                rec1 = GoogleSheetsServiceHelper.fetch_sheet_values(sp1_id, sheet1_name, json_credentials)
                msg_parts.append(_("Spreadsheet 1 (ID: %s): Success! Read %s rows.") % (sp1_id, len(rec1)))
                has_success = True
            except Exception as e:
                msg_parts.append(_("Spreadsheet 1 Error (ID: %s): %s") % (sp1_id, str(e)))

        if sp2_id:
            try:
                rec2 = GoogleSheetsServiceHelper.fetch_sheet_values(sp2_id, sheet2_name, json_credentials)
                msg_parts.append(_("Spreadsheet 2 (ID: %s): Success! Read %s rows.") % (sp2_id, len(rec2)))
                has_success = True
            except Exception as e:
                msg_parts.append(_("Spreadsheet 2 Error (ID: %s): %s") % (sp2_id, str(e)))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Google Connection Test Results"),
                'message': "\n".join(msg_parts),
                'type': 'success' if has_success else 'danger',
                'sticky': True,
            }
        }

    def action_manual_lead_sync(self):
        """Action button to trigger manual synchronization from settings screen."""
        self.ensure_one()
        self.set_values()
        res = self.env['crm.master.lead']._sync_leads_from_google_sheets(triggered_by='manual')
        inserted = res.get('inserted', 0)
        duplicates = res.get('duplicates', 0)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Manual Lead Synchronization Complete"),
                'message': _("Sync finished successfully!\nInserted: %s new master leads.\nDuplicates Skipped: %s.") % (inserted, duplicates),
                'type': 'success',
                'sticky': True,
            }
        }
