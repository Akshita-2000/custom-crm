# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from ..models.voiso_mixin import end_voiso_call


class VoisoActiveCallWizard(models.TransientModel):
    _name = 'voiso.active.call.wizard'
    _description = 'Voiso Active Call Screen'

    call_id = fields.Char(string="Voiso Call ID", required=True)
    customer_name = fields.Char(string="Customer Name", required=True)
    phone_masked = fields.Char(string="Phone Number", required=True)
    res_model = fields.Char(string="Related Model")
    res_id = fields.Integer(string="Related Record ID")
    call_status = fields.Char(string="Status", default="In Progress")

    def action_end_call(self):
        """Hangs up / terminates active Voiso call and closes modal."""
        self.ensure_one()
        target_record = False
        if self.res_model and self.res_id:
            try:
                target_record = self.env[self.res_model].browse(self.res_id)
            except Exception:
                pass

        end_voiso_call(self.env, self.call_id, target_record=target_record)

        # Closes the modal window immediately
        return {'type': 'ir.actions.act_window_close'}
