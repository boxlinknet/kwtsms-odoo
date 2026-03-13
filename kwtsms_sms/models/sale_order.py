"""SMS notifications on sale order events."""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """Hook into sale.order for SMS notifications."""

    _inherit = ['sale.order', 'kwtsms.notification.mixin']
    _name = 'sale.order'

    def action_confirm(self):
        """Send SMS after order confirmation."""
        result = super().action_confirm()

        for order in self:
            try:
                order._kwtsms_send_notification(
                    'order_confirm', 'kwtsms.auto_order_confirm')
            except Exception as e:
                _logger.error(
                    'kwtSMS: Failed to send order confirmation SMS for %s: %s',
                    order.name, e,
                )

        return result

    def action_cancel(self):
        """Send SMS after order cancellation."""
        result = super().action_cancel()

        for order in self:
            try:
                order._kwtsms_send_notification(
                    'order_cancel', 'kwtsms.auto_order_cancel')
            except Exception as e:
                _logger.error(
                    'kwtSMS: Failed to send order cancellation SMS for %s: %s',
                    order.name, e,
                )

        return result
