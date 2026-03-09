"""kwtSMS Gateway Configuration model."""

import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class KwtSmsGatewayConfig(models.Model):
    """Stores dynamic gateway state: sender IDs, coverage, balance."""

    _name = 'kwtsms.gateway.config'
    _description = 'kwtSMS Gateway Configuration'

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
        string='Last Verified',
    )
    api_status = fields.Selection([
        ('not_configured', 'Not Configured'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], string='API Status', default='not_configured')
    api_error = fields.Char(
        string='API Error',
    )

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
        return config

    def action_login_verify(self):
        """Verify credentials and fetch account data from kwtSMS API.

        Called from the settings page Login/Verify button.

        Returns:
            dict: Notification action with success or error message.
        """
        self.ensure_one()
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
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': error_msg,
                    'type': 'danger',
                    'sticky': False,
                },
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
            coverage_data = coverage_resp.get('coverage', [])
            vals['coverage_json'] = json.dumps(coverage_data, ensure_ascii=False)

        self.write(vals)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Connected'),
                'message': _('Gateway verified. Balance: %s') % vals['balance_available'],
                'type': 'success',
                'sticky': False,
            },
        }

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

    def get_balance(self):
        """Return available balance.

        Returns:
            int: Available SMS credits.
        """
        self.ensure_one()
        return self.balance_available

    def _cron_refresh_balance(self):
        """Cron job: refresh balance for all configured companies."""
        configs = self.search([('api_status', '=', 'connected')])
        for config in configs:
            try:
                from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
                api = KwtSmsApi(config.env)
                resp = api.check_balance()
                if resp.get('result') == 'OK':
                    config.write({
                        'balance_available': resp.get('available', 0),
                        'balance_purchased': resp.get('purchased', 0),
                        'last_verified': fields.Datetime.now(),
                    })
            except Exception as e:
                _logger.error('Balance refresh failed for company %s: %s',
                              config.company_id.name, e)
