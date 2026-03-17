"""kwtSMS OTP Device Trust model."""

import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class KwtSmsOtpDevice(models.Model):
    """Remembered device trust tokens for OTP bypass."""

    _name = 'kwtsms.otp.device'
    _description = 'kwtSMS OTP Trusted Device'
    _order = 'create_date desc'

    user_id = fields.Many2one(
        'res.users', string='User', required=True, index=True,
        ondelete='cascade',
    )
    device_hash = fields.Char(string='Device Hash', required=True, index=True)
    user_agent_hash = fields.Char(string='User Agent Hash')
    expires_at = fields.Datetime(string='Expires At', index=True)
    ip_address = fields.Char(string='IP Address')
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    def _cron_cleanup_expired_devices(self):
        """Daily cron: delete expired device trust records."""
        expired = self.search([
            ('expires_at', '<', fields.Datetime.now()),
        ])
        count = len(expired)
        if count:
            expired.unlink()
            _logger.info('kwtSMS OTP: Cleaned up %d expired device trusts', count)
