# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import itertools
import psycopg2

import odoo.addons.decimal_precision as dp

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, except_orm


class ProductTemplate(models.Model):
    _inherit = "product.template"
    
    base_price	=  fields.Boolean(string="Base Price", store=True, default=False )
    element_id = fields.Many2one("qaqc.chemical.element", string="Element", ondelete="restrict" )
    
    # mining_type = fields.Selection([
    #     ('base', 'Base'),
    #     ('ni', 'Nickel'),
    #     ('fe', 'Fe'),
    #     ('moisture', 'Moisture'),
    # ], string='Sale Mining Type',  store=True)