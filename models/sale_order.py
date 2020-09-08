from odoo import api, exceptions, fields, models, _, SUPERUSER_ID
import odoo.addons.decimal_precision as dp
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"

    # partner_id = fields.Many2one('res.partner', 
    #     string='Customer', readonly=True, 
    #     related="contract_id.factory_id",
    #     required=True, change_default=True, index=True, track_visibility='always')

    shipping_id = fields.Many2one("shipping.order", 
        string="Shipping", 
        required=True, store=True, 
        ondelete="restrict", 
        domain=[ ('state','=',"approve") ], 
        readonly=True, 
        states={'draft': [('readonly', False)]}  
        )
    coa_id = fields.Many2one("qaqc.coa.order", 
        string="QAQC COA", 
        related="shipping_id.coa_id",
        store=True, 
        ondelete="restrict", 
        # domain=[ "&",('state','=',"final") , ('surveyor_id.surveyor','=',"intertek") ], 
        readonly=True, 
        # states={'draft': [('readonly', False)]}  
        )
    contract_id = fields.Many2one(
		'sale.contract',
		string='Contract', 
        store=True,
        readonly=True,
        related="shipping_id.sale_contract_id",
		)
    park_industry_id = fields.Many2one(
		'sale.park.industry',
		string='Park Industry', 
        store=True,
        readonly=True,
        related="partner_id.park_industry_id",
		)
    mining_payment_type = fields.Selection([
        ('80_pc', 'DP 80 %'), 
		('20_pc', 'Full Payment 20 %'),
        ], string='Payment Type', required=True, copy=False, index=True, default='80_pc')
    currency = fields.Float( string="Currency (IDR)", required=True, default=0 )


    @api.multi
    def action_confirm(self):
        super(SaleOrder, self).action_confirm()
        # QaqcCoaSudo = self.env['qaqc.coa'].sudo()
        # coa = QaqcCoaSudo.search([ ("id", '=', self.coa_id.id ) ])
        # coa.button_done()
        return True

    @api.onchange("contract_id" )
    def onchange_contract_id(self):
        sale_contract_id = self.shipping_id.sale_contract_id
        if sale_contract_id : 
            self.partner_id = sale_contract_id.factory_id

    @api.onchange("coa_id" )
    def onchange_coa_id(self):
        for line in self.order_line :
            line.product_uom_qty = self.coa_id.quantity

    @api.onchange("mining_payment_type", "currency" )
    def _set_orderline(self):
        for line in self.order_line :
            line.set_price_unit()

    @api.onchange("partner_id" )
    def _onchange_partner_id(self):
        for line in self.order_line :
            line.product_id_change()

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    coa_id = fields.Many2one("qaqc.coa.order", related='order_id.coa_id', store=True, readonly=True ,string="QAQC COA", ondelete="restrict" )
    contract_id = fields.Many2one("sale.contract", related='order_id.contract_id', store=True, readonly=True ,string="Contract", ondelete="restrict" )
    park_industry_id = fields.Many2one("sale.park.industry", related='order_id.park_industry_id', store=True, readonly=True ,string="Park Industry", ondelete="restrict" )
    
    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        super(SaleOrderLine, self).product_id_change()

        if( self.coa_id ) :
            self.product_uom_qty = self.coa_id.quantity

        self.set_price_unit()
    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        super(SaleOrderLine, self).product_uom_change()
        self.set_price_unit()

    def set_price_unit(self):
        if( self.contract_id and self.coa_id ) :
            coa = self.coa_id
            contract = self.contract_id
            if( self.order_id.mining_payment_type == "80_pc" ) :
                if( self.product_id.base_price ):
                    self.price_unit = contract.base_price * self.order_id.currency
                elif( self.product_id.element_id ):
                    self.price_unit = 0  
            elif( self.order_id.mining_payment_type == "20_pc" ) : 
                if( self.product_id.base_price ):
                    self.price_unit = contract.base_price * self.order_id.currency
                if( self.product_id.element_id ):
                    _coa_element_spec = None
                    _contract_specification = None
                    for element_spec in coa.element_specs :
                        if element_spec.element_id == self.product_id.element_id :
                            _coa_element_spec = element_spec
                            break

                    for specification in contract.specifications :
                        if specification.element_id == self.product_id.element_id :
                            _contract_specification = specification
                            break
                    if( _coa_element_spec and _contract_specification ) :
                        result = _contract_specification._compute_price_based_on_rules( _coa_element_spec )
                        self.name = result["name"]
                        self.price_unit = result["price"] * self.order_id.currency