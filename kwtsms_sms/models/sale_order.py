"""SMS notifications on sale order events."""

import logging

from odoo import models, api

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """Hook into sale.order for SMS notifications."""

    _inherit = ['sale.order', 'kwtsms.notification.mixin', 'kwtsms.admin.notification.mixin']
    _name = 'sale.order'
    _description = 'Sales Order'

    @api.model_create_multi
    def create(self, vals_list):
        """Send admin SMS for new quotation creation."""
        orders = super().create(vals_list)
        for order in orders:
            try:
                currency = order.currency_id.symbol if order.currency_id else ''
                order._kwtsms_send_admin_notification(
                    'admin_new_quotation',
                    'kwtsms.auto_admin_new_quotation',
                    'kwtsms.admin_phone_sales',
                    {
                        'company_name': order.company_id.name or '',
                        'order_name': order.name or '',
                        'customer_name': order.partner_id.name or '',
                        'amount': '%s %s' % (order.amount_total, currency),
                        'salesperson': order.user_id.name or '',
                    },
                )
            except Exception as e:
                _logger.error(
                    'kwtSMS: Admin new quotation SMS failed for %s: %s',
                    order.name, e,
                )
        return orders

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

            try:
                ICP = self.env['ir.config_parameter'].sudo()
                threshold = float(ICP.get_param('kwtsms.large_order_threshold', '1000'))
                if order.amount_total >= threshold:
                    currency = order.currency_id.symbol if order.currency_id else ''
                    order._kwtsms_send_admin_notification(
                        'admin_large_order',
                        'kwtsms.auto_admin_large_order',
                        'kwtsms.admin_phone_sales',
                        {
                            'company_name': order.company_id.name or '',
                            'order_name': order.name or '',
                            'customer_name': order.partner_id.name or '',
                            'amount': '%s %s' % (order.amount_total, currency),
                        },
                    )
            except Exception as e:
                _logger.error(
                    'kwtSMS: Admin large order SMS failed for %s: %s',
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

            try:
                currency = order.currency_id.symbol if order.currency_id else ''
                order._kwtsms_send_admin_notification(
                    'admin_order_cancelled',
                    'kwtsms.auto_admin_order_cancelled',
                    'kwtsms.admin_phone_sales',
                    {
                        'company_name': order.company_id.name or '',
                        'order_name': order.name or '',
                        'customer_name': order.partner_id.name or '',
                        'amount': '%s %s' % (order.amount_total, currency),
                    },
                )
            except Exception as e:
                _logger.error(
                    'kwtSMS: Admin order cancel SMS failed for %s: %s',
                    order.name, e,
                )

        return result
