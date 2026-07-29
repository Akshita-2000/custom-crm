# CRM Lead Synchronization & Auto Assignment (Odoo 17 Community Edition)

## Overview
This module automates the process of reading leads from two Google Sheets, storing them in a intermediate **Master Lead** repository (`crm.master.lead`), detecting and skipping duplicate records, and allowing CRM Managers to distribute unimported leads among active salespeople using an interactive distribution wizard before importing them into Odoo CRM (`crm.lead`).

## Structure & Architecture
- **Google Sheets API Service**: Connects via Service Account JSON credentials to Google Sheets REST API.
- **Scheduled Action (Cron)**: Runs automatically every 5 minutes to fetch, parse, deduplicate, and record leads.
- **Master Lead Repository**: intermediate model holding all raw and deduplicated lead records with filters (Today, Yesterday, This Week, Assigned/Not Assigned, Imported/Not Imported).
- **Import Wizard (`TransientModel`)**: Loads active CRM Salespeople dynamically and enforces strict lead total validations before sequential auto-assignment.
- **Audit Logging & History**: Full audit trail of sync execution logs (`crm.lead.sync.log`) and import allocations history (`crm.lead.import.history`).

## Menus
`CRM -> Lead Synchronization`
- **Master Leads**: View, search, and group synchronized leads.
- **Import Leads**: Open auto-assignment distribution wizard.
- **Import History**: Review past lead distribution batches.
- **Google Sheet Settings**: Configure Spreadsheet ID, sheet names, and Service Account JSON credentials.
- **Sync Logs**: View cron job and manual synchronization execution logs.
