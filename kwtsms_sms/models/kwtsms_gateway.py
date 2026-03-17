"""kwtSMS Gateway Configuration model."""

import json
import logging
from datetime import timedelta

import pytz

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class KwtSmsGatewayConfig(models.Model):
    """Stores gateway state and proxies settings from ir.config_parameter."""

    _name = 'kwtsms.gateway.config'
    _description = 'kwtSMS Gateway Configuration'

    name = fields.Char(
        string='Name',
        default='kwtSMS',
    )

    @api.depends_context('kwtsms_page_title')
    def _compute_display_name(self):
        """Show page-specific title in breadcrumb."""
        title = self.env.context.get('kwtsms_page_title')
        for record in self:
            record.display_name = title or record.name

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    sender_ids_json = fields.Text(
        string='Sender IDs (JSON)',
        default='[]',
    )
    coverage_json = fields.Text(
        string='Coverage Data (JSON)',
        default='[]',
    )
    balance_available = fields.Integer(
        string='Available Balance',
        default=0,
    )
    balance_purchased = fields.Integer(
        string='Purchased Balance',
        default=0,
    )
    last_verified = fields.Datetime(
        string='Last Updated',
    )
    api_status = fields.Selection([
        ('not_configured', 'Not Configured'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], string='API Status', default='not_configured')
    api_error = fields.Char(
        string='API Error',
    )

    # ═══════════════════════════════════════
    # Configuration proxy fields (read/write ir.config_parameter)
    # ═══════════════════════════════════════

    cfg_enabled = fields.Boolean(
        string='Enable kwtSMS Gateway',
        compute='_compute_cfg_general',
        inverse='_inverse_cfg_enabled',
    )
    cfg_test_mode = fields.Boolean(
        string='Test Mode',
        compute='_compute_cfg_general',
        inverse='_inverse_cfg_test_mode',
        help='When enabled, SMS messages are queued but not delivered.',
    )
    cfg_api_username = fields.Char(
        string='API Username',
        compute='_compute_cfg_credentials',
        inverse='_inverse_cfg_api_username',
        groups='base.group_system',
    )
    cfg_api_password = fields.Char(
        string='API Password',
        compute='_compute_cfg_credentials',
        inverse='_inverse_cfg_api_password',
        groups='base.group_system',
    )
    cfg_sender_id = fields.Selection(
        selection='_get_sender_id_selection',
        string='Sender ID',
        compute='_compute_cfg_credentials',
        inverse='_inverse_cfg_sender_id',
    )
    cfg_default_country_code = fields.Selection(
        selection='_get_country_code_selection',
        string='Default Country Code',
        compute='_compute_cfg_general',
        inverse='_inverse_cfg_default_country_code',
    )
    cfg_log_retention_days = fields.Integer(
        string='Log Retention (Days)',
        compute='_compute_cfg_general',
        inverse='_inverse_cfg_log_retention_days',
    )

    # Integration toggles
    cfg_auto_order_confirm = fields.Boolean(
        string='SMS on Order Confirmation',
        compute='_compute_cfg_toggles',
        inverse='_inverse_cfg_auto_order_confirm',
    )
    cfg_auto_delivery_done = fields.Boolean(
        string='SMS on Delivery Completion',
        compute='_compute_cfg_toggles',
        inverse='_inverse_cfg_auto_delivery_done',
    )
    cfg_auto_order_cancel = fields.Boolean(
        string='SMS on Order Cancellation',
        compute='_compute_cfg_toggles',
        inverse='_inverse_cfg_auto_order_cancel',
    )
    cfg_auto_invoice_posted = fields.Boolean(
        string='SMS on Invoice Posted',
        compute='_compute_cfg_toggles',
        inverse='_inverse_cfg_auto_invoice_posted',
    )
    cfg_auto_payment_received = fields.Boolean(
        string='SMS on Payment Received',
        compute='_compute_cfg_toggles',
        inverse='_inverse_cfg_auto_payment_received',
    )

    # Admin notification phone fields
    cfg_admin_phone = fields.Char(
        string='Admin Phone (General)',
        compute='_compute_cfg_admin_phones',
        inverse='_inverse_cfg_admin_phone',
    )
    cfg_admin_phone_sales = fields.Char(
        string='Admin Phone (Sales)',
        compute='_compute_cfg_admin_phones',
        inverse='_inverse_cfg_admin_phone_sales',
    )
    cfg_admin_phone_inventory = fields.Char(
        string='Admin Phone (Inventory)',
        compute='_compute_cfg_admin_phones',
        inverse='_inverse_cfg_admin_phone_inventory',
    )
    cfg_admin_phone_accounting = fields.Char(
        string='Admin Phone (Accounting)',
        compute='_compute_cfg_admin_phones',
        inverse='_inverse_cfg_admin_phone_accounting',
    )
    cfg_admin_phone_crm = fields.Char(
        string='Admin Phone (CRM)',
        compute='_compute_cfg_admin_phones',
        inverse='_inverse_cfg_admin_phone_crm',
    )

    # Admin notification toggles
    cfg_auto_admin_new_quotation = fields.Boolean(
        string='SMS on New Quotation',
        compute='_compute_cfg_admin_toggles',
        inverse='_inverse_cfg_auto_admin_new_quotation',
    )
    cfg_auto_admin_order_cancelled = fields.Boolean(
        string='SMS on Order Cancelled',
        compute='_compute_cfg_admin_toggles',
        inverse='_inverse_cfg_auto_admin_order_cancelled',
    )
    cfg_auto_admin_large_order = fields.Boolean(
        string='SMS on Large Order',
        compute='_compute_cfg_admin_toggles',
        inverse='_inverse_cfg_auto_admin_large_order',
    )
    cfg_auto_admin_low_stock = fields.Boolean(
        string='SMS on Low Stock',
        compute='_compute_cfg_admin_toggles',
        inverse='_inverse_cfg_auto_admin_low_stock',
    )
    cfg_auto_admin_incoming_shipment = fields.Boolean(
        string='SMS on Incoming Shipment',
        compute='_compute_cfg_admin_toggles',
        inverse='_inverse_cfg_auto_admin_incoming_shipment',
    )
    cfg_auto_admin_payment_received = fields.Boolean(
        string='SMS on Payment Received (Admin)',
        compute='_compute_cfg_admin_toggles',
        inverse='_inverse_cfg_auto_admin_payment_received',
    )
    cfg_auto_admin_invoice_overdue = fields.Boolean(
        string='SMS on Invoice Overdue',
        compute='_compute_cfg_admin_toggles',
        inverse='_inverse_cfg_auto_admin_invoice_overdue',
    )
    cfg_auto_admin_new_lead = fields.Boolean(
        string='SMS on New Lead',
        compute='_compute_cfg_admin_toggles',
        inverse='_inverse_cfg_auto_admin_new_lead',
    )
    cfg_auto_admin_lead_stage_changed = fields.Boolean(
        string='SMS on Lead Stage Changed',
        compute='_compute_cfg_admin_toggles',
        inverse='_inverse_cfg_auto_admin_lead_stage_changed',
    )

    # Admin notification threshold fields
    cfg_large_order_threshold = fields.Float(
        string='Large Order Threshold',
        compute='_compute_cfg_admin_thresholds',
        inverse='_inverse_cfg_large_order_threshold',
    )
    cfg_overdue_invoice_days = fields.Integer(
        string='Overdue Invoice Days',
        compute='_compute_cfg_admin_thresholds',
        inverse='_inverse_cfg_overdue_invoice_days',
    )

    # CRM module availability
    has_crm_module = fields.Boolean(
        string='CRM Module Installed',
        compute='_compute_has_crm_module',
    )

    # ═══════════════════════════════════════
    # Compute methods for config proxy fields
    # ═══════════════════════════════════════

    def _compute_cfg_general(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            record.cfg_enabled = ICP.get_param('kwtsms.enabled', 'True') == 'True'
            record.cfg_test_mode = ICP.get_param('kwtsms.test_mode', 'True') == 'True'
            record.cfg_default_country_code = ICP.get_param('kwtsms.default_country_code', '965') or '965'
            record.cfg_log_retention_days = int(ICP.get_param('kwtsms.log_retention_days', '90'))

    def _compute_cfg_credentials(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            record.cfg_api_username = ICP.get_param('kwtsms.api_username', '')
            record.cfg_api_password = ICP.get_param('kwtsms.api_password', '')
            record.cfg_sender_id = ICP.get_param('kwtsms.sender_id', 'KWT-SMS') or 'KWT-SMS'

    def _compute_cfg_toggles(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            record.cfg_auto_order_confirm = ICP.get_param('kwtsms.auto_order_confirm', 'True') == 'True'
            record.cfg_auto_delivery_done = ICP.get_param('kwtsms.auto_delivery_done', 'False') == 'True'
            record.cfg_auto_order_cancel = ICP.get_param('kwtsms.auto_order_cancel', 'False') == 'True'
            record.cfg_auto_invoice_posted = ICP.get_param('kwtsms.auto_invoice_posted', 'False') == 'True'
            record.cfg_auto_payment_received = ICP.get_param('kwtsms.auto_payment_received', 'False') == 'True'

    def _compute_cfg_admin_phones(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            record.cfg_admin_phone = ICP.get_param('kwtsms.admin_phone', '')
            record.cfg_admin_phone_sales = ICP.get_param('kwtsms.admin_phone_sales', '')
            record.cfg_admin_phone_inventory = ICP.get_param('kwtsms.admin_phone_inventory', '')
            record.cfg_admin_phone_accounting = ICP.get_param('kwtsms.admin_phone_accounting', '')
            record.cfg_admin_phone_crm = ICP.get_param('kwtsms.admin_phone_crm', '')

    def _compute_cfg_admin_toggles(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            record.cfg_auto_admin_new_quotation = ICP.get_param('kwtsms.auto_admin_new_quotation', 'False') == 'True'
            record.cfg_auto_admin_order_cancelled = ICP.get_param('kwtsms.auto_admin_order_cancelled', 'False') == 'True'
            record.cfg_auto_admin_large_order = ICP.get_param('kwtsms.auto_admin_large_order', 'False') == 'True'
            record.cfg_auto_admin_low_stock = ICP.get_param('kwtsms.auto_admin_low_stock', 'False') == 'True'
            record.cfg_auto_admin_incoming_shipment = ICP.get_param('kwtsms.auto_admin_incoming_shipment', 'False') == 'True'
            record.cfg_auto_admin_payment_received = ICP.get_param('kwtsms.auto_admin_payment_received', 'False') == 'True'
            record.cfg_auto_admin_invoice_overdue = ICP.get_param('kwtsms.auto_admin_invoice_overdue', 'False') == 'True'
            record.cfg_auto_admin_new_lead = ICP.get_param('kwtsms.auto_admin_new_lead', 'False') == 'True'
            record.cfg_auto_admin_lead_stage_changed = ICP.get_param('kwtsms.auto_admin_lead_stage_changed', 'False') == 'True'

    def _compute_cfg_admin_thresholds(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            record.cfg_large_order_threshold = float(ICP.get_param('kwtsms.large_order_threshold', '1000'))
            record.cfg_overdue_invoice_days = int(ICP.get_param('kwtsms.overdue_invoice_days', '30'))

    def _compute_has_crm_module(self):
        installed = bool(self.env['ir.module.module'].sudo().search([
            ('name', '=', 'crm'), ('state', '=', 'installed'),
        ], limit=1))
        for record in self:
            record.has_crm_module = installed

    # ═══════════════════════════════════════
    # Inverse methods (write back to ir.config_parameter)
    # ═══════════════════════════════════════

    def _inverse_cfg_enabled(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.enabled', 'True' if record.cfg_enabled else 'False')

    def _inverse_cfg_test_mode(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.test_mode', 'True' if record.cfg_test_mode else 'False')

    def _inverse_cfg_api_username(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.api_username', record.cfg_api_username or '')

    def _inverse_cfg_api_password(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.api_password', record.cfg_api_password or '')

    def _inverse_cfg_sender_id(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.sender_id', record.cfg_sender_id or 'KWT-SMS')

    def _inverse_cfg_default_country_code(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.default_country_code', record.cfg_default_country_code or '965')

    def _inverse_cfg_log_retention_days(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.log_retention_days', str(record.cfg_log_retention_days or 90))

    def _inverse_cfg_auto_order_confirm(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.auto_order_confirm', 'True' if record.cfg_auto_order_confirm else 'False')

    def _inverse_cfg_auto_delivery_done(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.auto_delivery_done', 'True' if record.cfg_auto_delivery_done else 'False')

    def _inverse_cfg_auto_order_cancel(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.auto_order_cancel', 'True' if record.cfg_auto_order_cancel else 'False')

    def _inverse_cfg_auto_invoice_posted(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.auto_invoice_posted', 'True' if record.cfg_auto_invoice_posted else 'False')

    def _inverse_cfg_auto_payment_received(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.auto_payment_received', 'True' if record.cfg_auto_payment_received else 'False')

    def _inverse_cfg_admin_phone(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.admin_phone', record.cfg_admin_phone or '')

    def _inverse_cfg_admin_phone_sales(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.admin_phone_sales', record.cfg_admin_phone_sales or '')

    def _inverse_cfg_admin_phone_inventory(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.admin_phone_inventory', record.cfg_admin_phone_inventory or '')

    def _inverse_cfg_admin_phone_accounting(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.admin_phone_accounting', record.cfg_admin_phone_accounting or '')

    def _inverse_cfg_admin_phone_crm(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.admin_phone_crm', record.cfg_admin_phone_crm or '')

    def _inverse_cfg_auto_admin_new_quotation(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.auto_admin_new_quotation', 'True' if record.cfg_auto_admin_new_quotation else 'False')

    def _inverse_cfg_auto_admin_order_cancelled(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.auto_admin_order_cancelled', 'True' if record.cfg_auto_admin_order_cancelled else 'False')

    def _inverse_cfg_auto_admin_large_order(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.auto_admin_large_order', 'True' if record.cfg_auto_admin_large_order else 'False')

    def _inverse_cfg_auto_admin_low_stock(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.auto_admin_low_stock', 'True' if record.cfg_auto_admin_low_stock else 'False')

    def _inverse_cfg_auto_admin_incoming_shipment(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.auto_admin_incoming_shipment', 'True' if record.cfg_auto_admin_incoming_shipment else 'False')

    def _inverse_cfg_auto_admin_payment_received(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.auto_admin_payment_received', 'True' if record.cfg_auto_admin_payment_received else 'False')

    def _inverse_cfg_auto_admin_invoice_overdue(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.auto_admin_invoice_overdue', 'True' if record.cfg_auto_admin_invoice_overdue else 'False')

    def _inverse_cfg_auto_admin_new_lead(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.auto_admin_new_lead', 'True' if record.cfg_auto_admin_new_lead else 'False')

    def _inverse_cfg_auto_admin_lead_stage_changed(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.auto_admin_lead_stage_changed', 'True' if record.cfg_auto_admin_lead_stage_changed else 'False')

    def _inverse_cfg_large_order_threshold(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.large_order_threshold', str(record.cfg_large_order_threshold or 1000))

    def _inverse_cfg_overdue_invoice_days(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('kwtsms.overdue_invoice_days', str(record.cfg_overdue_invoice_days or 30))

    # ═══════════════════════════════════════
    # Selection builders
    # ═══════════════════════════════════════

    @api.model
    def _get_country_code_selection(self):
        """Build country code selection from gateway coverage data."""
        result = [('965', '965 (Kuwait)')]
        try:
            config = self.sudo()._get_or_create()
            prefixes = config.get_coverage_prefixes()
            seen = {'965'}
            for prefix in prefixes:
                prefix = str(prefix)
                if prefix and prefix not in seen:
                    result.append((prefix, prefix))
                    seen.add(prefix)
        except Exception as e:
            _logger.warning('kwtSMS: Could not load coverage prefixes: %s', e)
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
            config = self.sudo()._get_or_create()
            sender_list = config.get_sender_id_list()
            seen = {'KWT-SMS'}
            for sid in sender_list:
                if sid and sid not in seen:
                    result.append((sid, sid))
                    seen.add(sid)
        except Exception as e:
            _logger.warning('kwtSMS: Could not load sender IDs: %s', e)
        ICP = self.env['ir.config_parameter'].sudo()
        current = ICP.get_param('kwtsms.sender_id', '')
        if current and current not in {r[0] for r in result}:
            result.append((current, current))
        return result

    # ═══════════════════════════════════════
    # Singleton & helpers
    # ═══════════════════════════════════════

    @api.model
    def _get_or_create(self):
        """Get or create singleton config for the current company.

        Returns:
            recordset: Gateway config record for current company.
        """
        config = self.search([
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not config:
            config = self.create({
                'company_id': self.env.company.id,
            })
        elif not config.name:
            config.name = 'kwtSMS Dashboard'
        return config

    def get_sender_id_list(self):
        """Parse sender_ids_json and return as list.

        Returns:
            list: List of sender ID strings.
        """
        self.ensure_one()
        try:
            return json.loads(self.sender_ids_json or '[]')
        except (json.JSONDecodeError, TypeError):
            return []

    def get_coverage_prefixes(self):
        """Parse coverage_json and return as list of country code prefixes.

        Returns:
            list: List of country code strings (e.g. ['965']).
        """
        self.ensure_one()
        try:
            return json.loads(self.coverage_json or '[]')
        except (json.JSONDecodeError, TypeError):
            return []

    def get_balance(self):
        """Return available balance.

        Returns:
            int: Available SMS credits.
        """
        self.ensure_one()
        return self.balance_available

    # ═══════════════════════════════════════
    # Dashboard computed fields
    # ═══════════════════════════════════════

    current_sender = fields.Char(
        string='Sender ID',
        compute='_compute_dashboard_fields',
    )
    sms_today = fields.Integer(
        string='Sent Today',
        compute='_compute_dashboard_fields',
    )
    sms_this_week = fields.Integer(
        string='This Week',
        compute='_compute_dashboard_fields',
    )
    sms_this_month = fields.Integer(
        string='This Month',
        compute='_compute_dashboard_fields',
    )
    sms_failed_30d = fields.Integer(
        string='Failed (30d)',
        compute='_compute_dashboard_fields',
    )

    def _compute_dashboard_fields(self):
        """Compute SMS analytics for the dashboard.

        Uses the user's timezone (or UTC) for day/week/month boundaries
        so "today" means the user's local today, not UTC midnight.
        """
        SmsLog = self.env['kwtsms.sms.log'].sudo()
        ICP = self.env['ir.config_parameter'].sudo()
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        now_utc = fields.Datetime.now().replace(tzinfo=pytz.utc)
        now_local = now_utc.astimezone(user_tz)
        today_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start = today_local.astimezone(pytz.utc).replace(tzinfo=None)
        week_start_local = today_local - timedelta(days=today_local.weekday())
        week_start = week_start_local.astimezone(pytz.utc).replace(tzinfo=None)
        month_start_local = today_local.replace(day=1)
        month_start = month_start_local.astimezone(pytz.utc).replace(tzinfo=None)
        thirty_days_ago = fields.Datetime.now() - timedelta(days=30)

        for record in self:
            company_domain = [('company_id', '=', record.company_id.id)]
            record.current_sender = ICP.get_param('kwtsms.sender_id', 'KWT-SMS')
            record.sms_today = SmsLog.search_count(company_domain + [
                ('create_date', '>=', today_start),
                ('status', 'in', ['success', 'test']),
            ])
            record.sms_this_week = SmsLog.search_count(company_domain + [
                ('create_date', '>=', week_start),
                ('status', 'in', ['success', 'test']),
            ])
            record.sms_this_month = SmsLog.search_count(company_domain + [
                ('create_date', '>=', month_start),
                ('status', 'in', ['success', 'test']),
            ])
            record.sms_failed_30d = SmsLog.search_count(company_domain + [
                ('create_date', '>=', thirty_days_ago),
                ('status', '=', 'error'),
            ])

    # ═══════════════════════════════════════
    # Actions: Login, Logout, Refresh, Test SMS
    # ═══════════════════════════════════════

    def action_login(self):
        """Save credentials, verify connection, auto-select first sender ID."""
        self.ensure_one()
        self.action_login_verify()

        # On success, auto-select first sender ID if not already set
        if self.api_status == 'connected':
            ICP = self.env['ir.config_parameter'].sudo()
            sender_list = self.get_sender_id_list()
            current = ICP.get_param('kwtsms.sender_id', '')
            if sender_list and (not current or current == 'KWT-SMS'):
                ICP.set_param('kwtsms.sender_id', sender_list[0])

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_login_verify(self):
        """Verify credentials and fetch account data from kwtSMS API.

        Returns:
            dict: Notification action with success or error message.
        """
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        username = ICP.get_param('kwtsms.api_username', '')
        password = ICP.get_param('kwtsms.api_password', '')
        if not username or not password:
            self.write({
                'api_status': 'not_configured',
                'api_error': _('Please enter your API username and password first.'),
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi

        api = KwtSmsApi(self.env)

        # Check balance (verifies credentials)
        balance_resp = api.check_balance()
        if balance_resp.get('result') != 'OK':
            error_msg = balance_resp.get('description', _('Unknown error'))
            self.write({
                'api_status': 'error',
                'api_error': error_msg,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

        # Save balance
        vals = {
            'balance_available': balance_resp.get('available', 0),
            'balance_purchased': balance_resp.get('purchased', 0),
            'api_status': 'connected',
            'api_error': False,
            'last_verified': fields.Datetime.now(),
        }

        # Fetch sender IDs
        sender_resp = api.fetch_sender_ids()
        if sender_resp.get('result') == 'OK':
            sender_list = sender_resp.get('senderid', [])
            vals['sender_ids_json'] = json.dumps(sender_list, ensure_ascii=False)

        # Fetch coverage
        coverage_resp = api.fetch_coverage()
        if coverage_resp.get('result') == 'OK':
            prefixes = coverage_resp.get('prefixes', [])
            vals['coverage_json'] = json.dumps(prefixes, ensure_ascii=False)

        self.write(vals)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_logout(self):
        """Log out: clear credentials and reset gateway state."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.api_username', '')
        ICP.set_param('kwtsms.api_password', '')
        ICP.set_param('kwtsms.sender_id', 'KWT-SMS')

        self.ensure_one()
        self.write({
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

    def action_refresh_dashboard(self):
        """Refresh dashboard data by re-verifying credentials and fetching latest data."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        username = ICP.get_param('kwtsms.api_username', '')
        password = ICP.get_param('kwtsms.api_password', '')
        if not username or not password:
            self.write({
                'api_status': 'not_configured',
                'api_error': _('API credentials not configured.'),
            })
            return

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi

        api = KwtSmsApi(self.env)
        balance_resp = api.check_balance()
        if balance_resp.get('result') != 'OK':
            error_msg = balance_resp.get('description', _('Unknown error'))
            self.write({
                'api_status': 'error',
                'api_error': error_msg,
            })
            return

        vals = {
            'balance_available': balance_resp.get('available', 0),
            'balance_purchased': balance_resp.get('purchased', 0),
            'api_status': 'connected',
            'api_error': False,
            'last_verified': fields.Datetime.now(),
        }

        sender_resp = api.fetch_sender_ids()
        if sender_resp.get('result') == 'OK':
            sender_list = sender_resp.get('senderid', [])
            vals['sender_ids_json'] = json.dumps(sender_list, ensure_ascii=False)

        coverage_resp = api.fetch_coverage()
        if coverage_resp.get('result') == 'OK':
            prefixes = coverage_resp.get('prefixes', [])
            vals['coverage_json'] = json.dumps(prefixes, ensure_ascii=False)

        self.write(vals)

    @api.model
    def action_kwtsms_send_test_rpc(self, phone, message):
        """RPC endpoint for OWL widget test SMS. Bypasses form save cycle."""
        if not self.env.user.has_group('base.group_system'):
            return {'success': False, 'message': _('Only administrators can send test SMS.')}

        if not phone:
            return {'success': False, 'message': _('Please enter a phone number.')}
        if not message:
            return {'success': False, 'message': _('Please enter a message.')}

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        api_client = KwtSmsApi(self.env)

        response = api_client.send(phone, message, recipient_type='admin')

        if response.get('result') == 'OK':
            if api_client._test_mode:
                msg = _('Test SMS sent to %s (test mode, not delivered).') % phone
            else:
                msg = _('SMS sent to %s successfully.') % phone
            return {'success': True, 'message': msg}
        else:
            error_msg = response.get('description', _('Unknown error'))
            return {'success': False, 'message': _('Test SMS failed: %s') % error_msg}

    # ═══════════════════════════════════════
    # Navigation actions (open specific views)
    # ═══════════════════════════════════════

    @api.model
    def _action_open_dashboard(self):
        """Open the dashboard form for the current company's gateway config."""
        config = self._get_or_create()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dashboard'),
            'res_model': 'kwtsms.gateway.config',
            'view_mode': 'form',
            'res_id': config.id,
            'target': 'current',
            'view_id': self.env.ref('kwtsms_sms.view_kwtsms_dashboard_form').id,
            'context': {
                'form_view_initial_mode': 'readonly',
                'kwtsms_page_title': _('Dashboard'),
            },
            'path': 'kwtsms',
        }

    @api.model
    def _action_open_settings(self):
        """Open the settings form."""
        config = self._get_or_create()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Settings'),
            'res_model': 'kwtsms.gateway.config',
            'view_mode': 'form',
            'res_id': config.id,
            'target': 'main',
            'view_id': self.env.ref('kwtsms_sms.view_kwtsms_settings_form').id,
            'context': {'kwtsms_page_title': _('Settings')},
            'path': 'kwtsms-settings',
        }

    @api.model
    def _action_open_gateway(self):
        """Open the gateway configuration form."""
        config = self._get_or_create()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Gateway'),
            'res_model': 'kwtsms.gateway.config',
            'view_mode': 'form',
            'res_id': config.id,
            'target': 'main',
            'view_id': self.env.ref('kwtsms_sms.view_kwtsms_gateway_form').id,
            'context': {'kwtsms_page_title': _('Gateway')},
            'path': 'kwtsms-gateway',
        }

    @api.model
    def _action_open_help(self):
        """Open the help page."""
        config = self._get_or_create()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Help'),
            'res_model': 'kwtsms.gateway.config',
            'view_mode': 'form',
            'res_id': config.id,
            'target': 'main',
            'view_id': self.env.ref('kwtsms_sms.view_kwtsms_help_form').id,
            'context': {
                'form_view_initial_mode': 'readonly',
                'kwtsms_page_title': _('Help'),
            },
            'path': 'kwtsms-help',
        }

    def action_goto_settings(self):
        """Navigate to Settings page via its server action."""
        action = self.env.ref('kwtsms_sms.action_kwtsms_settings')
        return {
            'type': 'ir.actions.act_url',
            'url': '/odoo/action-%d' % action.id,
            'target': 'self',
        }

    def action_goto_gateway(self):
        """Navigate to Gateway page via its server action."""
        action = self.env.ref('kwtsms_sms.action_kwtsms_gateway')
        return {
            'type': 'ir.actions.act_url',
            'url': '/odoo/action-%d' % action.id,
            'target': 'self',
        }

    def action_goto_templates(self):
        """Navigate to Templates list using stored path."""
        return {
            'type': 'ir.actions.act_url',
            'url': '/odoo/kwtsms-templates',
            'target': 'self',
        }

    def action_goto_logs(self):
        """Navigate to Logs list using stored path."""
        return {
            'type': 'ir.actions.act_url',
            'url': '/odoo/kwtsms-logs',
            'target': 'self',
        }

    def action_goto_help(self):
        """Navigate to Help page via its server action."""
        action = self.env.ref('kwtsms_sms.action_kwtsms_help')
        return {
            'type': 'ir.actions.act_url',
            'url': '/odoo/action-%d' % action.id,
            'target': 'self',
        }

    def action_open_buy_credits(self):
        """Open kwtSMS dashboard to buy credits."""
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://www.kwtsms.com/login',
            'target': 'new',
        }

    # ═══════════════════════════════════════
    # Cron
    # ═══════════════════════════════════════

    def _build_truncated_details(self, items, template_body, context_base):
        """Build a details string truncated to fit within 7 SMS pages.

        Args:
            items: List of detail line strings.
            template_body: Template body pattern for size estimation.
            context_base: Base context dict (without 'details' key).

        Returns:
            str: Truncated details string.
        """
        from odoo.addons.kwtsms_sms.tools.phone_utils import count_sms_parts

        details_lines = []
        remaining = len(items)

        for item in items:
            test_details = ', '.join(details_lines + [item])
            test_context = dict(context_base, details=test_details)
            test_msg = template_body
            for key, val in test_context.items():
                test_msg = test_msg.replace('{%s}' % key, str(val))
            _, pages, _ = count_sms_parts(test_msg)
            if pages > 7 and details_lines:
                left = remaining
                details_lines.append('... and %d more' % left)
                break
            details_lines.append(item)
            remaining -= 1

        return ', '.join(details_lines)

    def _cron_admin_low_stock_alert(self):
        """Daily cron: send admin SMS summary of products below reorder level."""
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('kwtsms.enabled', 'False') != 'True':
            return
        if ICP.get_param('kwtsms.auto_admin_low_stock', 'False') != 'True':
            return

        Orderpoint = self.env['stock.warehouse.orderpoint'].sudo()
        orderpoints = Orderpoint.search([])

        low_stock = []
        for op in orderpoints:
            if op.product_id.qty_available < op.product_min_qty:
                low_stock.append({
                    'name': op.product_id.display_name,
                    'qty': op.product_id.qty_available,
                    'min': op.product_min_qty,
                })

        if not low_stock:
            return

        company_name = self.env.company.name or ''

        # Get template to use its body for truncation estimation
        company_lang = self.env.company.partner_id.lang or ''
        lang = 'ar' if company_lang.startswith('ar') else 'en'
        template = self.env['kwtsms.sms.template'].get_template_for_event(
            'admin_low_stock', lang,
        )
        if not template:
            return

        details = self._build_truncated_details(
            items=['%s: %.0f (min %.0f)' % (item['name'], item['qty'], item['min']) for item in low_stock],
            template_body=template.body,
            context_base={'company_name': company_name, 'count': str(len(low_stock))},
        )

        context_data = {
            'company_name': company_name,
            'count': str(len(low_stock)),
            'details': details,
        }

        phone = (
            ICP.get_param('kwtsms.admin_phone_inventory', '')
            or ICP.get_param('kwtsms.admin_phone', '')
        )
        if not phone:
            _logger.info('kwtSMS: No admin phone for low stock alert, skipping')
            return

        message = template.render_from_dict(context_data)

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        api = KwtSmsApi(self.env)
        api.send(
            phone, message,
            template_id=template.id,
            res_model='stock.warehouse.orderpoint',
            res_id=0,
            recipient_type='admin',
        )

    def _cron_admin_overdue_invoices(self):
        """Daily cron: send admin SMS summary of overdue customer invoices."""
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('kwtsms.enabled', 'False') != 'True':
            return
        if ICP.get_param('kwtsms.auto_admin_invoice_overdue', 'False') != 'True':
            return

        days = int(ICP.get_param('kwtsms.overdue_invoice_days', '30'))
        cutoff = fields.Date.today() - timedelta(days=days)

        invoices = self.env['account.move'].sudo().search([
            ('move_type', '=', 'out_invoice'),
            ('payment_state', 'not in', ['paid', 'reversed', 'in_payment']),
            ('invoice_date_due', '<', cutoff),
        ])

        if not invoices:
            return

        company_name = self.env.company.name or ''
        total = sum(inv.amount_residual for inv in invoices)
        currency = invoices[0].currency_id.symbol if invoices[0].currency_id else ''

        company_lang = self.env.company.partner_id.lang or ''
        lang = 'ar' if company_lang.startswith('ar') else 'en'
        template = self.env['kwtsms.sms.template'].get_template_for_event(
            'admin_invoice_overdue', lang,
        )
        if not template:
            return

        details = self._build_truncated_details(
            items=['%s: %s %s' % (inv.name, inv.amount_residual, currency) for inv in invoices],
            template_body=template.body,
            context_base={
                'company_name': company_name,
                'count': str(len(invoices)),
                'total_amount': '%s %s' % (total, currency),
            },
        )

        context_data = {
            'company_name': company_name,
            'count': str(len(invoices)),
            'total_amount': '%s %s' % (total, currency),
            'details': details,
        }

        phone = (
            ICP.get_param('kwtsms.admin_phone_accounting', '')
            or ICP.get_param('kwtsms.admin_phone', '')
        )
        if not phone:
            _logger.info('kwtSMS: No admin phone for overdue invoices, skipping')
            return

        message = template.render_from_dict(context_data)

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        api = KwtSmsApi(self.env)
        api.send(
            phone, message,
            template_id=template.id,
            res_model='account.move',
            res_id=0,
            recipient_type='admin',
        )

    def _cron_refresh_all(self):
        """Cron job: refresh balance, sender IDs, and coverage for connected companies.

        On auth failure, marks gateway as error and stops retrying.
        Skips entirely when the gateway is disabled.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('kwtsms.enabled', 'True') != 'True':
            _logger.debug('kwtSMS cron: gateway disabled, skipping refresh.')
            return

        configs = self.search([('api_status', '=', 'connected')])
        for config in configs:
            try:
                from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
                api = KwtSmsApi(config.env)

                balance_resp = api.check_balance()
                if balance_resp.get('result') != 'OK':
                    error_msg = balance_resp.get('description', 'Unknown error')
                    _logger.warning(
                        'kwtSMS cron: auth failed for company %s: %s',
                        config.company_id.name, error_msg,
                    )
                    config.write({
                        'api_status': 'error',
                        'api_error': error_msg,
                    })
                    continue

                vals = {
                    'balance_available': balance_resp.get('available', 0),
                    'balance_purchased': balance_resp.get('purchased', 0),
                    'last_verified': fields.Datetime.now(),
                }

                sender_resp = api.fetch_sender_ids()
                if sender_resp.get('result') == 'OK':
                    sender_list = sender_resp.get('senderid', [])
                    vals['sender_ids_json'] = json.dumps(sender_list, ensure_ascii=False)

                coverage_resp = api.fetch_coverage()
                if coverage_resp.get('result') == 'OK':
                    prefixes = coverage_resp.get('prefixes', [])
                    vals['coverage_json'] = json.dumps(prefixes, ensure_ascii=False)

                config.write(vals)

            except Exception as e:
                _logger.error('kwtSMS cron: refresh failed for company %s: %s',
                              config.company_id.name, e)
