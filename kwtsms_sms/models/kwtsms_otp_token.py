"""kwtSMS OTP Token model for active OTP sessions."""

import logging
from datetime import timedelta

from odoo import models, fields

_logger = logging.getLogger(__name__)


class KwtSmsOtpToken(models.Model):
    """Active OTP sessions and rate limit enforcement store."""

    _name = 'kwtsms.otp.token'
    _description = 'kwtSMS OTP Token'
    _order = 'create_date desc'

    phone = fields.Char(string='Phone', index=True, required=True)
    otp_hash = fields.Char(string='OTP Hash')
    otp_type = fields.Selection([
        ('portal_login', 'Portal Login'),
        ('backend_login', 'Backend Login'),
        ('passwordless', 'Passwordless'),
        ('signup', 'Signup'),
        ('password_reset', 'Password Reset'),
    ], string='OTP Type', required=True)
    user_id = fields.Many2one('res.users', string='User')
    ip_address = fields.Char(string='IP Address', index=True)
    expires_at = fields.Datetime(string='Expires At', index=True)
    attempt_count = fields.Integer(string='Attempts', default=0)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('expired', 'Expired'),
        ('locked', 'Locked'),
    ], string='State', default='pending', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    def _cron_cleanup_expired_tokens(self):
        """Hourly cron: delete completed and abandoned tokens."""
        cutoff = fields.Datetime.now() - timedelta(hours=24)
        # Delete completed tokens older than 24h
        old_tokens = self.search([
            ('state', 'in', ['verified', 'expired', 'locked']),
            ('create_date', '<', cutoff),
        ])
        # Also delete abandoned pending tokens past expiry
        abandoned = self.search([
            ('state', '=', 'pending'),
            ('expires_at', '<', fields.Datetime.now()),
        ])
        to_delete = old_tokens | abandoned
        count = len(to_delete)
        if count:
            to_delete.unlink()
            _logger.info('kwtSMS OTP: Cleaned up %d expired tokens', count)
