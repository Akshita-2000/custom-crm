# -*- coding: utf-8 -*-
from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    voiso_user_id = fields.Char(
        string="Voiso User ID",
        help="Numeric user ID in Voiso (retrieved via Voiso GET /users API). Required for Click-to-Call.",
        copy=False
    )
