"""Shared SMS notification logic for business event hooks."""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class KwtSmsNotificationMixin(models.AbstractModel):
    """Mixin providing SMS notification logic for business event hooks.

    Inherit this mixin and call _kwtsms_send_notification() from your
    business event hooks (action_confirm, _action_done, action_post, etc.).
    """

    _name = 'kwtsms.notification.mixin'
    _description = 'kwtSMS Notification Mixin'

    def _kwtsms_send_notification(self, event_type, config_key):
        """Send SMS notification for a business event.

        Args:
            event_type: Template event type (e.g. 'order_confirm').
            config_key: ICP key for the feature toggle (e.g. 'kwtsms.auto_order_confirm').
        """
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()

        if ICP.get_param('kwtsms.enabled', 'False') != 'True':
            return
        if ICP.get_param(config_key, 'False') != 'True':
            return

        partner = self.partner_id if hasattr(self, 'partner_id') else None
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
            res_model=self._name,
            res_id=self.id,
        )
