# -*- coding: utf-8 -*-
import csv
import io
import json
import logging
import re
import ssl
import time
import urllib.request
import urllib.parse
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class GoogleSheetsServiceHelper:
    """
    Helper class to interface with Google Sheets.
    Supports Zero-Config Public CSV export URL (no credentials required)
    and fallback to Service Account API v4.
    """

    @classmethod
    def _clean_spreadsheet_id(cls, raw_str):
        """Extracts clean Spreadsheet ID from raw input string or full Google Sheet URL."""
        if not raw_str:
            return ""
        raw_str = str(raw_str).strip()
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', raw_str)
        if match:
            return match.group(1)
        return raw_str.split('/')[0].split('?')[0].strip()

    @classmethod
    def _http_get_content(cls, url):
        """
        Robust HTTP GET fetcher supporting both requests and urllib with
        unverified SSL context to bypass Windows Python missing SSL CA cert errors.
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,text/csv,*/*;q=0.8'
        }
        
        # Method 1: Try Python 'requests' library (if installed in Odoo environment)
        try:
            import requests
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200 and resp.text:
                return resp.text
        except Exception as req_err:
            _logger.info("requests library fetch failed: %s. Trying urllib fallback.", str(req_err))

        # Method 2: Standard urllib with unverified SSL context
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            return response.read().decode('utf-8')

    @classmethod
    def fetch_public_sheet_csv(cls, spreadsheet_id, sheet_name=None):
        """
        Fetches sheet data directly via Google Sheets Public CSV Export URL with smart endpoint fallbacks.
        Supports full URL pasting and auto-extracts Spreadsheet ID.
        """
        clean_id = cls._clean_spreadsheet_id(spreadsheet_id)
        if not clean_id:
            raise UserError(_("Spreadsheet ID is missing."))

        urls_to_try = []
        
        # Priority 1: Primary export endpoint (Fetches first tab automatically, 100% reliable!)
        urls_to_try.append(f"https://docs.google.com/spreadsheets/d/{clean_id}/export?format=csv")

        # Priority 2: Tab name specific endpoints
        if sheet_name and str(sheet_name).strip():
            s_name = str(sheet_name).strip()
            encoded_sheet = urllib.parse.quote(s_name)
            urls_to_try.append(f"https://docs.google.com/spreadsheets/d/{clean_id}/export?format=csv&sheet={encoded_sheet}")
            urls_to_try.append(f"https://docs.google.com/spreadsheets/d/{clean_id}/gviz/tq?tqx=out:csv&sheet={encoded_sheet}")

        # Priority 3: Fallback gviz endpoint
        urls_to_try.append(f"https://docs.google.com/spreadsheets/d/{clean_id}/gviz/tq?tqx=out:csv")

        last_error = None
        for url in urls_to_try:
            try:
                content = cls._http_get_content(url)
                if not content or len(content.strip()) == 0:
                    continue

                if "<html" in content.lower() or "google.com/accounts" in content.lower():
                    raise UserError(_("Spreadsheet is private. Please click 'Share' in Google Sheets and set access to 'Anyone with the link can view'."))

                reader = csv.DictReader(io.StringIO(content))
                records = list(reader)
                if records:
                    return records
            except UserError as ue:
                raise ue
            except Exception as e:
                last_error = str(e)
                continue

        raise UserError(_("Could not fetch Google Sheet CSV. Please verify your Spreadsheet ID/URL. Technical detail: %s") % (last_error or 'HTTP 404 Not Found'))

    @classmethod
    def get_service_account_token(cls, service_account_info):
        """Obtains OAuth2 access token for Google API using service account credentials."""
        try:
            from google.oauth2 import service_account
            import google.auth.transport.requests

            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
            )
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)
            return credentials.token
        except Exception as e:
            _logger.info("google-auth package refresh failed or missing, trying jwt fallback: %s", str(e))
            try:
                import jwt
                now = int(time.time())
                payload = {
                    'iss': service_account_info.get('client_email'),
                    'scope': 'https://www.googleapis.com/auth/spreadsheets.readonly',
                    'aud': service_account_info.get('token_uri', 'https://oauth2.googleapis.com/token'),
                    'exp': now + 3600,
                    'iat': now
                }
                private_key = service_account_info.get('private_key')
                signed_jwt = jwt.encode(payload, private_key, algorithm='RS256')
                if isinstance(signed_jwt, bytes):
                    signed_jwt = signed_jwt.decode('utf-8')

                req_data = urllib.parse.urlencode({
                    'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                    'assertion': signed_jwt
                }).encode('utf-8')

                token_url = service_account_info.get('token_uri', 'https://oauth2.googleapis.com/token')
                req = urllib.request.Request(token_url, data=req_data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
                with urllib.request.urlopen(req, timeout=15) as response:
                    res_body = json.loads(response.read().decode('utf-8'))
                    return res_body.get('access_token')
            except Exception as jwt_err:
                _logger.error("Failed to get Google API Access Token: %s", str(jwt_err))
                raise UserError(_("Could not authenticate with Google Sheets API. Please check your Service Account JSON credentials."))

    @classmethod
    def fetch_sheet_values(cls, spreadsheet_id, sheet_name=None, json_credentials_str=None):
        """
        Fetches all rows from a given spreadsheet and sheet tab name.
        If json_credentials_str is empty/not a valid Service Account JSON dict, uses Zero-Config Public CSV fetch.
        """
        clean_id = cls._clean_spreadsheet_id(spreadsheet_id)
        if not clean_id:
            return []

        credentials_info = None
        if json_credentials_str and str(json_credentials_str).strip():
            try:
                parsed = json.loads(str(json_credentials_str).strip())
                if isinstance(parsed, dict) and 'type' in parsed:
                    credentials_info = parsed
            except Exception:
                credentials_info = None

        if not credentials_info:
            _logger.info("No valid JSON Credentials dictionary provided. Using Zero-Config Public CSV fetch for spreadsheet_id=%s, sheet_name=%s", clean_id, sheet_name)
            return cls.fetch_public_sheet_csv(clean_id, sheet_name)

        # Try gspread if available
        try:
            import gspread
            gc = gspread.service_account_from_dict(credentials_info)
            sh = gc.open_by_key(clean_id)
            worksheet = sh.worksheet(sheet_name) if sheet_name else sh.get_worksheet(0)
            records = worksheet.get_all_records()
            return records
        except Exception as gspread_err:
            _logger.info("gspread approach failed or not installed: %s. Using REST API fallback.", str(gspread_err))

        # REST API Fallback
        token = cls.get_service_account_token(credentials_info)
        if not token:
            return cls.fetch_public_sheet_csv(clean_id, sheet_name)

        encoded_sheet_name = urllib.parse.quote(sheet_name or 'Sheet1')
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{clean_id}/values/{encoded_sheet_name}?valueRenderOption=FORMATTED_VALUE"

        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                values = res_data.get('values', [])
                if not values or len(values) < 2:
                    return []

                headers = [str(h).strip() for h in values[0]]
                records = []
                for row in values[1:]:
                    padded_row = row + [''] * (len(headers) - len(row))
                    record_dict = {headers[i]: padded_row[i] for i in range(len(headers))}
                    records.append(record_dict)
                return records
        except Exception as req_err:
            _logger.info("Service Account API request failed: %s. Falling back to Public CSV fetch.", str(req_err))
            return cls.fetch_public_sheet_csv(clean_id, sheet_name)
