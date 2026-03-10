"""kwtSMS Message Template model."""

import logging

from odoo import models, fields, api, _

from odoo.addons.kwtsms_sms.tools.phone_utils import count_sms_parts

_logger = logging.getLogger(__name__)


class KwtSmsTemplate(models.Model):
    """Multilingual SMS templates with placeholders."""

    _name = 'kwtsms.sms.template'
    _description = 'kwtSMS Message Template'
    _order = 'event_type, lang, name'

    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
    )
    event_type = fields.Selection([
        ('order_confirm', 'Order Confirmation'),
        ('order_cancel', 'Order Cancelled'),
        ('delivery_done', 'Delivery Completed'),
        ('invoice_posted', 'Invoice Posted'),
        ('payment_received', 'Payment Received'),
        ('custom', 'Custom'),
    ], string='Event Type', required=True, default='custom')
    lang = fields.Selection([
        ('en', 'English'),
        ('ar', 'Arabic'),
    ], string='Language', required=True, default='en')
    body = fields.Text(
        string='Message Body',
        required=True,
        translate=True,
        help='Use placeholders: #order_name#, #customer_name#, #amount#, '
             '#company_name#, #picking_name#, #tracking_ref#, '
             '#invoice_name#, #payment_ref#, #amount_paid#',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Related Model',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    char_count = fields.Integer(
        string='Characters',
        compute='_compute_sms_info',
        store=True,
    )
    page_count = fields.Integer(
        string='SMS Pages',
        compute='_compute_sms_info',
        store=True,
    )
    is_unicode = fields.Boolean(
        string='Unicode',
        compute='_compute_sms_info',
        store=True,
    )

    @api.depends('body')
    def _compute_sms_info(self):
        for record in self:
            if record.body:
                chars, pages, unicode_msg = count_sms_parts(record.body)
                record.char_count = chars
                record.page_count = pages
                record.is_unicode = unicode_msg
            else:
                record.char_count = 0
                record.page_count = 0
                record.is_unicode = False

    def render_template(self, record):
        """Render template by replacing placeholders with record values.

        Supports both #placeholder# and {placeholder} syntax.

        Args:
            record: Odoo recordset to get values from.

        Returns:
            str: Rendered message text.
        """
        self.ensure_one()
        if not self.body:
            return ''

        values = {}
        if hasattr(record, 'name'):
            values['order_name'] = record.name or ''
            values['picking_name'] = record.name or ''
            values['invoice_name'] = record.name or ''
            values['payment_ref'] = record.name or ''
        if hasattr(record, 'partner_id') and record.partner_id:
            values['customer_name'] = record.partner_id.name or ''
        if hasattr(record, 'amount_total'):
            currency = record.currency_id.symbol if hasattr(record, 'currency_id') and record.currency_id else ''
            values['amount'] = '%s %s' % (record.amount_total, currency)
        if hasattr(record, 'amount') and not hasattr(record, 'amount_total'):
            currency = record.currency_id.symbol if hasattr(record, 'currency_id') and record.currency_id else ''
            values['amount_paid'] = '%s %s' % (record.amount, currency)
            values['amount'] = '%s %s' % (record.amount, currency)
        if hasattr(record, 'ref') and record.ref:
            values['payment_ref'] = record.ref
        if hasattr(record, 'company_id') and record.company_id:
            values['company_name'] = record.company_id.name or ''
        elif self.env.company:
            values['company_name'] = self.env.company.name or ''
        if hasattr(record, 'carrier_tracking_ref'):
            values['tracking_ref'] = record.carrier_tracking_ref or ''

        result = self.body
        for key, val in values.items():
            result = result.replace('#%s#' % key, str(val))
            result = result.replace('{%s}' % key, str(val))

        # Clean up fragments left by empty placeholders
        import re
        # Remove unreplaced placeholders (both syntaxes)
        result = re.sub(r'#\w+#', '', result)
        result = re.sub(r'\{\w+\}', '', result)
        # Remove label patterns like "Tracking: " when value was empty
        result = re.sub(r'\S+:\s*$', '', result, flags=re.MULTILINE)
        # Collapse multiple spaces
        result = re.sub(r'  +', ' ', result)
        return result.strip()

    @api.model
    def get_template_for_event(self, event_type, lang='en'):
        """Find an active template for the given event type and language.

        Falls back to English if no template found for requested language.

        Args:
            event_type: Event type selection value.
            lang: Language code ('en' or 'ar').

        Returns:
            recordset: Template record, or empty recordset if not found.
        """
        template = self.search([
            ('event_type', '=', event_type),
            ('lang', '=', lang),
            ('active', '=', True),
        ], limit=1)

        if not template and lang != 'en':
            template = self.search([
                ('event_type', '=', event_type),
                ('lang', '=', 'en'),
                ('active', '=', True),
            ], limit=1)

        return template
