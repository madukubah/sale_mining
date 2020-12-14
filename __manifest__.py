# -*- coding: utf-8 -*-

{
    'name': 'Sale Mining',
    'version': '1.0',
    'author': 'Technoindo.com',
    'category': 'Sales Management',
    'depends': [
        'sale_contract',
        'shipping',
        'mining_qaqc_chemical_element',
        'sale_stock',
        'sales_team',
    ],
    'data': [
        'views/sale_order.xml',
        'views/product_template.xml',

        'security/ir.model.access.csv',
    ],
    'qweb': [
        # 'static/src/xml/cashback_templates.xml',
    ],
    'demo': [
        # 'demo/sale_agent_demo.xml',
    ],
    "installable": True,
	"auto_instal": False,
	"application": False,
}
