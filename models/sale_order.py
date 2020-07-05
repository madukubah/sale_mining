from odoo import api, exceptions, fields, models, _, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"

    coa_id = fields.Many2one("qaqc.coa", string="QAQC COA", required=True, store=True, ondelete="restrict" )
    # shipping_id = fields.Many2one("shipping.shipping", string="Shipping", required=True, store=True, ondelete="restrict", domain=[ ('state','=',"approve")], readonly=True, states={'draft': [('readonly', False)]}  )

    # @api.onchange("coa_id" )
    # def _set_orderline(self):
    #     # for rec in self:
    #     products = self.env['product.product'].search([])
    #     _logger.warning( "product.product" )
    #     OD_L = self.env['sale.order.line']
    #     ctx = dict(self.env.context )
    #     uid = SUPERUSER_ID if self.env.user.has_group('point_of_sale.group_pos_user') else self.env.user.id

    #     order_lines = []
    #     for product in products:
    #         _logger.warning( product.name )
    #         values = {
    #             'name': self.name,
    #             'origin': self.order_id.name,
    #             'date_planned': datetime.strptime(self.order_id.date_order, DEFAULT_SERVER_DATETIME_FORMAT) + timedelta(days=self.customer_lead),
    #             'product_id': self.product_id.id,
    #             'product_qty': self.product_uom_qty,
    #             'product_uom': self.product_uom.id,
    #             'company_id': self.order_id.company_id.id,
    #             'group_id': group_id,
    #             'sale_line_id': self.id
    #         }
    #         order_lines.append(OD_L.with_context(ctx).sudo(uid).create(values).id)

    # @api.onchange("coa_id" )
    # def add_to_offer(self):
    #     line_env = self.env['sale.order.line']
    #     products = self.env['product.product'].search([])
    #     for product in products:
    #         for wizard in self:
    #             _logger.warning( "wizard.entries" )
    #             _logger.warning( wizard.id )
    #             # for what in wizard.entries:
    #             new_line = line_env.create({
    #                 'product_id': product.id,
    #                 'name': product.name,
    #                 'order_id': wizard.id,
    #                 'product_uom' : product.uom_id.id})                
    #             new_line.product_id_change() #Calling an onchange method to update the record
    @api.onchange("coa_id" )
    def _set_orderline(self):
        _logger.warning( "_set_orderline" )
        _logger.warning( self.coa_id.quantity )
        for line in self.order_line :
            line.product_uom_qty = self.coa_id.quantity
            

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    coa_id = fields.Many2one("qaqc.coa", related='order_id.coa_id', store=True, readonly=True ,string="QAQC COA", required=True, ondelete="restrict" )

    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        super(SaleOrderLine, self).product_id_change()

        _logger.warning( "coa_id" )
        _logger.warning( self.coa_id.quantity )
        if( self.coa_id ) :
            self.product_uom_qty = self.coa_id.quantity

    
    