"""SMS notification on delivery completion."""

import logging

from odoo import models, _

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    """Hook into stock.picking._action_done to send SMS notifications."""

    _inherit = 'stock.picking'

    def _action_done(self):
        """Send SMS after delivery completion.

        SMS failures never block the business operation.
        """
        result = super()._action_done()

        for picking in self:
            if picking.picking_type_code != 'outgoing':
                continue
            try:
                picking._kwtsms_send_notification('delivery_done')
            except Exception as e:
                _logger.error(
                    'kwtSMS: Failed to send delivery SMS for %s: %s',
                    picking.name, e,
                )

        return result

    def _kwtsms_send_notification(self, event_type):
        """Send SMS notification for a delivery event.

        Args:
            event_type: Template event type (e.g. 'delivery_done').
        """
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()

        # Check if enabled
        if ICP.get_param('kwtsms.enabled', 'False') != 'True':
            return
        if ICP.get_param('kwtsms.auto_delivery_done', 'False') != 'True':
            return

        # Get phone number
        partner = self.partner_id
        if not partner:
            return
        phone = partner.phone
        if not phone:
            _logger.info('kwtSMS: No phone for partner %s, skipping SMS', partner.name)
            return

        # Detect language
        lang = 'ar' if partner.lang and partner.lang.startswith('ar') else 'en'

        # Get template
        template = self.env['kwtsms.sms.template'].get_template_for_event(event_type, lang)
        if not template:
            _logger.info('kwtSMS: No template for event %s lang %s', event_type, lang)
            return

        # Render message
        message = template.render_template(self)

        # Send via API
        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        api = KwtSmsApi(self.env)
        response = api.send_single(phone, message)

        # Log result
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
            res_model='stock.picking',
            res_id=self.id,
        )
