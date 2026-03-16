"""Shared SMS notification logic for admin event hooks."""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class KwtSmsAdminNotificationMixin(models.AbstractModel):
    """Mixin providing SMS notification logic for admin events.

    Unlike the customer mixin (kwtsms.notification.mixin) which reads
    phone from partner and renders from record fields, this mixin:
    - Resolves phone from config: per-app override > global admin phone
    - Renders templates from an explicit context_data dict
    - Uses company language (not partner language)
    """

    _name = 'kwtsms.admin.notification.mixin'
    _description = 'kwtSMS Admin Notification Mixin'

    def _kwtsms_send_admin_notification(self, event_type, config_key,
                                         app_override_key, context_data,
                                         res_model=None, res_id=None):
        """Send SMS to admin for a business event.

        Args:
            event_type: Template event type (e.g. 'admin_new_quotation').
            config_key: ICP key for event toggle
                        (e.g. 'kwtsms.auto_admin_new_quotation').
            app_override_key: ICP key for per-app phone override
                              (e.g. 'kwtsms.admin_phone_sales').
            context_data: Dict of placeholder values for template rendering.
            res_model: Override for log's related model (default: self._name).
            res_id: Override for log's related record ID (default: self.id).
        """
        ICP = self.env['ir.config_parameter'].sudo()

        if ICP.get_param('kwtsms.enabled', 'False') != 'True':
            return
        if ICP.get_param(config_key, 'False') != 'True':
            return

        phone = (
            ICP.get_param(app_override_key, '')
            or ICP.get_param('kwtsms.admin_phone', '')
        )
        if not phone:
            _logger.info(
                'kwtSMS: No admin phone configured for %s, skipping',
                event_type,
            )
            return

        company_lang = self.env.company.partner_id.lang or ''
        lang = 'ar' if company_lang.startswith('ar') else 'en'

        template = self.env['kwtsms.sms.template'].get_template_for_event(
            event_type, lang,
        )
        if not template:
            _logger.info(
                'kwtSMS: No template for admin event %s lang %s',
                event_type, lang,
            )
            return

        message = template.render_from_dict(context_data)

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        api = KwtSmsApi(self.env)
        api.send(
            phone, message,
            template_id=template.id,
            res_model=res_model or self._name,
            res_id=(
                res_id if res_id is not None
                else (self.id if isinstance(self.id, int) else 0)
            ),
            recipient_type='admin',
        )
