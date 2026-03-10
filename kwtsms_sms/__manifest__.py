{
    'name': 'kwtSMS Gateway',
    'version': '19.0.1.1.0',
    'summary': 'Send SMS via kwtSMS gateway with business event notifications',
    'description': """
kwtSMS Gateway for Odoo
=======================

Replace Odoo IAP SMS with kwtSMS gateway. Features:

* Direct kwtSMS API integration
* Auto-SMS on order confirmation, cancellation, delivery, invoice, and payment
* Multilingual templates (English + Arabic)
* Full SMS audit log
* Phone normalization for GCC numbers
* Bulk sending with automatic batching
    """,
    'author': 'BoxLink',
    'website': 'https://boxlink.net',
    'support': 'mo@boxlink.net',
    'category': 'Marketing/SMS Marketing',
    'license': 'OPL-1',
    'price': 49.00,
    'currency': 'USD',
    'depends': [
        'base',
        'sms',
        'sale_management',
        'stock',
        'account',
        'mail',
    ],
    'data': [
        'security/kwtsms_security.xml',
        'security/ir.model.access.csv',
        'data/kwtsms_data.xml',
        'data/ir_cron_data.xml',
        'views/kwtsms_sms_log_views.xml',
        'views/kwtsms_sms_template_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/sms_compose_wizard_views.xml',
        'wizard/test_sms_wizard_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'kwtsms_sms/static/src/css/kwtsms_styles.css',
            'kwtsms_sms/static/src/js/test_sms_widget.js',
            'kwtsms_sms/static/src/xml/test_sms_widget.xml',
        ],
    },
    'external_dependencies': {},
    'application': True,
    'installable': True,
    'auto_install': False,
    'images': [
        'static/description/banner.png',
    ],
}
