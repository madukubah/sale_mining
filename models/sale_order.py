from odoo import api, exceptions, fields, models, _, SUPERUSER_ID
import odoo.addons.decimal_precision as dp
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
import logging
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"

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
        if( self.coa_id ) :
            self.warehouse_id = self.coa_id.warehouse_id

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
    

    @api.multi
    def _action_procurement_create(self):
        """
        Create procurements based on quantity ordered. If the quantity is increased, new
        procurements are created. If the quantity is decreased, no automated action is taken.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        new_procs = self.env['procurement.order']  # Empty recordset
        Rule = self.env['procurement.rule']  

        for line in self:
            if line.state != 'sale' or not line.product_id._need_procurement():
                continue
            qty = 0.0
            for proc in line.procurement_ids.filtered(lambda r: r.state != 'cancel'):
                qty += proc.product_qty
            if float_compare(qty, line.product_uom_qty, precision_digits=precision) >= 0:
                continue

            if not line.order_id.procurement_group_id:
                vals = line.order_id._prepare_procurement_group()
                line.order_id.procurement_group_id = self.env["procurement.group"].create(vals)

            vals = line._prepare_order_line_procurement(group_id=line.order_id.procurement_group_id.id)
            vals['product_qty'] = line.product_uom_qty - qty
            # find procurement.rule
            rule = Rule.search([ ("location_src_id", '=', self.coa_id.location_id.id ), ("warehouse_id", '=', self.coa_id.warehouse_id.id ) ])
            if len(rule) > 0 :
                vals['rule_id'] = rule[0].id
            else :
                raise UserError(_('Please Set Up Procurement Rule And Picking Type in Location Properly') )
                

            new_proc = self.env["procurement.order"].with_context(procurement_autorun_defer=True).create(vals)
            new_proc.message_post_with_view('mail.message_origin_link',
                values={'self': new_proc, 'origin': line.order_id},
                subtype_id=self.env.ref('mail.mt_note').id)
            new_procs += new_proc
        new_procs.run()
        return new_procs
