"""SMS notification on delivery completion."""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    """Hook into stock.picking._action_done to send SMS notifications."""

    _inherit = ['stock.picking', 'kwtsms.notification.mixin', 'kwtsms.admin.notification.mixin']
    _name = 'stock.picking'
    _description = 'Transfer'

    def _action_done(self):
        """Send SMS after delivery completion.

        SMS failures never block the business operation.
        """
        result = super()._action_done()

        for picking in self:
            if picking.picking_type_code != 'outgoing':
                continue
            try:
                picking._kwtsms_send_notification(
                    'delivery_done', 'kwtsms.auto_delivery_done')
            except Exception as e:
                _logger.error(
                    'kwtSMS: Failed to send delivery SMS for %s: %s',
                    picking.name, e,
                )

        for picking in self:
            if picking.picking_type_code != 'incoming':
                continue
            try:
                picking._kwtsms_send_admin_notification(
                    'admin_incoming_shipment',
                    'kwtsms.auto_admin_incoming_shipment',
                    'kwtsms.admin_phone_inventory',
                    {
                        'company_name': picking.company_id.name or '',
                        'picking_name': picking.name or '',
                        'supplier_name': picking.partner_id.name or '',
                        'product_count': str(len(picking.move_ids)),
                    },
                )
            except Exception as e:
                _logger.error(
                    'kwtSMS: Admin incoming shipment SMS failed for %s: %s',
                    picking.name, e,
                )

        return result
