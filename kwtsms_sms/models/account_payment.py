"""SMS notification on payment receipt."""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    """Hook into account.payment.action_post for payment SMS."""

    _inherit = ['account.payment', 'kwtsms.notification.mixin']
    _name = 'account.payment'

    def action_post(self):
        """Send SMS after inbound payment is posted."""
        result = super().action_post()

        for payment in self:
            if payment.payment_type != 'inbound':
                continue
            try:
                payment._kwtsms_send_notification(
                    'payment_received', 'kwtsms.auto_payment_received')
            except Exception as e:
                _logger.error(
                    'kwtSMS: Failed to send payment received SMS for %s: %s',
                    payment.name, e,
                )

        return result
