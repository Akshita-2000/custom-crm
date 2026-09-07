# -*- coding: utf-8 -*-
from odoo import models, fields, api
from .voiso_mixin import make_voiso_call, mask_phone_number

class CustomCrmLead(models.Model):
    _inherit = 'custom.crm.lead'

    phone_masked = fields.Char(string="Phone Number", compute="_compute_phone_masked")
    mobile_masked = fields.Char(string="Mobile Number", compute="_compute_phone_masked")

    @api.depends('phone', 'mobile')
    def _compute_phone_masked(self):
        for rec in self:
            rec.phone_masked = mask_phone_number(rec.phone)
            rec.mobile_masked = mask_phone_number(rec.mobile)

    def action_voiso_call_phone(self):
        self.ensure_one()
        return make_voiso_call(self.env, self, self.phone, number_type='Phone')

    def action_voiso_call_mobile(self):
        self.ensure_one()
        return make_voiso_call(self.env, self, self.mobile, number_type='Mobile')
