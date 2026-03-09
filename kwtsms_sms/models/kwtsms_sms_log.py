"""kwtSMS Message Log model."""

import logging
from datetime import timedelta

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class KwtSmsLog(models.Model):
    """Full audit trail of all SMS attempts."""

    _name = 'kwtsms.sms.log'
    _description = 'kwtSMS Message Log'
    _order = 'create_date desc'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )
    phone_number = fields.Char(
        string='Phone Number',
        required=True,
        index=True,
    )
    message_body = fields.Text(
        string='Message Body',
    )
    template_id = fields.Many2one(
        'kwtsms.sms.template',
        string='Template',
    )
    sender_id = fields.Char(
        string='Sender ID',
    )
    status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('test', 'Test'),
        ('queued', 'Queued'),
    ], string='Status', default='queued', index=True)
    api_response = fields.Text(
        string='API Response',
    )
    msg_id = fields.Char(
        string='Message ID',
        index=True,
    )
    points_charged = fields.Integer(
        string='Points Charged',
        default=0,
    )
    balance_after = fields.Integer(
        string='Balance After',
        default=0,
    )
    error_code = fields.Char(
        string='Error Code',
    )
    error_description = fields.Char(
        string='Error Description',
    )
    test_mode = fields.Boolean(
        string='Test Mode',
        default=False,
    )
    res_model = fields.Char(
        string='Related Model',
    )
    res_id = fields.Integer(
        string='Related Record ID',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    @api.depends('phone_number', 'create_date')
    def _compute_name(self):
        for record in self:
            date_str = record.create_date.strftime('%Y-%m-%d %H:%M') if record.create_date else ''
            record.name = 'SMS to %s at %s' % (record.phone_number or '', date_str)

    def action_view_related_record(self):
        """Open the related record (sale.order, stock.picking, etc.)."""
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def _cron_cleanup_old_logs(self):
        """Delete logs older than the configured retention days."""
        ICP = self.env['ir.config_parameter'].sudo()
        retention_days = int(ICP.get_param('kwtsms.log_retention_days', '90'))
        if retention_days <= 0:
            return

        cutoff = fields.Datetime.now() - timedelta(days=retention_days)
        old_logs = self.search([('create_date', '<', cutoff)])
        count = len(old_logs)
        if count:
            old_logs.unlink()
            _logger.info('Cleaned up %d kwtSMS log entries older than %d days',
                         count, retention_days)
