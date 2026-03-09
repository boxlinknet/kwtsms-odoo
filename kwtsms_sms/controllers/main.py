"""kwtSMS Controllers for API endpoints."""

import logging

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class KwtSmsController(http.Controller):
    """API endpoints for kwtSMS gateway operations."""

    @http.route('/kwtsms/balance', type='jsonrpc', auth='user')
    def get_balance(self, **kwargs):
        """Get current SMS balance.

        Returns:
            dict: Balance information.
        """
        if not request.env.user.has_group('base.group_system'):
            return {'success': False, 'error': _('Access denied.')}

        config = request.env['kwtsms.gateway.config'].sudo()._get_or_create()
        return {
            'success': True,
            'data': {
                'available': config.balance_available,
                'purchased': config.balance_purchased,
                'status': config.api_status,
                'last_verified': str(config.last_verified) if config.last_verified else None,
            },
        }
