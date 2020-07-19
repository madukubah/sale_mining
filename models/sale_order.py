from odoo import api, exceptions, fields, models, _, SUPERUSER_ID
import odoo.addons.decimal_precision as dp
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"

    coa_id = fields.Many2one("qaqc.coa", string="QAQC COA", required=True, store=True, ondelete="restrict" )
    # shipping_id = fields.Many2one("shipping.shipping", string="Shipping", required=True, store=True, ondelete="restrict", domain=[ ('state','=',"approve")], readonly=True, states={'draft': [('readonly', False)]}  )
    contract_id = fields.Many2one(
		'sale.contract',
		string='Contract', 
        store=True,
        readonly=True,
        related="partner_id.contract_id",
		)
    park_industry_id = fields.Many2one(
		'sale.park.industry',
		string='Park Industry', 
        store=True,
        readonly=True,
        related="partner_id.park_industry_id",
		)

    @api.onchange("coa_id" )
    def _set_orderline(self):
        _logger.warning( "_set_orderline" )
        _logger.warning( self.coa_id.quantity )
        for line in self.order_line :
            line.product_uom_qty = self.coa_id.quantity

    @api.onchange("partner_id" )
    def onchange_contract_id(self):
        for line in self.order_line :
            line.product_id_change()

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    coa_id = fields.Many2one("qaqc.coa", related='order_id.coa_id', store=True, readonly=True ,string="QAQC COA", required=True, ondelete="restrict" )
    contract_id = fields.Many2one("sale.contract", related='order_id.contract_id', store=True, readonly=True ,string="Contract", required=True, ondelete="restrict" )
    park_industry_id = fields.Many2one("sale.park.industry", related='order_id.park_industry_id', store=True, readonly=True ,string="Park Industry", required=True, ondelete="restrict" )
    
    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        super(SaleOrderLine, self).product_id_change()
        
        _logger.warning( "_set_orderline" )
        _logger.warning( self.product_id.name )

        if( self.coa_id ) :
            self.product_uom_qty = self.coa_id.quantity

        self.set_price_unit()
        # if( self.order_id.contract_id and self.order_id.park_industry_id ) :
        #     self.price_unit = self.order_id.contract_id.base_price * self.order_id.park_industry_id.currency_80_pc
    
    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        super(SaleOrderLine, self).product_uom_change()

        self.set_price_unit()
        # if( self.order_id.contract_id and self.order_id.park_industry_id ) :
        #     self.price_unit = self.order_id.contract_id.base_price * self.order_id.park_industry_id.currency_80_pc

    def set_price_unit(self):
        if( self.contract_id and self.park_industry_id ) :
            _logger.warning( "set_price_unit" )
            _logger.warning( self.product_id.mining_type )

            coa = self.coa_id
            contract = self.contract_id
            park_industry = self.park_industry_id

            _logger.warning( coa.ni_spec )
            _logger.warning( contract.ni_spec )

            if( self.product_id.mining_type == 'base' ):
                self.price_unit = contract.base_price * park_industry.currency_80_pc

            # nickel price adjustment
            elif( self.product_id.mining_type == 'ni' ):
                if( coa.ni_spec > contract.ni_spec ) : 
                    self.price_unit = contract.base_price * contract.ni_price_adjustment_bonus
                    self.name = 'Bonus'
                if( coa.ni_spec < contract.ni_spec ) : 
                    self.price_unit = contract.base_price * contract.ni_price_adjustment_penalty * (-1)
                    self.name = 'Penalty'
            # fe price adjustment
            elif( self.product_id.mining_type == 'fe' ):
                if( coa.fe_spec > contract.fe_spec_to ) : 
                    self.price_unit = contract.base_price * contract.fe_price_adjustment_bonus
                    self.name = 'Bonus'
                if( coa.fe_spec < contract.fe_spec_from ) : 
                    self.price_unit = contract.base_price * contract.fe_price_adjustment_penalty * (-1)
                    self.name = 'Penalty'
            # moisture price adjustment
            elif( self.product_id.mining_type == 'moisture' ):
                if( coa.moisture_spec < contract.moisture_spec_from ) : 
                    self.price_unit = contract.base_price * contract.moisture_price_adjustment_bonus
                    self.name = 'Bonus'
                if( coa.moisture_spec > contract.moisture_spec_to ) : 
                    self.price_unit = contract.base_price * contract.moisture_price_adjustment_penalty * (-1)
                    self.name = 'Penalty'