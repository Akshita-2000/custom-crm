# -*- coding: utf-8 -*-
import re
import requests
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def mask_phone_number(raw_phone):
    """
    Masks phone number for any international country code, displaying only the last 2 digits.
    Examples:
      'p:+971507087993' -> '+971 ********93'
      'p:+923337912747' -> '+92 ********47'
      '+91 9575950549'  -> '+91 ********49'
      '3216226672'      -> '********72'
    """
    if not raw_phone:
        return ''
    phone_str = str(raw_phone).strip()
    # Strip common lead import prefixes like 'p:', 'tel:', 'phone:'
    phone_str = re.sub(r'^(p:|tel:|phone:)', '', phone_str, flags=re.IGNORECASE).strip()

    digits = re.sub(r'\D', '', phone_str)
    if len(digits) <= 2:
        return '*' * len(digits)

    last_two = digits[-2:]

    # Detect country code prefix (e.g. +971, +92, +91, +1, +44, etc.)
    prefix = ''
    if phone_str.startswith('+'):
        match = re.match(r'^(\+\d{1,4})', phone_str)
        if match:
            prefix = match.group(1) + ' '
    elif len(digits) >= 11:
        if digits.startswith('971'):
            prefix = '+971 '
        elif digits.startswith('92'):
            prefix = '+92 '
        elif digits.startswith('91'):
            prefix = '+91 '
        elif digits.startswith('1'):
            prefix = '+1 '
        elif digits.startswith('44'):
            prefix = '+44 '
        else:
            prefix = '+' + digits[:2] + ' '

    # Calculate middle mask length
    prefix_digits_len = len(re.sub(r'\D', '', prefix)) if prefix else 0
    middle_count = max(4, len(digits) - 2 - prefix_digits_len)
    masked_middle = '*' * middle_count

    return f"{prefix}{masked_middle}{last_two}"


def normalize_phone_number(raw_phone, default_country_code='91'):
    """
    Normalizes raw phone input string for Voiso API worldwide.
    - Strips 'p:', 'tel:', spaces, dashes, parentheses, dots.
    - Preserves international country code digits (e.g. '+971 50 708 7993' -> '971507087993', '+92 333 7912747' -> '923337912747').
    - If 10-digit number without country code is provided, prepends default_country_code.
    """
    if not raw_phone:
        return ''
    phone_str = str(raw_phone).strip()

    # Strip common lead import prefixes like 'p:', 'tel:', 'phone:'
    phone_str = re.sub(r'^(p:|tel:|phone:)', '', phone_str, flags=re.IGNORECASE).strip()

    # Remove whitespace and formatting characters
    cleaned = re.sub(r'[\s\-\(\)\.]', '', phone_str)
    # Strip leading '+' as Voiso expects full numeric digit string with country code
    if cleaned.startswith('+'):
        cleaned = cleaned[1:]
    # Remove any non-digit character
    cleaned = re.sub(r'\D', '', cleaned)

    # Clean default country code
    clean_cc = re.sub(r'\D', '', str(default_country_code or '91'))

    # If phone is a 10-digit local number without country code, prepend default country code
    if len(cleaned) == 10 and clean_cc and not cleaned.startswith(clean_cc):
        cleaned = clean_cc + cleaned

    return cleaned


def end_voiso_call(env, call_id, target_record=None, voiso_user_id=None):
    """
    Terminates active Voiso call via POST /voice/calls/{call_id}/hangup with user_id.
    """
    if not call_id:
        return True

    ICP = env['ir.config_parameter'].sudo()
    base_url = (ICP.get_param('voiso.base_url') or 'https://wekotrade.voiso.com/api/v4').strip().rstrip('/')
    api_key = (ICP.get_param('voiso.api_key') or '').strip()

    if not api_key:
        raise UserError(_("Voiso API Key is missing."))

    user_id_val = voiso_user_id or env.user.voiso_user_id
    if not user_id_val:
        raise UserError(_("Your Odoo user does not have a mapped Voiso User ID."))

    try:
        user_id_val = int(user_id_val)
    except ValueError:
        pass

    endpoint = f"{base_url}/voice/calls/{call_id}/hangup"
    headers = {
        'Authorization': f"Bearer {api_key}",
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    payload = {
        'user_id': user_id_val
    }

    _logger.info("Hanging up Voiso Call ID %s via POST %s with user %s", call_id, endpoint, user_id_val)

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        _logger.info("Voiso Hangup response: %s %s", response.status_code, response.text)
    except Exception as e:
        _logger.warning("Error hanging up Voiso call %s: %s", call_id, str(e))

    if target_record and hasattr(target_record, 'message_post'):
        target_record.message_post(
            body=_("🔴 <b>Voiso Call Disconnected / Ended</b><br/>• <b>Call ID:</b> <code>%s</code>") % call_id,
            subtype_xmlid='mail.mt_note'
        )

    return True


def make_voiso_call(env, target_record, phone_number, number_type='Phone'):
    """
    Initiates outbound Voiso call via server-side POST API v4.
    """
    ICP = env['ir.config_parameter'].sudo()
    enabled = ICP.get_param('voiso.enabled', default='False').lower() in ('true', '1')
    base_url = (ICP.get_param('voiso.base_url') or 'https://wekotrade.voiso.com/api/v4').strip().rstrip('/')
    api_key = (ICP.get_param('voiso.api_key') or '').strip()
    default_cc = ICP.get_param('voiso.default_country_code', default='91').strip()

    if not enabled:
        raise UserError(_("Voiso Integration is disabled. Please enable it in Settings > CRM > Voiso Click-to-Call Integration."))

    if not api_key:
        raise UserError(_("Voiso API Key is missing. Please configure the Voiso API Key in Odoo Settings."))

    # 1. Check logged-in user's Voiso User ID mapping
    current_user = env.user
    voiso_user_id = current_user.voiso_user_id
    if not voiso_user_id:
        raise UserError(_("Your Odoo user '%s' does not have a mapped Voiso User ID.\n\n"
                          "Please contact your Odoo administrator or go to Settings > Voiso Integration and click 'Sync Voiso Users'.") % current_user.name)

    # 2. Clean and validate phone number (Worldwide support for +971, +92, +91, etc.)
    normalized_phone = normalize_phone_number(phone_number, default_country_code=default_cc)
    if not normalized_phone or len(normalized_phone) < 7:
        raise UserError(_("Invalid or missing %s number '%s' for record '%s'.") % (number_type, phone_number or '', target_record.display_name or ''))

    # Parse numeric user ID if integer string
    try:
        user_id_val = int(voiso_user_id)
    except ValueError:
        user_id_val = voiso_user_id

    # 3. Prepare payload and request headers
    endpoint = f"{base_url}/voice/calls"
    headers = {
        'Authorization': f"Bearer {api_key}",
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    payload = {
        'user_id': user_id_val,
        'phone_number': normalized_phone,
    }

    _logger.info("Initiating Voiso Call via %s for user %s to phone %s", endpoint, user_id_val, normalized_phone)

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
    except requests.exceptions.Timeout:
        raise UserError(_("Connection to Voiso API timed out. Please verify your internet connection or Voiso server availability."))
    except requests.exceptions.RequestException as e:
        raise UserError(_("Failed to connect to Voiso server: %s") % str(e))

    # 4. Handle HTTP status codes
    if response.status_code in (200, 201):
        res_data = {}
        try:
            res_data = response.json()
        except Exception:
            pass

        call_id = ''
        if isinstance(res_data, dict):
            call_id = res_data.get('call', {}).get('id') or res_data.get('id', '')

        masked_disp = mask_phone_number(normalized_phone)
        log_msg = _("📞 <b>Voiso Outbound Call Initiated</b><br/>"
                    "• <b>Agent:</b> %s (Voiso ID: %s)<br/>"
                    "• <b>Dialed Number:</b> %s (%s)<br/>"
                    "• <b>Call ID:</b> <code>%s</code>") % (
                        current_user.name, voiso_user_id, masked_disp, number_type, call_id or 'Started'
                    )

        # Post note to Chatter log if mail.thread is supported
        if hasattr(target_record, 'message_post'):
            target_record.message_post(body=log_msg, subtype_xmlid='mail.mt_note')

        # Create Active Call Wizard modal screen
        wizard = env['voiso.active.call.wizard'].create({
            'call_id': call_id or 'N/A',
            'customer_name': target_record.display_name or 'Customer',
            'phone_masked': masked_disp,
            'res_model': target_record._name,
            'res_id': target_record.id,
        })

        return {
            'name': _('📞 Active Voiso Call'),
            'type': 'ir.actions.act_window',
            'res_model': 'voiso.active.call.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    elif response.status_code == 422:
        err_json = {}
        try:
            err_json = response.json().get('errors', {})
        except Exception:
            pass

        err_parts = []
        if 'user' in err_json:
            err_parts.append(_("1. Voiso Agent Offline: Voiso User ID %s (%s) is OFFLINE in Voiso.\n"
                               "-> Solution: Please log into https://wekotrade.voiso.com/ in your browser/softphone and set your status to ONLINE / AVAILABLE.") % (voiso_user_id, current_user.name))
        if 'phone_number' in err_json:
            err_parts.append(_("2. Invalid Phone Number Format: Voiso rejected phone number '%s'.\n"
                               "-> Solution: Ensure the customer phone number has the country code (e.g. +971507087993, +923337912747, +919876543210).") % mask_phone_number(normalized_phone))

        if not err_parts:
            err_parts.append(response.text)

        raise UserError(_("Voiso Call Rejected (422):\n\n%s") % "\n\n".join(err_parts))

    elif response.status_code in (401, 403):
        raise UserError(_("Voiso API Authorization Failed (%d).\n\n"
                          "Please check your API key in Settings and ensure it has 'voice.call.manage' scope.") % response.status_code)
    elif response.status_code == 400:
        err_msg = response.text
        try:
            err_msg = response.json().get('message', response.text)
        except Exception:
            pass
        raise UserError(_("Voiso Call Error (400 Bad Request): %s\n\n"
                          "Ensure your Voiso softphone is logged in and ready.") % err_msg)
    elif response.status_code == 404:
        raise UserError(_("Voiso User ID (%s) or API endpoint not found (404).") % voiso_user_id)
    else:
        err_msg = response.text
        try:
            err_msg = response.json().get('message', response.text)
        except Exception:
            pass
        raise UserError(_("Voiso Call Error (%d): %s") % (response.status_code, err_msg))
