"""Send Test SMS Wizard."""

import logging

from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class KwtSmsTestWizard(models.TransientModel):
    """Wizard to send a test SMS from Settings."""

    _name = 'kwtsms.test.sms.wizard'
    _description = 'Send Test SMS'

    phone = fields.Char(
        string='Phone Number',
        required=True,
    )
    message = fields.Text(
        string='Message',
        required=True,
    )

    def action_send(self):
        """Send test SMS through the kwtSMS gateway."""
        self.ensure_one()

        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('kwtsms.enabled', 'True') != 'True':
            raise UserError(_('SMS gateway is disabled. Enable it in kwtSMS Gateway settings.'))

        if not self.phone:
            raise UserError(_('Phone number is required.'))
        if not self.message:
            raise UserError(_('Message is required.'))
        username = ICP.get_param('kwtsms.api_username', '')
        password = ICP.get_param('kwtsms.api_password', '')
        if not username or not password:
            raise UserError(_('Please enter API credentials and login first.'))

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        api_client = KwtSmsApi(self.env)

        # Force test mode ON for the test wizard, regardless of system setting
        system_test_mode = api_client._test_mode
        api_client._test_mode = True

        response = api_client.send(self.phone, self.message)

        if response.get('result') == 'OK':
            api_client._log_send(
                numbers=self.phone,
                message=self.message,
                response=response,
                status='test',
            )
            live_warning = ''
            if not system_test_mode:
                live_warning = _(' WARNING: System test mode is OFF.')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Test SMS Sent'),
                    'message': _('Test SMS sent to %s (test mode).%s') % (self.phone, live_warning),
                    'type': 'success',
                    'sticky': False,
                },
            }
        else:
            error_msg = response.get('description', _('Unknown error'))
            api_client._log_send(
                numbers=self.phone,
                message=self.message,
                response=response,
                status='error',
                error_code=response.get('code'),
                error_description=error_msg,
            )
            raise UserError(_('Test SMS failed: %s') % error_msg)
