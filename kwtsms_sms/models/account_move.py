"""SMS notification on invoice posting."""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    """Hook into account.move.action_post for invoice SMS."""

    _inherit = ['account.move', 'kwtsms.notification.mixin']
    _name = 'account.move'
    _description = 'Journal Entry'

    def action_post(self):
        """Send SMS after customer invoice is posted."""
        result = super().action_post()

        for move in self:
            if move.move_type != 'out_invoice':
                continue
            try:
                move._kwtsms_send_notification(
                    'invoice_posted', 'kwtsms.auto_invoice_posted')
            except Exception as e:
                _logger.error(
                    'kwtSMS: Failed to send invoice posted SMS for %s: %s',
                    move.name, e,
                )

        return result
