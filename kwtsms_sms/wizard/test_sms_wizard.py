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
        """Send test SMS through the kwtSMS gateway (always in test mode)."""
        self.ensure_one()

        if not self.phone:
            raise UserError(_('Phone number is required.'))
        if not self.message:
            raise UserError(_('Message is required.'))

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        api_client = KwtSmsApi(self.env)

        # Force test mode ON regardless of global setting
        response = api_client.send(self.phone, self.message, test_mode=True)

        if response.get('result') == 'OK':
            live_warning = ''
            if not api_client._test_mode:
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
            raise UserError(_('Test SMS failed: %s') % error_msg)
