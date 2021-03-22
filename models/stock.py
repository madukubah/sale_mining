# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.multi
    def do_new_transfer(self):
        super(StockPicking, self).do_new_transfer()
        for pick in self:
            sale_id = pick.sale_id
            if sale_id :
                QaqcCoaSudo = self.env['qaqc.coa.order'].sudo()
                ShippingSudo = self.env['shipping.order'].sudo()
                BargeActivitySudo = self.env['shipping.barge.activity'].sudo()

                coa = QaqcCoaSudo.search([ ("id", '=', sale_id.coa_id.id ) ])
                shipping = ShippingSudo.search([ ("id", '=', sale_id.shipping_id.id ) ])
                barge_activity = BargeActivitySudo.search([ ("id", '=', shipping.barge_activity_id.id ) ])
                if( coa and shipping ):
                    coa.action_done()
                    shipping.action_done()
                    barge_activity.action_done()
                else : 
                    raise UserError(_('Assay Result Barge, Shipping and Barging File is Required To Do This Action') )
