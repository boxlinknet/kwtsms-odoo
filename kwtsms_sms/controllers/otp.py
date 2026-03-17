"""OTP verification controller for SMS-based 2FA."""

import logging
from datetime import timedelta

from odoo import http, fields, _
from odoo.http import request

from odoo.addons.kwtsms_sms.tools.otp_service import (
    generate_otp, verify_otp, generate_device_token, hash_user_agent,
    hash_device_token,
)

_logger = logging.getLogger(__name__)


class KwtSmsOtpController(http.Controller):
    """Handles OTP verification for SMS-based MFA."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_otp_config(self):
        """Read OTP configuration from system parameters."""
        ICP = request.env['ir.config_parameter'].sudo()
        return {
            'length': int(ICP.get_param('kwtsms.otp_length', '6')),
            'expiry_minutes': int(ICP.get_param('kwtsms.otp_expiry_minutes', '5')),
            'max_attempts': int(ICP.get_param('kwtsms.otp_max_attempts', '3')),
            'lockout_minutes': int(ICP.get_param('kwtsms.otp_lockout_minutes', '15')),
            'cooldown_seconds': int(ICP.get_param('kwtsms.otp_cooldown_seconds', '60')),
            'ip_daily_limit': int(ICP.get_param('kwtsms.otp_ip_daily_limit', '10')),
            'remember_days': int(ICP.get_param('kwtsms.otp_remember_days', '30')),
        }

    def _get_ip(self):
        """Get client IP address (handles proxy mode)."""
        return request.httprequest.environ.get(
            'HTTP_X_FORWARDED_FOR', request.httprequest.remote_addr,
        ).split(',')[0].strip()

    def _get_user_agent(self):
        """Get client User-Agent string."""
        return request.httprequest.headers.get('User-Agent', '')

    def _mask_phone(self, phone):
        """Mask phone number for display (show last 4 digits)."""
        if not phone or len(phone) < 4:
            return '****'
        return '****' + phone[-4:]

    def _log_otp(self, action, phone=None, user_id=None, otp_type=None,
                 error_reason=None):
        """Log an OTP event to the audit trail."""
        try:
            request.env['kwtsms.otp.log'].sudo().create({
                'phone': phone or '',
                'ip_address': self._get_ip(),
                'user_id': user_id,
                'otp_type': otp_type,
                'action': action,
                'error_reason': error_reason or '',
                'user_agent': self._get_user_agent(),
            })
        except Exception as e:
            _logger.error('kwtSMS OTP: Failed to log event: %s', e)

    def _resolve_phone(self, user):
        """Get normalized phone for a user, falling back to prepare_phone."""
        phone = user.partner_id.kwtsms_phone_normalized
        if not phone:
            raw = user.partner_id.phone or ''
            if raw:
                from odoo.addons.kwtsms_sms.tools.phone_utils import prepare_phone
                ICP = request.env['ir.config_parameter'].sudo()
                default_cc = ICP.get_param('kwtsms.default_country_code', '965')
                phone, _ = prepare_phone(raw, default_cc)
        return phone or ''

    def _determine_otp_type(self, user, passwordless=False):
        """Determine OTP type based on user and flow."""
        if passwordless:
            return 'passwordless'
        if user.has_group('base.group_user'):
            return 'backend_login'
        return 'portal_login'

    def _check_rate_limits(self, phone, config):
        """Check rate limits. Returns error string or None if OK."""
        Token = request.env['kwtsms.otp.token'].sudo()
        ip = self._get_ip()

        # Per-phone cooldown
        cooldown_cutoff = fields.Datetime.now() - timedelta(
            seconds=config['cooldown_seconds'],
        )
        recent = Token.search([
            ('phone', '=', phone),
            ('state', '=', 'pending'),
            ('create_date', '>', cooldown_cutoff),
        ], limit=1)
        if recent:
            return _('Please wait before requesting another code.')

        # Per-IP daily limit
        today_start = fields.Datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        ip_count = Token.search_count([
            ('ip_address', '=', ip),
            ('create_date', '>=', today_start),
        ])
        if ip_count >= config['ip_daily_limit']:
            return _('Too many requests. Try again tomorrow.')

        return None

    def _create_and_send_otp(self, phone, otp_type, user_id, config):
        """Generate OTP, store token, send SMS. Returns error or None."""
        Token = request.env['kwtsms.otp.token'].sudo()

        # Invalidate any existing pending tokens for this phone + type
        existing = Token.search([
            ('phone', '=', phone),
            ('otp_type', '=', otp_type),
            ('state', '=', 'pending'),
        ])
        if existing:
            existing.write({'state': 'expired'})

        # Generate OTP
        plain_code, hashed_code = generate_otp(config['length'])

        # Create token
        Token.create({
            'phone': phone,
            'otp_hash': hashed_code,
            'otp_type': otp_type,
            'user_id': user_id,
            'ip_address': self._get_ip(),
            'expires_at': fields.Datetime.now() + timedelta(
                minutes=config['expiry_minutes'],
            ),
        })

        # Send SMS
        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        api = KwtSmsApi(request.env)
        company_name = request.env.company.name or ''
        message = '%s: Your verification code is %s. Valid for %d minutes.' % (
            company_name, plain_code, config['expiry_minutes'],
        )
        result = api.send(
            phone, message, recipient_type='otp',
        )
        if result.get('result') != 'OK':
            _logger.error(
                'kwtSMS OTP: SMS send failed: %s', result.get('description'),
            )
            return _('Could not send verification code. Please try again.')

        self._log_otp('request', phone=phone, user_id=user_id, otp_type=otp_type)
        return None

    def _check_device_trust(self, user_id, config):
        """Check if this device is trusted (remember-me cookie).

        Returns True if trusted and OTP should be skipped.
        """
        if config['remember_days'] <= 0:
            return False

        cookie = request.httprequest.cookies.get('kwtsms_otp_device')
        if not cookie:
            return False

        device_hash = hash_device_token(cookie)
        ua_hash = hash_user_agent(self._get_user_agent())

        Device = request.env['kwtsms.otp.device'].sudo()
        trust = Device.search([
            ('device_hash', '=', device_hash),
            ('user_id', '=', user_id),
            ('expires_at', '>', fields.Datetime.now()),
            ('user_agent_hash', '=', ua_hash),
        ], limit=1)

        if trust:
            self._log_otp('device_skip', user_id=user_id)
            return True
        return False

    def _render_otp_page(self, values):
        """Render the OTP verify template with defaults."""
        defaults = {
            'error': None,
            'message': None,
            'phone_masked': '',
            'can_resend': False,
            'cooldown_remaining': 0,
        }
        defaults.update(values)
        return request.render('kwtsms_sms.kwtsms_otp_verify_template', defaults)

    def _finalize_login(self, uid, config, phone=None, otp_type=None):
        """Finalize session after successful OTP and set device cookie."""
        # Finalize session (Odoo native MFA completion)
        # finalize() pops pre_uid/pre_login and sets uid on session
        request.session.finalize(request.env)

        # Build redirect response
        response = request.redirect('/web')

        # Set device trust cookie if enabled
        if config['remember_days'] > 0:
            plain_token, hashed_token = generate_device_token()
            ua_hash = hash_user_agent(self._get_user_agent())
            request.env['kwtsms.otp.device'].sudo().create({
                'user_id': uid,
                'device_hash': hashed_token,
                'user_agent_hash': ua_hash,
                'expires_at': fields.Datetime.now() + timedelta(
                    days=config['remember_days'],
                ),
                'ip_address': self._get_ip(),
            })
            self._log_otp(
                'device_trusted', user_id=uid, otp_type=otp_type,
            )
            max_age = config['remember_days'] * 86400
            response.set_cookie(
                'kwtsms_otp_device', plain_token,
                max_age=max_age, httponly=True,
                secure=request.httprequest.scheme == 'https',
                samesite='Lax',
            )

        return response

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @http.route('/kwtsms/otp/verify', type='http', auth='public',
                methods=['GET', 'POST'], sitemap=False, csrf=True)
    def otp_verify(self, **kwargs):
        """Handle OTP verification page (GET: show form, POST: verify)."""
        # Get pre_uid from session (set by Odoo MFA framework)
        pre_uid = request.session.get('pre_uid')
        passwordless_uid = request.session.get('kwtsms_otp_passwordless_uid')
        uid = pre_uid or passwordless_uid

        if not uid:
            return request.redirect('/web/login')

        config = self._get_otp_config()
        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists():
            return request.redirect('/web/login')

        is_passwordless = bool(passwordless_uid)
        otp_type = self._determine_otp_type(user, passwordless=is_passwordless)
        phone = self._resolve_phone(user)

        if request.httprequest.method == 'GET':
            return self._handle_get(uid, user, phone, otp_type, config)

        # POST: verify submitted code
        return self._handle_post(uid, user, phone, otp_type, config, kwargs)

    def _handle_get(self, uid, user, phone, otp_type, config):
        """Handle GET request: check trust, send OTP, show form."""
        # Check device trust first
        if self._check_device_trust(uid, config):
            return self._finalize_login(uid, config)

        if not phone:
            self._log_otp(
                'invalid_phone', user_id=uid, otp_type=otp_type,
                error_reason='no phone on partner',
            )
            return self._render_otp_page({
                'error': _(
                    'No phone number on your account. '
                    'Contact your administrator.'
                ),
            })

        # Check rate limits
        rate_error = self._check_rate_limits(phone, config)
        if rate_error:
            return self._render_otp_page({
                'error': rate_error,
                'phone_masked': self._mask_phone(phone),
                'cooldown_remaining': config['cooldown_seconds'],
            })

        # Generate and send OTP
        send_error = self._create_and_send_otp(phone, otp_type, uid, config)
        if send_error:
            return self._render_otp_page({
                'error': send_error,
                'phone_masked': self._mask_phone(phone),
                'can_resend': True,
            })

        return self._render_otp_page({
            'message': _('Verification code sent.'),
            'phone_masked': self._mask_phone(phone),
            'cooldown_remaining': config['cooldown_seconds'],
        })

    def _handle_post(self, uid, user, phone, otp_type, config, kwargs):
        """Handle POST request: verify OTP code."""
        otp_code = kwargs.get('otp_code', '').strip()
        if not otp_code:
            return self._render_otp_page({
                'error': _('Please enter the verification code.'),
                'phone_masked': self._mask_phone(phone),
                'can_resend': True,
            })

        Token = request.env['kwtsms.otp.token'].sudo()
        token = Token.search([
            ('phone', '=', phone),
            ('otp_type', '=', otp_type),
            ('state', '=', 'pending'),
        ], order='create_date desc', limit=1)

        if not token:
            return self._render_otp_page({
                'error': _('Code expired. Please request a new one.'),
                'phone_masked': self._mask_phone(phone),
                'can_resend': True,
            })

        # Check expiry
        if token.expires_at and token.expires_at < fields.Datetime.now():
            token.write({'state': 'expired'})
            self._log_otp(
                'expired', phone=phone, user_id=uid, otp_type=otp_type,
            )
            return self._render_otp_page({
                'error': _('Code expired. Please request a new one.'),
                'phone_masked': self._mask_phone(phone),
                'can_resend': True,
            })

        # Check lockout
        if token.attempt_count >= config['max_attempts']:
            lockout_until = token.create_date + timedelta(
                minutes=config['lockout_minutes'],
            )
            if fields.Datetime.now() < lockout_until:
                token.write({'state': 'locked'})
                self._log_otp(
                    'locked_out', phone=phone, user_id=uid,
                    otp_type=otp_type,
                )
                return self._render_otp_page({
                    'error': _(
                        'Too many attempts. Try again in %d minutes.'
                    ) % config['lockout_minutes'],
                    'phone_masked': self._mask_phone(phone),
                })
            else:
                # Lockout expired, token is permanently invalid
                token.write({'state': 'locked'})
                self._log_otp(
                    'expired', phone=phone, user_id=uid,
                    otp_type=otp_type,
                )
                return self._render_otp_page({
                    'error': _('Code expired. Please request a new one.'),
                    'phone_masked': self._mask_phone(phone),
                    'can_resend': True,
                })

        # Verify OTP
        if verify_otp(otp_code, token.otp_hash):
            token.write({'state': 'verified'})
            self._log_otp(
                'verify_ok', phone=phone, user_id=uid, otp_type=otp_type,
            )
            return self._finalize_login(
                uid, config, phone=phone, otp_type=otp_type,
            )

        # Wrong code
        token.write({'attempt_count': token.attempt_count + 1})
        remaining = config['max_attempts'] - token.attempt_count - 1
        self._log_otp(
            'verify_failed', phone=phone, user_id=uid, otp_type=otp_type,
        )
        return self._render_otp_page({
            'error': _(
                'Invalid code. %d attempt(s) remaining.'
            ) % max(remaining, 0),
            'phone_masked': self._mask_phone(phone),
            'can_resend': True,
        })

    @http.route('/kwtsms/otp/resend', type='http', auth='public',
                methods=['POST'], sitemap=False, csrf=True)
    def otp_resend(self, **kwargs):
        """Resend OTP code (invalidates previous, respects cooldown)."""
        pre_uid = request.session.get('pre_uid')
        passwordless_uid = request.session.get('kwtsms_otp_passwordless_uid')
        uid = pre_uid or passwordless_uid

        if not uid:
            return request.redirect('/web/login')

        config = self._get_otp_config()
        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists():
            return request.redirect('/web/login')

        is_passwordless = bool(passwordless_uid)
        otp_type = self._determine_otp_type(user, passwordless=is_passwordless)
        phone = self._resolve_phone(user)

        if not phone:
            return request.redirect('/kwtsms/otp/verify')

        # Check rate limits
        rate_error = self._check_rate_limits(phone, config)
        if rate_error:
            self._log_otp(
                'resend', phone=phone, user_id=uid, otp_type=otp_type,
                error_reason='cooldown',
            )
            return request.redirect('/kwtsms/otp/verify')

        # Generate and send new OTP (invalidates previous)
        self._create_and_send_otp(phone, otp_type, uid, config)
        self._log_otp('resend', phone=phone, user_id=uid, otp_type=otp_type)
        return request.redirect('/kwtsms/otp/verify')
