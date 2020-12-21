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
        domain=[ ('state','=',"confirm") ], 
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
    
    income_account_id = fields.Many2one('account.account', 
        string='Income Account', 
        required=True,
        domain=[('deprecated', '=', False), ('user_type_id', '=', 14 ) ], 
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
    hpm_price = fields.Float( string="HPM + Shipping Cost", default=0, digits=dp.get_precision('Product Unit of Measure') )

    @api.multi
    def action_confirm(self):
        super(SaleOrder, self).action_confirm()
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

    @api.onchange("coa_id", "contract_id" )
    def compute_hpm(self):
        if( self.coa_id and self.contract_id ) :
            base_price = self.contract_id.get_base_price_amount(self.coa_id.id , self.contract_id.id )
            self.hpm_price = base_price
            self._set_orderline()

    @api.onchange("mining_payment_type", "currency", "hpm_price" )
    def _set_orderline(self):
        for line in self.order_line :
            line.set_price_unit()

    @api.onchange("income_account_id", "partner_id" )
    def _onchange_income_account_id(self):
        for line in self.order_line :
            line.product_id_change()
    

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    income_account_id = fields.Many2one('account.account', 
        string='Income Account', 
        related='order_id.income_account_id',
        readonly=True,
        domain=[('deprecated', '=', False)], 
        )
    coa_id = fields.Many2one("qaqc.coa.order", related='order_id.coa_id', store=True, readonly=True ,string="QAQC COA", ondelete="restrict" )
    contract_id = fields.Many2one("sale.contract", related='order_id.contract_id', store=True, readonly=True ,string="Contract", ondelete="restrict" )
    park_industry_id = fields.Many2one("sale.park.industry", related='order_id.park_industry_id', store=True, readonly=True ,string="Park Industry", ondelete="restrict" )
    
    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        super(SaleOrderLine, self).product_id_change()
        for line in self:
            if( line.coa_id and line.product_id ) :
                if( line.product_id.base_price and line.product_id.type == "product" ) :
                    line.product_uom_qty = line.coa_id.quantity
                if( line.income_account_id ) :
                    line.product_id.write({"property_account_income_id" : line.income_account_id.id })

            line.set_price_unit()
        
    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        super(SaleOrderLine, self).product_uom_change()
        for line in self:
            line.set_price_unit()

    def set_price_unit(self):
        for line in self:
            if( line.contract_id and line.coa_id ) :
                coa = line.coa_id
                contract = line.contract_id

                if( line.order_id.mining_payment_type == "80_pc" ) :
                    if( line.product_id.base_price ):
                        line.price_unit = line.order_id.hpm_price * line.order_id.currency
                    elif( line.product_id.element_id ):
                        line.price_unit = 0  
                elif( line.order_id.mining_payment_type == "20_pc" ) : 
                    if( line.product_id.base_price ):
                        line.price_unit = line.order_id.hpm_price * line.order_id.currency
                    if( line.product_id.element_id ):
                        _coa_element_spec = None
                        _contract_specification = None
                        for element_spec in coa.element_specs :
                            if element_spec.element_id == line.product_id.element_id :
                                _coa_element_spec = element_spec
                                break

                        for specification in contract.specifications :
                            if specification.element_id == line.product_id.element_id :
                                _contract_specification = specification
                                break
                        if( _coa_element_spec and _contract_specification ) :
                            result = _contract_specification._compute_price_based_on_rules( _coa_element_spec )
                            line.name = result["name"]
                            line.price_unit = result["price"] * line.order_id.currency

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
            rule = Rule.search([ ("location_src_id", '=', line.coa_id.location_id.id ), ("warehouse_id", '=', line.coa_id.warehouse_id.id ) ])
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
