"""kwtSMS OTP Audit Log model."""

import logging
from datetime import timedelta

from odoo import models, fields

_logger = logging.getLogger(__name__)


class KwtSmsOtpLog(models.Model):
    """Append-only audit trail for all OTP events."""

    _name = 'kwtsms.otp.log'
    _description = 'kwtSMS OTP Log'
    _order = 'create_date desc'

    phone = fields.Char(string='Phone', index=True)
    ip_address = fields.Char(string='IP Address', index=True)
    user_id = fields.Many2one('res.users', string='User')
    otp_type = fields.Selection([
        ('portal_login', 'Portal Login'),
        ('backend_login', 'Backend Login'),
        ('passwordless', 'Passwordless'),
        ('signup', 'Signup'),
        ('password_reset', 'Password Reset'),
    ], string='OTP Type')
    action = fields.Selection([
        ('request', 'OTP Requested'),
        ('resend', 'OTP Resent'),
        ('verify_ok', 'Verified OK'),
        ('verify_failed', 'Verification Failed'),
        ('expired', 'Expired'),
        ('locked_out', 'Locked Out'),
        ('invalid_phone', 'Invalid Phone'),
        ('user_not_found', 'User Not Found'),
        ('captcha_failed', 'CAPTCHA Failed'),
        ('ambiguous_phone', 'Ambiguous Phone'),
        ('device_trusted', 'Device Trusted'),
        ('device_skip', 'Device Skip'),
        ('device_revoked', 'Device Revoked'),
        ('password_changed', 'Password Changed'),
    ], string='Action', index=True, required=True)
    error_reason = fields.Char(string='Error Reason')
    user_agent = fields.Char(string='User Agent')
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    def _cron_cleanup_old_otp_logs(self):
        """Daily cron: delete OTP logs older than retention days."""
        ICP = self.env['ir.config_parameter'].sudo()
        retention_days = int(ICP.get_param('kwtsms.log_retention_days', '90'))
        if retention_days <= 0:
            return
        cutoff = fields.Datetime.now() - timedelta(days=retention_days)
        old_logs = self.search([('create_date', '<', cutoff)])
        count = len(old_logs)
        if count:
            old_logs.unlink()
            _logger.info('kwtSMS OTP: Cleaned up %d old OTP log entries', count)
