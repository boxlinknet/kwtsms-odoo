"""SMS notification on invoice posting."""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    """Hook into account.move.action_post for invoice SMS."""

    _inherit = 'account.move'

    def action_post(self):
        """Send SMS after customer invoice is posted."""
        result = super().action_post()

        for move in self:
            if move.move_type != 'out_invoice':
                continue
            try:
                move._kwtsms_send_notification('invoice_posted')
            except Exception as e:
                _logger.error(
                    'kwtSMS: Failed to send invoice posted SMS for %s: %s',
                    move.name, e,
                )

        return result

    def _kwtsms_send_notification(self, event_type):
        """Send SMS notification for an invoice event."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()

        if ICP.get_param('kwtsms.enabled', 'False') != 'True':
            return
        if ICP.get_param('kwtsms.auto_invoice_posted', 'False') != 'True':
            return

        partner = self.partner_id
        if not partner:
            return
        phone = partner.phone
        if not phone:
            _logger.info('kwtSMS: No phone for partner %s, skipping SMS', partner.name)
            return

        lang = 'ar' if partner.lang and partner.lang.startswith('ar') else 'en'

        template = self.env['kwtsms.sms.template'].get_template_for_event(event_type, lang)
        if not template:
            _logger.info('kwtSMS: No template for event %s lang %s', event_type, lang)
            return

        message = template.render_template(self)

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        api = KwtSmsApi(self.env)
        response = api.send_single(phone, message)

        status = 'success' if response.get('result') == 'OK' else 'error'
        if api._test_mode and status == 'success':
            status = 'test'

        api._log_send(
            numbers=phone,
            message=message,
            response=response,
            status=status,
            error_code=response.get('code') if status == 'error' else None,
            error_description=response.get('description') if status == 'error' else None,
            template_id=template.id,
            res_model='account.move',
            res_id=self.id,
        )
