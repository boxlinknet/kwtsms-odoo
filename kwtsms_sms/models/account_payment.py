"""SMS notification on payment receipt."""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    """Hook into account.payment.action_post for payment SMS."""

    _inherit = ['account.payment', 'kwtsms.notification.mixin', 'kwtsms.admin.notification.mixin']
    _name = 'account.payment'
    _description = 'Payments'

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
            try:
                invoice_name = ''
                if payment.reconciled_invoice_ids:
                    invoice_name = payment.reconciled_invoice_ids[0].name or ''
                currency = payment.currency_id.symbol if payment.currency_id else ''
                payment._kwtsms_send_admin_notification(
                    'admin_payment_received',
                    'kwtsms.auto_admin_payment_received',
                    'kwtsms.admin_phone_accounting',
                    {
                        'company_name': payment.company_id.name or '',
                        'customer_name': payment.partner_id.name or '',
                        'amount': '%s %s' % (payment.amount, currency),
                        'invoice_name': invoice_name,
                    },
                )
            except Exception as e:
                _logger.error(
                    'kwtSMS: Admin payment received SMS failed for %s: %s',
                    payment.name, e,
                )

        return result
