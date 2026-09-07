# -*- coding: utf-8 -*-
import requests
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    voiso_enabled = fields.Boolean(
        string="Enable Voiso Click-to-Call",
        config_parameter='voiso.enabled',
        default=True,
        help="Enable Voiso telephony integration across CRM Leads and Contacts."
    )
    voiso_base_url = fields.Char(
        string="Voiso Base URL",
        config_parameter='voiso.base_url',
        default='https://wekotrade.voiso.com/api/v4',
        help="Base API URL for Voiso (e.g. https://wekotrade.voiso.com/api/v4)"
    )
    voiso_api_key = fields.Char(
        string="Voiso API Key",
        config_parameter='voiso.api_key',
        help="API Key with 'voice.call.manage' and 'users.read' scopes."
    )
    voiso_default_country_code = fields.Char(
        string="Default Country Code",
        config_parameter='voiso.default_country_code',
        default='91',
        help="Default country code to auto-prepend for 10-digit numbers (e.g. 91 for India)."
    )

    def action_sync_voiso_users(self):
        """
        Calls GET /api/v4/users and automatically maps Voiso Users to Odoo Users
        by matching name (e.g. Vinay, Govinda, Muskan, Neha, Rajat, Arshad) or email.
        """
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        base_url = (ICP.get_param('voiso.base_url') or 'https://wekotrade.voiso.com/api/v4').strip().rstrip('/')
        api_key = (ICP.get_param('voiso.api_key') or '').strip()

        if not api_key:
            raise UserError(_("Please configure and save the Voiso API Key before syncing users."))

        endpoint = f"{base_url}/users"
        headers = {
            'Authorization': f"Bearer {api_key}",
            'Accept': 'application/json',
        }

        try:
            response = requests.get(endpoint, headers=headers, timeout=10)
        except Exception as e:
            raise UserError(_("Failed to connect to Voiso API: %s") % str(e))

        if response.status_code != 200:
            raise UserError(_("Voiso GET /users failed (%d): %s\n"
                              "Ensure API Key has 'users.read' scope.") % (response.status_code, response.text))

        data = response.json()
        # Voiso returns a list of users or object containing users array
        if isinstance(data, list):
            voiso_users = data
        elif isinstance(data, dict):
            voiso_users = data.get('users') or data.get('data') or [data]
        else:
            voiso_users = []

        if not voiso_users:
            raise UserError(_("No users retrieved from Voiso API."))

        odoo_users = self.env['res.users'].search([('active', '=', True)])
        mapped_count = 0
        details = []

        for vuser in voiso_users:
            if not isinstance(vuser, dict):
                continue
            v_id = str(vuser.get('id', ''))
            v_name = (vuser.get('name') or vuser.get('first_name') or vuser.get('full_name') or '').strip()
            v_email = (vuser.get('email') or '').strip()
            v_ext = str(vuser.get('extension') or vuser.get('ext') or '')

            if not v_id:
                continue

            # Match by Name (case-insensitive) or Email or Substring match
            matched_odoo_user = False
            for ouser in odoo_users:
                o_name = ouser.name.strip()
                o_email = (ouser.email or '').strip()

                if (v_name and o_name.lower() == v_name.lower()) or \
                   (v_name and v_name.lower() in o_name.lower()) or \
                   (v_name and o_name.lower() in v_name.lower()) or \
                   (v_email and o_email and o_email.lower() == v_email.lower()):
                    matched_odoo_user = ouser
                    break

            if matched_odoo_user:
                matched_odoo_user.sudo().write({'voiso_user_id': v_id})
                mapped_count += 1
                ext_str = f" (Extension: {v_ext})" if v_ext else ""
                details.append(f"• {matched_odoo_user.name} ➔ Voiso User ID: {v_id}{ext_str}")

        msg = _("Successfully mapped %d user(s):\n\n%s") % (mapped_count, "\n".join(details)) if details else _("Retrieved %d Voiso user(s), but no matching Odoo user names/emails were found.") % len(voiso_users)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Voiso User Auto-Sync Complete"),
                'message': msg,
                'type': 'success' if mapped_count > 0 else 'warning',
                'sticky': True,
            }
        }
