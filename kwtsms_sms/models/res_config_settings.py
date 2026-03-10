"""kwtSMS settings page integrated into Odoo Settings."""

import logging
from datetime import timedelta

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
    kwtsms_default_country_code = fields.Selection(
        selection='_get_country_code_selection',
        string='Default Country Code',
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
    kwtsms_auto_order_cancel = fields.Boolean(
        string='SMS on Order Cancellation',
        default=False,
    )
    kwtsms_auto_invoice_posted = fields.Boolean(
        string='SMS on Invoice Posted',
        default=False,
    )
    kwtsms_auto_payment_received = fields.Boolean(
        string='SMS on Payment Received',
        default=False,
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
        string='Last Updated',
        compute='_compute_gateway_info',
    )
    kwtsms_api_error = fields.Char(
        string='API Error',
        compute='_compute_gateway_info',
    )
    kwtsms_current_sender = fields.Char(
        string='Current Sender ID',
        compute='_compute_gateway_info',
    )

    # Dashboard analytics (computed)
    kwtsms_sms_today = fields.Integer(
        string='Sent Today',
        compute='_compute_dashboard_stats',
    )
    kwtsms_sms_this_week = fields.Integer(
        string='Sent This Week',
        compute='_compute_dashboard_stats',
    )
    kwtsms_sms_this_month = fields.Integer(
        string='Sent This Month',
        compute='_compute_dashboard_stats',
    )
    kwtsms_sms_failed = fields.Integer(
        string='Failed (30 days)',
        compute='_compute_dashboard_stats',
    )

    @api.model
    def _get_country_code_selection(self):
        """Build country code selection from gateway coverage data."""
        result = [('965', '965 (Kuwait)')]
        try:
            config = self.env['kwtsms.gateway.config'].sudo()._get_or_create()
            prefixes = config.get_coverage_prefixes()
            seen = {'965'}
            for prefix in prefixes:
                prefix = str(prefix)
                if prefix and prefix not in seen:
                    result.append((prefix, prefix))
                    seen.add(prefix)
        except Exception as e:
            _logger.warning('kwtSMS: Could not load coverage prefixes: %s', e)
        # Include the currently saved value so it doesn't get lost
        ICP = self.env['ir.config_parameter'].sudo()
        current = ICP.get_param('kwtsms.default_country_code', '965')
        if current and current not in {r[0] for r in result}:
            result.append((current, current))
        return result

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
            ICP = self.env['ir.config_parameter'].sudo()
            record.kwtsms_current_sender = ICP.get_param('kwtsms.sender_id', 'KWT-SMS')

    def _compute_dashboard_stats(self):
        """Compute SMS analytics from the log model."""
        SmsLog = self.env['kwtsms.sms.log'].sudo()
        now = fields.Datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)
        thirty_days_ago = now - timedelta(days=30)

        for record in self:
            record.kwtsms_sms_today = SmsLog.search_count([
                ('create_date', '>=', today_start),
                ('status', 'in', ['success', 'test']),
            ])
            record.kwtsms_sms_this_week = SmsLog.search_count([
                ('create_date', '>=', week_start),
                ('status', 'in', ['success', 'test']),
            ])
            record.kwtsms_sms_this_month = SmsLog.search_count([
                ('create_date', '>=', month_start),
                ('status', 'in', ['success', 'test']),
            ])
            record.kwtsms_sms_failed = SmsLog.search_count([
                ('create_date', '>=', thirty_days_ago),
                ('status', '=', 'error'),
            ])

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
        res['kwtsms_auto_order_cancel'] = ICP.get_param('kwtsms.auto_order_cancel', 'False') == 'True'
        res['kwtsms_auto_invoice_posted'] = ICP.get_param('kwtsms.auto_invoice_posted', 'False') == 'True'
        res['kwtsms_auto_payment_received'] = ICP.get_param('kwtsms.auto_payment_received', 'False') == 'True'

        # Sender ID
        sender_id = ICP.get_param('kwtsms.sender_id', 'KWT-SMS')
        res['kwtsms_sender_id'] = sender_id or 'KWT-SMS'

        # Country code
        country_code = ICP.get_param('kwtsms.default_country_code', '965')
        res['kwtsms_default_country_code'] = country_code or '965'

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
        ICP.set_param('kwtsms.auto_order_cancel', 'True' if self.kwtsms_auto_order_cancel else 'False')
        ICP.set_param('kwtsms.auto_invoice_posted', 'True' if self.kwtsms_auto_invoice_posted else 'False')
        ICP.set_param('kwtsms.auto_payment_received', 'True' if self.kwtsms_auto_payment_received else 'False')

        # Sender ID
        ICP.set_param('kwtsms.sender_id', self.kwtsms_sender_id or 'KWT-SMS')

        # Country code
        ICP.set_param('kwtsms.default_country_code', self.kwtsms_default_country_code or '965')

    def action_kwtsms_login(self):
        """Save credentials immediately, then verify and auto-select sender ID."""
        ICP = self.env['ir.config_parameter'].sudo()
        # Save credentials before verifying so the API client picks them up
        ICP.set_param('kwtsms.api_username', self.kwtsms_api_username or '')
        ICP.set_param('kwtsms.api_password', self.kwtsms_api_password or '')

        config = self.env['kwtsms.gateway.config'].sudo()._get_or_create()
        result = config.action_login_verify()

        # On success, auto-select first sender ID if not already set
        if config.api_status == 'connected':
            sender_list = config.get_sender_id_list()
            current = ICP.get_param('kwtsms.sender_id', '')
            if sender_list and (not current or current == 'KWT-SMS'):
                ICP.set_param('kwtsms.sender_id', sender_list[0])

        return result

    def action_kwtsms_refresh(self):
        """Refresh all gateway data: balance, sender IDs, coverage."""
        import json
        ICP = self.env['ir.config_parameter'].sudo()
        username = ICP.get_param('kwtsms.api_username', '')
        password = ICP.get_param('kwtsms.api_password', '')
        if not username or not password:
            config = self.env['kwtsms.gateway.config'].sudo()._get_or_create()
            config.write({
                'api_status': 'not_configured',
                'api_error': _('Please enter API credentials and login first.'),
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        try:
            api = KwtSmsApi(self.env)
            resp = api.check_balance()
        except Exception as e:
            _logger.error('kwtSMS: Refresh failed: %s', e)
            config = self.env['kwtsms.gateway.config'].sudo()._get_or_create()
            config.write({
                'api_status': 'error',
                'api_error': _('Could not connect to kwtSMS API.'),
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

        config = self.env['kwtsms.gateway.config'].sudo()._get_or_create()
        if resp.get('result') != 'OK':
            error_msg = resp.get('description', _('Unknown error'))
            config.write({
                'api_status': 'error',
                'api_error': error_msg,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

        vals = {
            'balance_available': resp.get('available', 0),
            'balance_purchased': resp.get('purchased', 0),
            'last_verified': fields.Datetime.now(),
        }

        # Refresh sender IDs
        try:
            sender_resp = api.fetch_sender_ids()
            if sender_resp.get('result') == 'OK':
                sender_list = sender_resp.get('senderid', [])
                vals['sender_ids_json'] = json.dumps(sender_list, ensure_ascii=False)
        except Exception as e:
            _logger.warning('kwtSMS: Sender ID refresh failed: %s', e)

        # Refresh coverage
        try:
            coverage_resp = api.fetch_coverage()
            if coverage_resp.get('result') == 'OK':
                prefixes = coverage_resp.get('prefixes', [])
                vals['coverage_json'] = json.dumps(prefixes, ensure_ascii=False)
        except Exception as e:
            _logger.warning('kwtSMS: Coverage refresh failed: %s', e)

        config.write(vals)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.model
    def action_kwtsms_send_test_rpc(self, phone, message):
        """RPC endpoint for OWL widget test SMS. Bypasses form save cycle."""
        if not phone:
            return {'success': False, 'message': 'Please enter a phone number.'}
        if not message:
            return {'success': False, 'message': 'Please enter a message.'}

        ICP = self.env['ir.config_parameter'].sudo()
        username = ICP.get_param('kwtsms.api_username', '')
        password = ICP.get_param('kwtsms.api_password', '')
        if not username or not password:
            return {'success': False, 'message': 'Please enter API credentials and login first.'}

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        api_client = KwtSmsApi(self.env)

        response = api_client.send_single(phone, message)

        if response.get('result') == 'OK':
            log_status = 'test' if api_client._test_mode else 'success'
            api_client._log_send(
                numbers=phone,
                message=message,
                response=response,
                status=log_status,
            )
            if api_client._test_mode:
                msg = 'Test SMS sent to %s (test mode, not delivered).' % phone
            else:
                msg = 'SMS sent to %s successfully.' % phone
            return {
                'success': True,
                'message': msg,
            }
        else:
            error_msg = response.get('description', 'Unknown error')
            api_client._log_send(
                numbers=phone,
                message=message,
                response=response,
                status='error',
                error_code=response.get('code'),
                error_description=error_msg,
            )
            return {'success': False, 'message': 'Test SMS failed: %s' % error_msg}

    def action_kwtsms_logout(self):
        """Log out: clear credentials and reset gateway state."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.api_username', '')
        ICP.set_param('kwtsms.api_password', '')
        ICP.set_param('kwtsms.sender_id', 'KWT-SMS')

        config = self.env['kwtsms.gateway.config'].sudo()._get_or_create()
        config.write({
            'api_status': 'not_configured',
            'api_error': False,
            'balance_available': 0,
            'balance_purchased': 0,
            'last_verified': False,
            'sender_ids_json': '[]',
            'coverage_json': '[]',
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
