"""Override res.company to route SMS through kwtSMS."""

from odoo import models


class ResCompany(models.Model):
    """Route Odoo SMS framework through kwtSMS gateway."""

    _inherit = 'res.company'

    def _get_sms_api_class(self):
        """Return KwtSmsApi when kwtSMS is configured.

        This is the critical integration point. Once configured, ALL SMS
        sent through Odoo's standard SMS framework will route through kwtSMS.

        Returns:
            class: KwtSmsApi if configured, otherwise default Odoo class.
        """
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        username = ICP.get_param('kwtsms.api_username', '')
        enabled = ICP.get_param('kwtsms.enabled', 'False') == 'True'

        if enabled and username:
            from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
            return KwtSmsApi
        return super()._get_sms_api_class()
