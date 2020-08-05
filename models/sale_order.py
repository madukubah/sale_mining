from odoo import api, exceptions, fields, models, _, SUPERUSER_ID
import odoo.addons.decimal_precision as dp
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"

    # coa_id = fields.Many2one("qaqc.coa", string="QAQC COA", required=True, store=True, ondelete="restrict" )
    coa_id = fields.Many2one("qaqc.coa", 
        string="QAQC COA", 
        required=True, store=True, 
        ondelete="restrict", domain=[ "|", "&",('state','=',"final"), ('state','=',"draft") , ('surveyor_id.surveyor','=',"intertek") ], 
        readonly=True, states={'draft': [('readonly', False)]}  
        )
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

    @api.onchange("coa_id" )
    def _set_orderline(self):
        for line in self.order_line :
            line.product_uom_qty = self.coa_id.quantity

    @api.onchange("mining_payment_type", "currency" )
    def _set_orderline(self):
        for line in self.order_line :
            line.set_price_unit()

    @api.onchange("partner_id" )
    def onchange_contract_id(self):
        for line in self.order_line :
            line.product_id_change()

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    coa_id = fields.Many2one("qaqc.coa", related='order_id.coa_id', store=True, readonly=True ,string="QAQC COA", ondelete="restrict" )
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
        if( self.contract_id and self.park_industry_id ) :
            coa = self.coa_id
            contract = self.contract_id
            park_industry = self.park_industry_id
            if( self.order_id.mining_payment_type == "80_pc" ) :
                if( self.product_id.mining_type == 'base' ):
                    self.price_unit = contract.base_price * self.order_id.currency
                else :
                    self.price_unit = 0

            elif( self.order_id.mining_payment_type == "20_pc" ) : 
                if( self.product_id.mining_type == 'base' ):
                    self.price_unit = contract.base_price * self.order_id.currency
                # nickel price adjustment
                elif( self.product_id.mining_type == 'ni' ):
                    if( coa.ni_spec > contract.ni_spec ) : 
                        self.price_unit = self.order_id.currency * contract.ni_price_adjustment_bonus
                        self.name = 'Ni Bonus'
                    if( coa.ni_spec < contract.ni_spec ) : 
                        self.price_unit = self.order_id.currency * contract.ni_price_adjustment_penalty * (-1)
                        self.name = 'Ni Penalty'
                # fe price adjustment
                elif( self.product_id.mining_type == 'fe' ):
                    if( coa.fe_spec > contract.fe_spec_to ) : 
                        self.price_unit = self.order_id.currency * contract.fe_price_adjustment_bonus
                        self.name = 'Fe Bonus'
                    if( coa.fe_spec < contract.fe_spec_from ) : 
                        self.price_unit = self.order_id.currency * contract.fe_price_adjustment_penalty * (-1)
                        self.name = 'Fe Penalty'
                # moisture price adjustment
                elif( self.product_id.mining_type == 'moisture' ):
                    if( coa.mc_spec < contract.moisture_spec_from ) : 
                        self.price_unit = self.order_id.currency * contract.moisture_price_adjustment_bonus
                        self.name = 'MC Bonus'
                    if( coa.mc_spec > contract.moisture_spec_to ) : 
                        self.price_unit = self.order_id.currency * contract.moisture_price_adjustment_penalty * (-1)
                        self.name = 'MC Penalty'


    # def set_price_unit(self):
    #     if( self.contract_id and self.park_industry_id ) :
    #         coa = self.coa_id
    #         contract = self.contract_id
    #         park_industry = self.park_industry_id
    #         if( self.order_id.mining_payment_type == "80_pc" ) :
    #             if( self.product_id.mining_type == 'base' ):
    #                 self.price_unit = contract.base_price * park_industry.currency_80_pc
    #             else :
    #                 self.price_unit = 0

    #         elif( self.order_id.mining_payment_type == "20_pc" ) : 
    #             if( self.product_id.mining_type == 'base' ):
    #                 self.price_unit = contract.base_price * park_industry.currency_20_pc
    #             # nickel price adjustment
    #             elif( self.product_id.mining_type == 'ni' ):
    #                 if( coa.ni_spec > contract.ni_spec ) : 
    #                     self.price_unit = park_industry.currency_20_pc * contract.ni_price_adjustment_bonus
    #                     self.name = 'Bonus'
    #                 if( coa.ni_spec < contract.ni_spec ) : 
    #                     self.price_unit = park_industry.currency_20_pc * contract.ni_price_adjustment_penalty * (-1)
    #                     self.name = 'Penalty'
    #             # fe price adjustment
    #             elif( self.product_id.mining_type == 'fe' ):
    #                 if( coa.fe_spec > contract.fe_spec_to ) : 
    #                     self.price_unit = park_industry.currency_20_pc * contract.fe_price_adjustment_bonus
    #                     self.name = 'Bonus'
    #                 if( coa.fe_spec < contract.fe_spec_from ) : 
    #                     self.price_unit = park_industry.currency_20_pc * contract.fe_price_adjustment_penalty * (-1)
    #                     self.name = 'Penalty'
    #             # moisture price adjustment
    #             elif( self.product_id.mining_type == 'moisture' ):
    #                 if( coa.mc_spec < contract.moisture_spec_from ) : 
    #                     self.price_unit = park_industry.currency_20_pc * contract.moisture_price_adjustment_bonus
    #                     self.name = 'Bonus'
    #                 if( coa.mc_spec > contract.moisture_spec_to ) : 
    #                     self.price_unit = park_industry.currency_20_pc * contract.moisture_price_adjustment_penalty * (-1)
    #                     self.name = 'Penalty'