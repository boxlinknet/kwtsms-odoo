"""OTP verification controller for SMS-based 2FA and signup."""

import json
import logging
import secrets
from datetime import datetime, timedelta

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
        # Check for signup flow (no user_id yet)
        signup_pending = request.session.get('kwtsms_otp_signup_pending')
        if signup_pending:
            return self._otp_verify_signup(kwargs)

        # Check for password reset flow
        reset_pending = request.session.get('kwtsms_otp_reset_pending')
        if reset_pending:
            return self._otp_verify_reset(kwargs)

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

    def _otp_verify_signup(self, kwargs):
        """Handle OTP verify for signup flow (no user exists yet)."""
        phone = request.session.get('kwtsms_otp_signup_phone', '')
        if not phone:
            return request.redirect('/web/signup?kwtsms_error=invalid')

        config = self._get_otp_config()

        if request.httprequest.method == 'GET':
            return self._render_otp_page({
                'message': _('Verification code sent.'),
                'phone_masked': self._mask_phone(phone),
                'cooldown_remaining': config['cooldown_seconds'],
            })

        # POST: verify code
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
            ('otp_type', '=', 'signup'),
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
                'expired', phone=phone, otp_type='signup',
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
                    'locked_out', phone=phone, otp_type='signup',
                )
                return self._render_otp_page({
                    'error': _(
                        'Too many attempts. Try again in %d minutes.'
                    ) % config['lockout_minutes'],
                    'phone_masked': self._mask_phone(phone),
                })
            else:
                token.write({'state': 'locked'})
                self._log_otp(
                    'expired', phone=phone, otp_type='signup',
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
                'verify_ok', phone=phone, otp_type='signup',
            )

            # Store proof in session
            proof = json.dumps({
                'phone': phone,
                'verified_at': datetime.utcnow().isoformat(),
                'nonce': secrets.token_hex(16),
            })
            request.session['kwtsms_otp_verified_phone'] = proof

            # Clean up signup pending state
            request.session.pop('kwtsms_otp_signup_pending', None)
            request.session.pop('kwtsms_otp_signup_phone', None)

            # Redirect back to signup to complete form submission
            return request.redirect('/web/signup')

        # Wrong code
        token.write({'attempt_count': token.attempt_count + 1})
        remaining = config['max_attempts'] - token.attempt_count - 1
        self._log_otp(
            'verify_failed', phone=phone, otp_type='signup',
        )
        return self._render_otp_page({
            'error': _(
                'Invalid code. %d attempt(s) remaining.'
            ) % max(remaining, 0),
            'phone_masked': self._mask_phone(phone),
            'can_resend': True,
        })

    def _otp_verify_reset(self, kwargs):
        """Handle OTP verify for password reset flow."""
        phone = request.session.get('kwtsms_otp_reset_phone', '')
        uid = request.session.get('kwtsms_otp_reset_uid')
        if not phone or not uid:
            return request.redirect('/web/login')

        config = self._get_otp_config()

        if request.httprequest.method == 'GET':
            return self._render_otp_page({
                'message': _('Verification code sent.'),
                'phone_masked': self._mask_phone(phone),
                'cooldown_remaining': config['cooldown_seconds'],
            })

        # POST: verify code
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
            ('otp_type', '=', 'password_reset'),
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
                'expired', phone=phone, user_id=uid,
                otp_type='password_reset',
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
                    otp_type='password_reset',
                )
                return self._render_otp_page({
                    'error': _(
                        'Too many attempts. Try again in %d minutes.'
                    ) % config['lockout_minutes'],
                    'phone_masked': self._mask_phone(phone),
                })
            else:
                token.write({'state': 'locked'})
                self._log_otp(
                    'expired', phone=phone, user_id=uid,
                    otp_type='password_reset',
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
                'verify_ok', phone=phone, user_id=uid,
                otp_type='password_reset',
            )

            # Store proof in session for password change
            proof = json.dumps({
                'user_id': uid,
                'verified_at': datetime.utcnow().isoformat(),
                'nonce': secrets.token_hex(16),
            })
            request.session['kwtsms_otp_reset_verified'] = proof

            # Clean up pending state
            request.session.pop('kwtsms_otp_reset_pending', None)
            request.session.pop('kwtsms_otp_reset_phone', None)

            # Redirect to password change form
            return request.redirect('/kwtsms/otp/new-password')

        # Wrong code
        token.write({'attempt_count': token.attempt_count + 1})
        remaining = config['max_attempts'] - token.attempt_count - 1
        self._log_otp(
            'verify_failed', phone=phone, user_id=uid,
            otp_type='password_reset',
        )
        return self._render_otp_page({
            'error': _(
                'Invalid code. %d attempt(s) remaining.'
            ) % max(remaining, 0),
            'phone_masked': self._mask_phone(phone),
            'can_resend': True,
        })

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

    @http.route('/kwtsms/otp/phone-login', type='http', auth='public',
                methods=['POST'], sitemap=False, csrf=True)
    def otp_phone_login(self, **kwargs):
        """Handle passwordless phone login: lookup user by phone, send OTP."""
        ICP = request.env['ir.config_parameter'].sudo()
        if ICP.get_param('kwtsms.otp_passwordless', 'False') != 'True':
            return request.redirect('/web/login')
        if ICP.get_param('kwtsms.enabled', 'False') != 'True':
            return request.redirect('/web/login')

        phone_input = kwargs.get('phone', '').strip()
        country_code = kwargs.get('country_code', '').strip()
        if not country_code:
            country_code = ICP.get_param('kwtsms.default_country_code', '965')

        config = self._get_otp_config()

        # Validate phone format
        from odoo.addons.kwtsms_sms.tools.phone_utils import prepare_phone
        normalized, error = prepare_phone(phone_input, country_code)
        if error:
            # Clear format error - not enumeration risk
            return request.redirect('/web/login?kwtsms_phone_error=invalid')

        # Look up user by normalized phone
        Partner = request.env['res.partner'].sudo()
        partners = Partner.search([
            ('kwtsms_phone_normalized', '=', normalized),
        ])
        users = request.env['res.users'].sudo().search([
            ('partner_id', 'in', partners.ids),
            ('active', '=', True),
        ])

        if len(users) > 1:
            self._log_otp(
                'ambiguous_phone', phone=normalized, otp_type='passwordless',
                error_reason='multiple users match',
            )
            # Generic message (anti-enumeration)
            return request.redirect('/web/login?kwtsms_phone_sent=1')

        if not users:
            self._log_otp(
                'user_not_found', phone=normalized, otp_type='passwordless',
            )
            # Generic message (anti-enumeration)
            return request.redirect('/web/login?kwtsms_phone_sent=1')

        user = users[0]

        # Check rate limits
        rate_error = self._check_rate_limits(normalized, config)
        if rate_error:
            self._log_otp(
                'request', phone=normalized, user_id=user.id,
                otp_type='passwordless', error_reason='rate limited',
            )
            return request.redirect('/web/login?kwtsms_phone_sent=1')

        # Generate and send OTP
        send_error = self._create_and_send_otp(
            normalized, 'passwordless', user.id, config,
        )
        if send_error:
            return request.redirect('/web/login?kwtsms_phone_error=send_failed')

        # Store user ID in session for verify flow
        request.session['kwtsms_otp_passwordless_uid'] = user.id
        return request.redirect('/kwtsms/otp/verify')

    @http.route('/kwtsms/otp/resend', type='http', auth='public',
                methods=['POST'], sitemap=False, csrf=True)
    def otp_resend(self, **kwargs):
        """Resend OTP code (invalidates previous, respects cooldown)."""
        # Handle signup flow resend (no user exists yet)
        signup_pending = request.session.get('kwtsms_otp_signup_pending')
        if signup_pending:
            return self._otp_resend_signup()

        # Handle password reset flow resend
        reset_pending = request.session.get('kwtsms_otp_reset_pending')
        if reset_pending:
            return self._otp_resend_reset()

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

    def _otp_resend_signup(self):
        """Resend OTP for signup flow."""
        phone = request.session.get('kwtsms_otp_signup_phone', '')
        if not phone:
            return request.redirect('/web/signup')

        config = self._get_otp_config()

        # Check rate limits
        rate_error = self._check_rate_limits(phone, config)
        if rate_error:
            self._log_otp(
                'resend', phone=phone, otp_type='signup',
                error_reason='cooldown',
            )
            return request.redirect('/kwtsms/otp/verify')

        # Generate and send new OTP (invalidates previous)
        self._create_and_send_otp(phone, 'signup', None, config)
        self._log_otp('resend', phone=phone, otp_type='signup')
        return request.redirect('/kwtsms/otp/verify')


    def _otp_resend_reset(self):
        """Resend OTP for password reset flow."""
        phone = request.session.get('kwtsms_otp_reset_phone', '')
        uid = request.session.get('kwtsms_otp_reset_uid')
        if not phone or not uid:
            return request.redirect('/web/login')

        config = self._get_otp_config()

        # Check rate limits
        rate_error = self._check_rate_limits(phone, config)
        if rate_error:
            self._log_otp(
                'resend', phone=phone, user_id=uid,
                otp_type='password_reset', error_reason='cooldown',
            )
            return request.redirect('/kwtsms/otp/verify')

        # Generate and send new OTP (invalidates previous)
        self._create_and_send_otp(phone, 'password_reset', uid, config)
        self._log_otp(
            'resend', phone=phone, user_id=uid,
            otp_type='password_reset',
        )
        return request.redirect('/kwtsms/otp/verify')


class KwtSmsResetController(http.Controller):
    """Handle phone-based password reset via OTP."""

    @http.route('/kwtsms/otp/reset-password', type='http', auth='public',
                methods=['POST'], sitemap=False, csrf=True)
    def otp_reset_password(self, **kwargs):
        """Handle phone-based password reset: lookup user, send OTP."""
        ICP = request.env['ir.config_parameter'].sudo()
        if ICP.get_param('kwtsms.otp_password_reset', 'False') != 'True':
            return request.redirect('/web/login')
        if ICP.get_param('kwtsms.enabled', 'False') != 'True':
            return request.redirect('/web/login')

        phone_input = kwargs.get('phone', '').strip()
        country_code = kwargs.get('country_code', '').strip()
        if not country_code:
            country_code = ICP.get_param('kwtsms.default_country_code', '965')

        # Validate phone format
        from odoo.addons.kwtsms_sms.tools.phone_utils import prepare_phone
        normalized, error = prepare_phone(phone_input, country_code)
        if error:
            return request.redirect(
                '/web/login?kwtsms_reset_error=invalid_phone',
            )

        otp_ctrl = KwtSmsOtpController()
        config = otp_ctrl._get_otp_config()

        # Look up user by phone (anti-enumeration: generic message regardless)
        Partner = request.env['res.partner'].sudo()
        partners = Partner.search([
            ('kwtsms_phone_normalized', '=', normalized),
        ])
        users = request.env['res.users'].sudo().search([
            ('partner_id', 'in', partners.ids),
            ('active', '=', True),
        ])

        if len(users) != 1:
            # Log but show generic message
            action = 'ambiguous_phone' if len(users) > 1 else 'user_not_found'
            otp_ctrl._log_otp(
                action, phone=normalized, otp_type='password_reset',
            )
            return request.redirect('/web/login?kwtsms_reset_sent=1')

        user = users[0]

        # Rate limits
        rate_error = otp_ctrl._check_rate_limits(normalized, config)
        if rate_error:
            # Show generic message (anti-enumeration)
            return request.redirect('/web/login?kwtsms_reset_sent=1')

        # Generate and send OTP
        send_error = otp_ctrl._create_and_send_otp(
            normalized, 'password_reset', user.id, config,
        )
        if send_error:
            return request.redirect(
                '/web/login?kwtsms_reset_error=send_failed',
            )

        # Store in session for verify flow
        request.session['kwtsms_otp_reset_uid'] = user.id
        request.session['kwtsms_otp_reset_phone'] = normalized
        request.session['kwtsms_otp_reset_pending'] = True
        return request.redirect('/kwtsms/otp/verify')

    @http.route('/kwtsms/otp/new-password', type='http', auth='public',
                methods=['GET', 'POST'], sitemap=False, csrf=True)
    def otp_new_password(self, **kwargs):
        """Show and handle the new password form after OTP verification."""
        proof_raw = request.session.get('kwtsms_otp_reset_verified')
        if not proof_raw:
            return request.redirect('/web/login')

        # Validate proof freshness (10 minute window)
        try:
            proof = json.loads(proof_raw) if isinstance(
                proof_raw, str,
            ) else proof_raw
            verified_at = datetime.fromisoformat(proof.get('verified_at', ''))
            if (datetime.utcnow() - verified_at).total_seconds() > 600:
                request.session.pop('kwtsms_otp_reset_verified', None)
                return request.redirect('/web/login?kwtsms_reset_error=expired')
        except (json.JSONDecodeError, ValueError, TypeError):
            request.session.pop('kwtsms_otp_reset_verified', None)
            return request.redirect('/web/login')

        uid = proof.get('user_id')
        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists():
            request.session.pop('kwtsms_otp_reset_verified', None)
            return request.redirect('/web/login')

        if request.httprequest.method == 'GET':
            return request.render(
                'kwtsms_sms.kwtsms_otp_new_password_template', {
                    'error': None,
                },
            )

        # POST: set new password
        password = kwargs.get('password', '')
        confirm_password = kwargs.get('confirm_password', '')

        if not password:
            return request.render(
                'kwtsms_sms.kwtsms_otp_new_password_template', {
                    'error': _('Please enter a new password.'),
                },
            )

        if len(password) < 8:
            return request.render(
                'kwtsms_sms.kwtsms_otp_new_password_template', {
                    'error': _('Password must be at least 8 characters.'),
                },
            )

        if password != confirm_password:
            return request.render(
                'kwtsms_sms.kwtsms_otp_new_password_template', {
                    'error': _('Passwords do not match.'),
                },
            )

        # Set the new password
        try:
            user.write({'password': password})
        except Exception as e:
            _logger.error('kwtSMS OTP: Password reset failed: %s', e)
            return request.render(
                'kwtsms_sms.kwtsms_otp_new_password_template', {
                    'error': _(
                        'Could not set password. Please try again.',
                    ),
                },
            )

        # Log success and clean up session
        otp_ctrl = KwtSmsOtpController()
        otp_ctrl._log_otp(
            'password_changed', user_id=uid,
            otp_type='password_reset',
        )
        request.session.pop('kwtsms_otp_reset_verified', None)
        request.session.pop('kwtsms_otp_reset_uid', None)

        return request.redirect('/web/login?kwtsms_reset_success=1')


class KwtSmsSignupController(http.Controller):
    """Override signup to add OTP phone verification before account creation.

    Inherits from AuthSignupHome via route override. When OTP signup is
    enabled, the POST flow is: collect phone -> send OTP -> verify -> store
    proof in session -> redirect back to signup -> super proceeds.
    """

    @http.route('/web/signup', type='http', auth='public', website=True,
                sitemap=False, csrf=True)
    def web_auth_signup(self, *args, **kwargs):
        """Intercept signup to require OTP phone verification."""
        from odoo.addons.auth_signup.controllers.main import AuthSignupHome
        _signup_home = AuthSignupHome()

        ICP = request.env['ir.config_parameter'].sudo()
        otp_enabled = (
            ICP.get_param('kwtsms.otp_signup', 'False') == 'True'
            and ICP.get_param('kwtsms.enabled', 'False') == 'True'
        )

        if not otp_enabled or request.httprequest.method == 'GET':
            # OTP disabled or GET request: use standard signup
            return _signup_home.web_auth_signup(*args, **kwargs)

        # POST: check if phone is already verified via OTP proof
        verified = request.session.get('kwtsms_otp_verified_phone')
        if verified:
            # Validate proof freshness (10 minute window)
            try:
                proof = json.loads(verified) if isinstance(verified, str) else verified
                verified_at = datetime.fromisoformat(proof.get('verified_at', ''))
                if (datetime.utcnow() - verified_at).total_seconds() > 600:
                    # Proof expired
                    request.session.pop('kwtsms_otp_verified_phone', None)
                    return request.redirect('/web/signup?kwtsms_error=expired')
            except (json.JSONDecodeError, ValueError, TypeError):
                request.session.pop('kwtsms_otp_verified_phone', None)
                return request.redirect('/web/signup?kwtsms_error=invalid')

            # Proof valid: proceed with standard signup
            result = _signup_home.web_auth_signup(*args, **kwargs)
            # Clear proof after use
            request.session.pop('kwtsms_otp_verified_phone', None)
            request.session.pop('kwtsms_otp_signup_data', None)
            return result

        # No proof yet: extract phone from form, send OTP
        phone = kwargs.get('phone', '').strip()
        if not phone:
            return request.redirect('/web/signup?kwtsms_error=no_phone')

        from odoo.addons.kwtsms_sms.tools.phone_utils import prepare_phone
        default_cc = ICP.get_param('kwtsms.default_country_code', '965')
        normalized, error = prepare_phone(phone, default_cc)
        if error:
            return request.redirect('/web/signup?kwtsms_error=invalid_phone')

        otp_ctrl = KwtSmsOtpController()
        config = otp_ctrl._get_otp_config()

        # Check rate limits
        rate_error = otp_ctrl._check_rate_limits(normalized, config)
        if rate_error:
            return request.redirect('/web/signup?kwtsms_error=rate_limit')

        # Store signup form data in session for after OTP verify
        request.session['kwtsms_otp_signup_data'] = kwargs
        request.session['kwtsms_otp_signup_phone'] = normalized

        # Generate and send OTP
        send_error = otp_ctrl._create_and_send_otp(
            normalized, 'signup', None, config,
        )
        if send_error:
            return request.redirect('/web/signup?kwtsms_error=send_failed')

        # Set session for OTP verify page
        request.session['kwtsms_otp_signup_pending'] = True
        return request.redirect('/kwtsms/otp/verify')
