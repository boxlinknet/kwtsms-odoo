"""SMS Sender for sending SMS directly from records."""

import logging
import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from odoo.addons.kwtsms_sms.tools.phone_utils import count_sms_parts

_logger = logging.getLogger(__name__)


class KwtSmsComposeWizard(models.TransientModel):
    """Compose and send SMS via kwtSMS from any record."""

    _name = 'kwtsms.sms.compose'
    _description = 'SMS Sender'

    phone = fields.Text(
        string='Phone Number(s)',
        required=True,
        help='Enter one or more phone numbers, separated by commas or one per line.',
    )
    message = fields.Text(
        string='Message',
        required=True,
    )
    template_id = fields.Many2one(
        'kwtsms.sms.template',
        string='Template',
    )
    res_model = fields.Char(
        string='Related Model',
        default=lambda self: self.env.context.get('active_model'),
    )
    res_id = fields.Integer(
        string='Related Record ID',
        default=lambda self: self.env.context.get('active_id', 0),
    )
    char_count = fields.Integer(
        string='Characters',
        compute='_compute_sms_info',
    )
    page_count = fields.Integer(
        string='SMS Pages',
        compute='_compute_sms_info',
    )
    is_unicode = fields.Boolean(
        string='Unicode',
        compute='_compute_sms_info',
    )
    test_mode = fields.Boolean(
        string='Test Mode',
        default=lambda self: self.env['ir.config_parameter'].sudo().get_param(
            'kwtsms.test_mode', 'True') == 'True',
    )

    @api.depends('message')
    def _compute_sms_info(self):
        for record in self:
            if record.message:
                chars, pages, unicode_msg = count_sms_parts(record.message)
                record.char_count = chars
                record.page_count = pages
                record.is_unicode = unicode_msg
            else:
                record.char_count = 0
                record.page_count = 0
                record.is_unicode = False

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Populate message from selected template."""
        if self.template_id and self.template_id.body:
            if self.res_model and self.res_id and self.res_model in self._ALLOWED_SOURCE_MODELS:
                record = self.env[self.res_model].browse(self.res_id)
                if record.exists():
                    self.message = self.template_id.render_template(record)
                    return
            self.message = self.template_id.body

    _ALLOWED_SOURCE_MODELS = {
        'res.partner', 'sale.order', 'stock.picking',
        'account.move', 'account.payment',
    }

    @api.model
    def default_get(self, fields_list):
        """Pre-fill phone from the active record context."""
        defaults = super().default_get(fields_list)
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')

        if active_model and active_id and active_model in self._ALLOWED_SOURCE_MODELS:
            record = self.env[active_model].browse(active_id)
            if record.exists():
                if hasattr(record, 'partner_id') and record.partner_id:
                    partner = record.partner_id
                    defaults['phone'] = partner.phone or ''
                elif hasattr(record, 'phone'):
                    defaults['phone'] = record.phone or ''

        return defaults

    def action_send(self):
        """Send the SMS message to one or more phone numbers."""
        self.ensure_one()

        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('kwtsms.enabled', 'True') != 'True':
            raise UserError(_('SMS gateway is disabled. Enable it in kwtSMS Gateway settings.'))

        if not self.phone:
            raise UserError(_('Phone number is required.'))
        if not self.message:
            raise UserError(_('Message is required.'))

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        api = KwtSmsApi(self.env)

        # Split by commas or newlines, strip whitespace
        phones = [p.strip() for p in re.split(r'[,\n\r]+', self.phone) if p.strip()]

        response = api.send(phones, self.message)

        valid_count = response.get('valid_count', 0)
        invalid_count = response.get('invalid_count', 0)
        duplicates = response.get('duplicates_removed', 0)
        numbers_sent = response.get('numbers_sent', ','.join(phones))

        if response.get('result') in ('OK', 'PARTIAL'):
            status = 'test' if api._test_mode else 'success'
            api._log_send(
                numbers=numbers_sent,
                message=self.message,
                response=response,
                status=status,
                template_id=self.template_id.id if self.template_id else None,
                res_model=self.res_model,
                res_id=self.res_id,
            )

            if len(phones) == 1 and valid_count == 1:
                msg = _('Message sent to %s') % numbers_sent
            else:
                msg_parts = [_('Message sent to %d number(s).') % valid_count]
                if duplicates:
                    msg_parts.append(
                        _('%d duplicate(s) removed.') % duplicates
                    )
                if invalid_count:
                    invalid_list = response.get('invalid', [])
                    bad_nums = ', '.join(
                        '%s (%s)' % (i['input'], i['reason'])
                        for i in invalid_list
                    )
                    msg_parts.append(
                        _('%d number(s) skipped: %s') % (invalid_count, bad_nums)
                    )
                msg = ' '.join(msg_parts)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('SMS Sent'),
                    'message': msg,
                    'type': 'success' if not invalid_count else 'warning',
                    'sticky': bool(invalid_count),
                },
            }
        else:
            error_msg = response.get('description', _('Unknown error'))
            api._log_send(
                numbers=numbers_sent,
                message=self.message,
                response=response,
                status='error',
                error_code=response.get('code'),
                error_description=error_msg,
                template_id=self.template_id.id if self.template_id else None,
                res_model=self.res_model,
                res_id=self.res_id,
            )
            raise UserError(_('SMS sending failed: %s') % error_msg)
