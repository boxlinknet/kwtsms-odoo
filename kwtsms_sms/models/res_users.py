"""MFA hooks for SMS OTP authentication."""

from odoo import models


class ResUsers(models.Model):
    """Override MFA hooks for SMS OTP on login."""

    _inherit = 'res.users'

    def _mfa_type(self):
        """Return 'sms_otp' if SMS OTP is enabled for this user type."""
        r = super()._mfa_type()
        if r:
            return r  # Another MFA (e.g., auth_totp) takes precedence

        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('kwtsms.enabled', 'False') != 'True':
            return r

        if self.has_group('base.group_user'):
            # Internal/backend user
            if ICP.get_param('kwtsms.otp_backend_login', 'False') == 'True':
                return 'sms_otp'
        else:
            # Portal user
            if ICP.get_param('kwtsms.otp_portal_login', 'False') == 'True':
                return 'sms_otp'
        return r

    def _mfa_url(self):
        """Return OTP verify URL when SMS OTP is the active MFA type."""
        r = super()._mfa_url()
        if r:
            return r
        if self._mfa_type() == 'sms_otp':
            return '/kwtsms/otp/verify'
        return r
