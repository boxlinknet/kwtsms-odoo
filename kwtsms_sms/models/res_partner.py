"""Normalized phone fields for OTP phone lookups."""

from odoo import models, fields, api

from odoo.addons.kwtsms_sms.tools.phone_utils import prepare_phone


class ResPartner(models.Model):
    """Add stored normalized phone field for indexed OTP lookups."""

    _inherit = 'res.partner'

    kwtsms_phone_normalized = fields.Char(
        string='Normalized Phone',
        compute='_compute_kwtsms_phone_normalized',
        store=True,
        index=True,
    )

    @api.depends('phone')
    def _compute_kwtsms_phone_normalized(self):
        default_cc = self.env['ir.config_parameter'].sudo().get_param(
            'kwtsms.default_country_code', '965',
        )
        for partner in self:
            if partner.phone:
                norm, _ = prepare_phone(partner.phone, default_cc)
                partner.kwtsms_phone_normalized = norm or False
            else:
                partner.kwtsms_phone_normalized = False
