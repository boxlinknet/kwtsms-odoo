"""kwtSMS settings page integrated into Odoo Settings."""

import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    """kwtSMS configuration in Settings > kwtSMS Gateway."""

    _inherit = 'res.config.settings'

    # General Settings (manually persisted to avoid Odoo deleting param on False)
    kwtsms_enabled = fields.Boolean(
        string='Enable kwtSMS Gateway',
        default=True,
    )
    kwtsms_test_mode = fields.Boolean(
        string='Test Mode',
        default=True,
        help='When enabled, SMS messages are queued but not delivered.',
    )
    kwtsms_default_country_code = fields.Char(
        string='Default Country Code',
        config_parameter='kwtsms.default_country_code',
        default='965',
    )
    kwtsms_log_retention_days = fields.Integer(
        string='Log Retention (Days)',
        config_parameter='kwtsms.log_retention_days',
        default=90,
    )

    # Gateway Settings
    kwtsms_api_username = fields.Char(
        string='API Username',
        config_parameter='kwtsms.api_username',
    )
    kwtsms_api_password = fields.Char(
        string='API Password',
        config_parameter='kwtsms.api_password',
    )
    kwtsms_sender_id = fields.Selection(
        selection='_get_sender_id_selection',
        string='Sender ID',
    )

    # Integration toggles (manually persisted to avoid Odoo deleting param on False)
    kwtsms_auto_order_confirm = fields.Boolean(
        string='SMS on Order Confirmation',
        default=True,
    )
    kwtsms_auto_delivery_done = fields.Boolean(
        string='SMS on Delivery Completion',
        default=False,
    )

    # Template selections (stored manually, Many2one can't use config_parameter)
    kwtsms_order_template_id = fields.Many2one(
        'kwtsms.sms.template',
        string='Order Confirmation Template',
    )
    kwtsms_delivery_template_id = fields.Many2one(
        'kwtsms.sms.template',
        string='Delivery Notification Template',
    )

    # Gateway status (computed, read-only)
    kwtsms_balance_available = fields.Integer(
        string='Available Balance',
        compute='_compute_gateway_info',
    )
    kwtsms_balance_purchased = fields.Integer(
        string='Purchased Balance',
        compute='_compute_gateway_info',
    )
    kwtsms_api_status = fields.Selection([
        ('not_configured', 'Not Configured'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], string='API Status', compute='_compute_gateway_info')
    kwtsms_last_verified = fields.Datetime(
        string='Last Verified',
        compute='_compute_gateway_info',
    )
    kwtsms_api_error = fields.Char(
        string='API Error',
        compute='_compute_gateway_info',
    )

    @api.model
    def _get_sender_id_selection(self):
        """Build sender ID selection from gateway config."""
        result = [('KWT-SMS', 'KWT-SMS')]
        try:
            config = self.env['kwtsms.gateway.config'].sudo()._get_or_create()
            sender_list = config.get_sender_id_list()
            seen = {'KWT-SMS'}
            for sid in sender_list:
                if sid and sid not in seen:
                    result.append((sid, sid))
                    seen.add(sid)
        except Exception as e:
            _logger.warning('kwtSMS: Could not load sender IDs: %s', e)
        # Include the currently saved value so it doesn't get lost
        ICP = self.env['ir.config_parameter'].sudo()
        current = ICP.get_param('kwtsms.sender_id', '')
        if current and current not in {r[0] for r in result}:
            result.append((current, current))
        return result

    def _compute_gateway_info(self):
        for record in self:
            config = self.env['kwtsms.gateway.config'].sudo()._get_or_create()
            record.kwtsms_balance_available = config.balance_available
            record.kwtsms_balance_purchased = config.balance_purchased
            record.kwtsms_api_status = config.api_status
            record.kwtsms_last_verified = config.last_verified
            record.kwtsms_api_error = config.api_error

    @api.model
    def get_values(self):
        """Load manually-persisted fields from system parameters."""
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()

        # Boolean fields (stored as 'True'/'False' strings to avoid deletion)
        res['kwtsms_enabled'] = ICP.get_param('kwtsms.enabled', 'True') == 'True'
        res['kwtsms_test_mode'] = ICP.get_param('kwtsms.test_mode', 'True') == 'True'
        res['kwtsms_auto_order_confirm'] = ICP.get_param('kwtsms.auto_order_confirm', 'True') == 'True'
        res['kwtsms_auto_delivery_done'] = ICP.get_param('kwtsms.auto_delivery_done', 'False') == 'True'

        # Sender ID
        sender_id = ICP.get_param('kwtsms.sender_id', 'KWT-SMS')
        res['kwtsms_sender_id'] = sender_id or 'KWT-SMS'

        # Templates
        try:
            order_tmpl_id = int(ICP.get_param('kwtsms.order_template_id', '0'))
        except (ValueError, TypeError):
            order_tmpl_id = 0
        try:
            delivery_tmpl_id = int(ICP.get_param('kwtsms.delivery_template_id', '0'))
        except (ValueError, TypeError):
            delivery_tmpl_id = 0

        if order_tmpl_id and self.env['kwtsms.sms.template'].browse(order_tmpl_id).exists():
            res['kwtsms_order_template_id'] = order_tmpl_id
        if delivery_tmpl_id and self.env['kwtsms.sms.template'].browse(delivery_tmpl_id).exists():
            res['kwtsms_delivery_template_id'] = delivery_tmpl_id

        return res

    def set_values(self):
        """Save manually-persisted fields to system parameters."""
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()

        # Boolean fields (explicitly store as string to prevent deletion)
        ICP.set_param('kwtsms.enabled', 'True' if self.kwtsms_enabled else 'False')
        ICP.set_param('kwtsms.test_mode', 'True' if self.kwtsms_test_mode else 'False')
        ICP.set_param('kwtsms.auto_order_confirm', 'True' if self.kwtsms_auto_order_confirm else 'False')
        ICP.set_param('kwtsms.auto_delivery_done', 'True' if self.kwtsms_auto_delivery_done else 'False')

        # Sender ID
        ICP.set_param('kwtsms.sender_id', self.kwtsms_sender_id or 'KWT-SMS')

        # Templates
        ICP.set_param(
            'kwtsms.order_template_id',
            str(self.kwtsms_order_template_id.id) if self.kwtsms_order_template_id else '0',
        )
        ICP.set_param(
            'kwtsms.delivery_template_id',
            str(self.kwtsms_delivery_template_id.id) if self.kwtsms_delivery_template_id else '0',
        )

    def action_kwtsms_login(self):
        """Delegate to gateway config login verification."""
        config = self.env['kwtsms.gateway.config'].sudo()._get_or_create()
        return config.action_login_verify()

    def action_kwtsms_refresh_balance(self):
        """Quick balance refresh only."""
        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        try:
            api = KwtSmsApi(self.env)
            resp = api.check_balance()
        except Exception as e:
            _logger.error('kwtSMS: Balance refresh failed: %s', e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Refresh Failed'),
                    'message': _('Could not connect to kwtSMS API.'),
                    'type': 'danger',
                    'sticky': False,
                },
            }

        config = self.env['kwtsms.gateway.config'].sudo()._get_or_create()
        if resp.get('result') == 'OK':
            config.write({
                'balance_available': resp.get('available', 0),
                'balance_purchased': resp.get('purchased', 0),
                'last_verified': fields.Datetime.now(),
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Balance Updated'),
                    'message': _('Available: %s') % resp.get('available', 0),
                    'type': 'success',
                    'sticky': False,
                },
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Refresh Failed'),
                'message': resp.get('description', _('Unknown error')),
                'type': 'danger',
                'sticky': False,
            },
        }
