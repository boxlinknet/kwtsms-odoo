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

        # Fetch coverage (API returns 'prefixes' key with country code list)
        coverage_resp = api.fetch_coverage()
        if coverage_resp.get('result') == 'OK':
            prefixes = coverage_resp.get('prefixes', [])
            vals['coverage_json'] = json.dumps(prefixes, ensure_ascii=False)

        self.write(vals)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
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

    def _cron_refresh_all(self):
        """Cron job: refresh balance, sender IDs, and coverage for connected companies.

        On auth failure, marks gateway as error and stops retrying.
        """
        configs = self.search([('api_status', '=', 'connected')])
        for config in configs:
            try:
                from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
                api = KwtSmsApi(config.env)

                # Check balance (also verifies credentials)
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

                # Refresh sender IDs
                sender_resp = api.fetch_sender_ids()
                if sender_resp.get('result') == 'OK':
                    sender_list = sender_resp.get('senderid', [])
                    vals['sender_ids_json'] = json.dumps(sender_list, ensure_ascii=False)

                # Refresh coverage
                coverage_resp = api.fetch_coverage()
                if coverage_resp.get('result') == 'OK':
                    prefixes = coverage_resp.get('prefixes', [])
                    vals['coverage_json'] = json.dumps(prefixes, ensure_ascii=False)

                config.write(vals)

            except Exception as e:
                _logger.error('kwtSMS cron: refresh failed for company %s: %s',
                              config.company_id.name, e)
