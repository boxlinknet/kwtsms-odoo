"""SMS notification on payment receipt."""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    """Hook into account.payment.action_post for payment SMS."""

    _inherit = 'account.payment'

    def action_post(self):
        """Send SMS after inbound payment is posted."""
        result = super().action_post()

        for payment in self:
            if payment.payment_type != 'inbound':
                continue
            try:
                payment._kwtsms_send_payment_notification('payment_received')
            except Exception as e:
                _logger.error(
                    'kwtSMS: Failed to send payment received SMS for %s: %s',
                    payment.name, e,
                )

        return result

    def _kwtsms_send_payment_notification(self, event_type):
        """Send SMS notification for a payment event."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()

        if ICP.get_param('kwtsms.enabled', 'False') != 'True':
            return
        if ICP.get_param('kwtsms.auto_payment_received', 'False') != 'True':
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
        response = api.send(phone, message)

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
            res_model='account.payment',
            res_id=self.id,
        )
