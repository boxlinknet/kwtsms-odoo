"""SMS notifications for CRM lead events."""

import logging

from odoo import models, api

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    """Hook into crm.lead for admin SMS notifications."""

    _inherit = ['crm.lead', 'kwtsms.admin.notification.mixin']
    _name = 'crm.lead'

    @api.model_create_multi
    def create(self, vals_list):
        """Send admin SMS when a new lead is created."""
        leads = super().create(vals_list)
        for lead in leads:
            try:
                lead._kwtsms_send_admin_notification(
                    'admin_new_lead',
                    'kwtsms.auto_admin_new_lead',
                    'kwtsms.admin_phone_crm',
                    {
                        'company_name': (
                            lead.company_id.name
                            if lead.company_id
                            else self.env.company.name or ''
                        ),
                        'lead_name': lead.name or '',
                        'salesperson': lead.user_id.name or '',
                        'contact_name': (
                            lead.partner_id.name
                            if lead.partner_id
                            else lead.contact_name or ''
                        ),
                    },
                )
            except Exception as e:
                _logger.error(
                    'kwtSMS: Admin new lead SMS failed for %s: %s',
                    lead.name, e,
                )
        return leads

    def write(self, vals):
        """Send admin SMS when lead stage changes."""
        old_stages = {}
        if 'stage_id' in vals:
            old_stages = {lead.id: lead.stage_id.name for lead in self}

        result = super().write(vals)

        if 'stage_id' in vals:
            for lead in self:
                old_stage = old_stages.get(lead.id, '')
                if old_stage and old_stage != lead.stage_id.name:
                    try:
                        lead._kwtsms_send_admin_notification(
                            'admin_lead_stage_changed',
                            'kwtsms.auto_admin_lead_stage_changed',
                            'kwtsms.admin_phone_crm',
                            {
                                'company_name': (
                                    lead.company_id.name
                                    if lead.company_id
                                    else self.env.company.name or ''
                                ),
                                'lead_name': lead.name or '',
                                'old_stage': old_stage,
                                'new_stage': lead.stage_id.name or '',
                            },
                        )
                    except Exception as e:
                        _logger.error(
                            'kwtSMS: Admin lead stage SMS failed for %s: %s',
                            lead.name, e,
                        )

        return result
