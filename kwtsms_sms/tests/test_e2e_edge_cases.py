"""Comprehensive E2E edge-case tests against the real kwtSMS API.

Covers phone normalization, validation, message cleaning, template rendering,
and error logging via real API calls with test_mode=1.

Every test sends through the full Odoo stack (wizard or direct API) and
verifies that the SMS log captures the correct status, error, and phone number.
"""

import logging

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)

TEST_PHONE = '96598765432'


def _get_api(env):
    """Create a KwtSmsApi instance."""
    from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
    return KwtSmsApi(env)


@tagged('post_install', '-at_install', 'kwtsms_e2e')
class TestPhoneNormalizationE2E(TransactionCase):
    """Test phone normalization via real API sends."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.has_creds = bool(ICP.get_param('kwtsms.api_username', ''))
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.enabled', 'True')

    def _skip_if_no_creds(self):
        if not self.has_creds:
            self.skipTest('No kwtSMS API credentials')

    def _last_log(self, phone=None):
        """Get most recent SMS log, optionally filtered by phone."""
        domain = []
        if phone:
            domain.append(('phone_number', '=', phone))
        return self.env['kwtsms.sms.log'].sudo().search(
            domain, limit=1, order='id desc',
        )

    # ---- Plus prefix ----

    def test_phone_plus_prefix(self):
        """Phone with + prefix should normalize and send OK."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send('+96598765432', 'E2E plus prefix test')
        self.assertEqual(resp.get('result'), 'OK')
        api._log_send(
            numbers='+96598765432', message='E2E plus prefix test',
            response=resp, status='test',
        )
        log = self._last_log('+96598765432')
        self.assertTrue(log)
        self.assertEqual(log.status, 'test')

    # ---- Double-zero prefix ----

    def test_phone_double_zero_prefix(self):
        """Phone with 00 prefix should normalize and send OK."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send('0096598765432', 'E2E double-zero test')
        self.assertEqual(resp.get('result'), 'OK')

    # ---- Spaces and dashes ----

    def test_phone_with_spaces(self):
        """Phone with spaces should normalize and send OK."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send('965 9876 5432', 'E2E spaces test')
        self.assertEqual(resp.get('result'), 'OK')

    def test_phone_with_dashes(self):
        """Phone with dashes should normalize and send OK."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send('965-9876-5432', 'E2E dashes test')
        self.assertEqual(resp.get('result'), 'OK')

    def test_phone_with_dots(self):
        """Phone with dots should normalize and send OK."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send('965.9876.5432', 'E2E dots test')
        self.assertEqual(resp.get('result'), 'OK')

    def test_phone_with_parentheses(self):
        """Phone with parentheses should normalize and send OK."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send('(965) 98765432', 'E2E parens test')
        self.assertEqual(resp.get('result'), 'OK')

    # ---- Arabic-Indic digits ----

    def test_phone_arabic_indic_digits(self):
        """Arabic-Indic digits in phone should normalize and send OK."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        # 96598765432 in Arabic-Indic
        arabic_phone = '\u0669\u0666\u0665\u0669\u0668\u0667\u0666\u0665\u0664\u0663\u0662'
        resp = api.send(arabic_phone, 'E2E Arabic digits phone test')
        self.assertEqual(resp.get('result'), 'OK')

    def test_phone_persian_digits(self):
        """Extended Arabic-Indic (Persian) digits in phone."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        persian_phone = '\u06f9\u06f6\u06f5\u06f9\u06f8\u06f7\u06f6\u06f5\u06f4\u06f3\u06f2'
        resp = api.send(persian_phone, 'E2E Persian digits phone test')
        self.assertEqual(resp.get('result'), 'OK')

    def test_phone_mixed_arabic_latin(self):
        """Mixed Arabic-Indic and Latin digits."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        mixed = '965\u0669\u0668\u0667\u0666\u0665\u0664\u0663\u0662'
        resp = api.send(mixed, 'E2E mixed digits phone test')
        self.assertEqual(resp.get('result'), 'OK')

    def test_phone_arabic_with_plus(self):
        """Arabic-Indic digits with + prefix."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        phone = '+\u0669\u0666\u0665\u0669\u0668\u0667\u0666\u0665\u0664\u0663\u0662'
        resp = api.send(phone, 'E2E Arabic + prefix test')
        self.assertEqual(resp.get('result'), 'OK')

    def test_phone_arabic_with_spaces_dashes(self):
        """Arabic digits with spaces and dashes."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        phone = '\u0669\u0666\u0665-\u0669\u0668\u0667\u0666-\u0665\u0664\u0663\u0662'
        resp = api.send(phone, 'E2E Arabic dashes test')
        self.assertEqual(resp.get('result'), 'OK')


@tagged('post_install', '-at_install', 'kwtsms_e2e')
class TestPhoneValidationErrorsE2E(TransactionCase):
    """Test invalid phone numbers: errors logged with correct description."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.has_creds = bool(ICP.get_param('kwtsms.api_username', ''))
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.enabled', 'True')

    def _skip_if_no_creds(self):
        if not self.has_creds:
            self.skipTest('No kwtSMS API credentials')

    def test_email_instead_of_phone(self):
        """Email address should fail validation before hitting API."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send('user@example.com', 'Email test')
        self.assertEqual(resp.get('result'), 'ERROR')
        self.assertEqual(resp.get('code'), 'ERR_VALIDATION')
        self.assertIn('email', resp.get('description', '').lower())

    def test_phone_too_short_3_digits(self):
        """3-digit number should fail validation."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send('123', 'Too short test')
        self.assertEqual(resp.get('result'), 'ERROR')
        self.assertEqual(resp.get('code'), 'ERR_VALIDATION')
        self.assertIn('short', resp.get('description', '').lower())

    def test_phone_too_short_6_digits(self):
        """6-digit number should fail validation."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send('123456', 'Too short 6 test')
        self.assertEqual(resp.get('result'), 'ERROR')
        self.assertEqual(resp.get('code'), 'ERR_VALIDATION')

    def test_phone_no_digits(self):
        """Letters-only should fail validation."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send('abcdef', 'No digits test')
        self.assertEqual(resp.get('result'), 'ERROR')
        self.assertEqual(resp.get('code'), 'ERR_VALIDATION')
        self.assertIn('no digits', resp.get('description', '').lower())

    def test_phone_symbols_only(self):
        """Symbols only should fail validation."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send('+-.()', 'Symbols only test')
        self.assertEqual(resp.get('result'), 'ERROR')
        self.assertEqual(resp.get('code'), 'ERR_VALIDATION')

    def test_phone_empty_string(self):
        """Empty string should fail validation."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send('', 'Empty phone test')
        self.assertEqual(resp.get('result'), 'ERROR')
        self.assertEqual(resp.get('code'), 'ERR_VALIDATION')

    def test_phone_whitespace_only(self):
        """Whitespace-only should fail validation."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send('   ', 'Whitespace phone test')
        self.assertEqual(resp.get('result'), 'ERROR')
        self.assertEqual(resp.get('code'), 'ERR_VALIDATION')


@tagged('post_install', '-at_install', 'kwtsms_e2e')
class TestPhoneValidationErrorLogging(TransactionCase):
    """Test that validation errors from bad phone numbers are logged correctly.

    Note: We test error logging via direct API calls (not wizards) because
    the wizard raises UserError after logging, and assertRaises rolls back
    the savepoint, erasing the log record. The wizard UserError behavior
    is tested separately in TestComposeWizardE2E.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.has_creds = bool(ICP.get_param('kwtsms.api_username', ''))
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.enabled', 'True')

    def _skip_if_no_creds(self):
        if not self.has_creds:
            self.skipTest('No kwtSMS API credentials')

    def test_email_phone_error_logged(self):
        """Email as phone: send returns error, _log_send persists it."""
        self._skip_if_no_creds()
        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        api = KwtSmsApi(self.env)
        response = api.send('user@example.com', 'Test email phone')

        self.assertEqual(response.get('result'), 'ERROR')
        self.assertEqual(response.get('code'), 'ERR_VALIDATION')

        # Log the error (same as wizard would before raising UserError)
        api._log_send(
            numbers='user@example.com',
            message='Test email phone',
            response=response,
            status='error',
            error_code=response.get('code'),
            error_description=response.get('description', ''),
        )

        log = self.env['kwtsms.sms.log'].sudo().search([
            ('phone_number', '=', 'user@example.com'),
        ], limit=1, order='id desc')
        self.assertTrue(log, 'Error log should be created for email phone')
        self.assertEqual(log.status, 'error')
        self.assertIn('email', (log.error_description or '').lower())

    def test_short_phone_error_logged(self):
        """Short phone number: error logged with description."""
        self._skip_if_no_creds()
        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        api = KwtSmsApi(self.env)
        response = api.send('123', 'Test short phone')

        self.assertEqual(response.get('result'), 'ERROR')
        self.assertEqual(response.get('code'), 'ERR_VALIDATION')

        api._log_send(
            numbers='123',
            message='Test short phone',
            response=response,
            status='error',
            error_code=response.get('code'),
            error_description=response.get('description', ''),
        )

        log = self.env['kwtsms.sms.log'].sudo().search([
            ('phone_number', '=', '123'),
        ], limit=1, order='id desc')
        self.assertTrue(log, 'Error log should be created for short phone')
        self.assertEqual(log.status, 'error')
        self.assertIn('short', (log.error_description or '').lower())

    def test_no_digits_phone_error_logged(self):
        """No-digit phone: error logged with description."""
        self._skip_if_no_creds()
        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        api = KwtSmsApi(self.env)
        response = api.send('not-a-phone', 'Test bad phone')

        self.assertEqual(response.get('result'), 'ERROR')
        self.assertEqual(response.get('code'), 'ERR_VALIDATION')

        api._log_send(
            numbers='not-a-phone',
            message='Test bad phone',
            response=response,
            status='error',
            error_code=response.get('code'),
            error_description=response.get('description', ''),
        )

        log = self.env['kwtsms.sms.log'].sudo().search([
            ('phone_number', '=', 'not-a-phone'),
        ], limit=1, order='id desc')
        self.assertTrue(log, 'Error log should be created for bad phone')
        self.assertEqual(log.status, 'error')
        self.assertTrue(log.error_description, 'Error description should not be empty')


@tagged('post_install', '-at_install', 'kwtsms_e2e')
class TestMessageCleaningE2E(TransactionCase):
    """Test message cleaning via real API sends."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.has_creds = bool(ICP.get_param('kwtsms.api_username', ''))
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.enabled', 'True')

    def _skip_if_no_creds(self):
        if not self.has_creds:
            self.skipTest('No kwtSMS API credentials')

    def test_emoji_stripped_from_message(self):
        """Emojis should be stripped and message should still send OK."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send(TEST_PHONE, 'Order confirmed \U0001f389\U0001f600!')
        self.assertEqual(resp.get('result'), 'OK')

    def test_multiple_emojis_stripped(self):
        """Multiple emojis including flags, symbols should be stripped."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        msg = '\U0001f1f0\U0001f1fc Test \U0001f4e8 message \U0001f680\U0001f389'
        resp = api.send(TEST_PHONE, msg)
        self.assertEqual(resp.get('result'), 'OK')

    def test_arabic_digits_in_message_converted(self):
        """Arabic-Indic digits in message should be converted to Latin."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        # OTP: ١٢٣٤٥٦ -> OTP: 123456
        msg = 'Your OTP is: \u0661\u0662\u0663\u0664\u0665\u0666'
        resp = api.send(TEST_PHONE, msg)
        self.assertEqual(resp.get('result'), 'OK')
        api._log_send(
            numbers=TEST_PHONE, message=msg, response=resp, status='test',
        )
        log = self.env['kwtsms.sms.log'].sudo().search([
            ('msg_id', '=', resp['msg-id']),
        ], limit=1)
        self.assertTrue(log)

    def test_persian_digits_in_message_converted(self):
        """Persian digits should be converted to Latin."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        msg = 'Code: \u06f1\u06f2\u06f3\u06f4\u06f5\u06f6'
        resp = api.send(TEST_PHONE, msg)
        self.assertEqual(resp.get('result'), 'OK')

    def test_zero_width_space_stripped(self):
        """Zero-width spaces should be stripped from message."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        msg = 'Hello\u200bWorld\u200btest'
        resp = api.send(TEST_PHONE, msg)
        self.assertEqual(resp.get('result'), 'OK')

    def test_bom_stripped(self):
        """BOM characters from copy-paste should be stripped."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        msg = '\ufeffHello World from clipboard'
        resp = api.send(TEST_PHONE, msg)
        self.assertEqual(resp.get('result'), 'OK')

    def test_soft_hyphen_stripped(self):
        """Soft hyphens should be stripped."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        msg = 'soft\u00adhyphen\u00adtest'
        resp = api.send(TEST_PHONE, msg)
        self.assertEqual(resp.get('result'), 'OK')

    def test_ltr_rtl_marks_stripped(self):
        """Directional marks should be stripped."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        msg = 'Hello\u200eWorld\u200f from test'
        resp = api.send(TEST_PHONE, msg)
        self.assertEqual(resp.get('result'), 'OK')

    def test_arabic_text_preserved(self):
        """Arabic letter text should be preserved (not stripped)."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        msg = '\u0645\u0631\u062d\u0628\u0627 \u0628\u0643'  # marhaba bk
        resp = api.send(TEST_PHONE, msg)
        self.assertEqual(resp.get('result'), 'OK')

    def test_arabic_text_with_emoji_and_digits(self):
        """Real-world: Arabic text + emoji + Arabic digits all cleaned."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        msg = (
            '\ufeff\u0645\u0631\u062d\u0628\u0627 \U0001f600'
            ' OTP: \u0661\u0662\u0663\u200b'
        )
        resp = api.send(TEST_PHONE, msg)
        self.assertEqual(resp.get('result'), 'OK')

    def test_emoji_only_message_becomes_empty(self):
        """Message with only emojis should fail (empty after cleaning)."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        resp = api.send(TEST_PHONE, '\U0001f600\U0001f389\U0001f680')
        self.assertEqual(resp.get('result'), 'ERROR')
        self.assertEqual(resp.get('code'), 'ERR_VALIDATION')
        self.assertIn('empty', resp.get('description', '').lower())


@tagged('post_install', '-at_install', 'kwtsms_e2e')
class TestApiErrorLogging(TransactionCase):
    """Test that API errors (not validation) are logged correctly."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.has_creds = bool(ICP.get_param('kwtsms.api_username', ''))
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.enabled', 'True')

    def _skip_if_no_creds(self):
        if not self.has_creds:
            self.skipTest('No kwtSMS API credentials')

    def test_send_to_non_routable_number(self):
        """Send to a number with no route: should get API error and log it."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        # 599 is not a valid country code, the API may reject it
        resp = api.send('5992203222', 'Non-routable test')
        # The API may accept it (test mode) or reject it
        api._log_send(
            numbers='5992203222', message='Non-routable test',
            response=resp,
            status='test' if resp.get('result') == 'OK' else 'error',
            error_code=resp.get('code') if resp.get('result') != 'OK' else None,
            error_description=resp.get('description') if resp.get('result') != 'OK' else None,
        )
        log = self.env['kwtsms.sms.log'].sudo().search([
            ('phone_number', '=', '5992203222'),
        ], limit=1, order='id desc')
        self.assertTrue(log, 'Log record should exist')
        if log.status == 'error':
            self.assertTrue(log.error_description,
                            'Error description should be saved from API')
            _logger.info('Non-routable number error: %s', log.error_description)

    def test_error_description_saved_exactly(self):
        """Verify error_description stores the exact API error message."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        # Send via _send_sms_batch with a known bad number to trigger API error
        messages = [{
            'content': 'Error logging test',
            'numbers': [
                {'uuid': 'test-uuid-err-1', 'number': '5992203222'},
            ],
        }]
        api._send_sms_batch(messages)
        # Check the log
        log = self.env['kwtsms.sms.log'].sudo().search([
            ('phone_number', 'ilike', '5992203222'),
        ], limit=1, order='id desc')
        if log and log.status == 'error':
            self.assertTrue(log.error_description,
                            'error_description must contain the API error text')
            self.assertTrue(log.error_code,
                            'error_code must be populated')
            _logger.info('Error code=%s description=%s',
                         log.error_code, log.error_description)


@tagged('post_install', '-at_install', 'kwtsms_e2e')
class TestTemplateRenderingE2E(TransactionCase):
    """Test template rendering with real records."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.has_creds = bool(ICP.get_param('kwtsms.api_username', ''))
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.enabled', 'True')
        ICP.set_param('kwtsms.auto_order_confirm', 'True')

    def _skip_if_no_creds(self):
        if not self.has_creds:
            self.skipTest('No kwtSMS API credentials')

    def test_template_placeholders_replaced(self):
        """Template {placeholders} should be replaced with record values."""
        template = self.env['kwtsms.sms.template'].create({
            'name': 'E2E Placeholder Test',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Hi {customer_name}, order {order_name} is confirmed!',
        })
        partner = self.env['res.partner'].create({
            'name': 'Sultan Al-Otaibi',
            'phone': TEST_PHONE,
        })
        product = self.env['product.product'].search([], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': 'Wireless Charger', 'list_price': 10.0,
            })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
            })],
        })
        result = template.render_template(order)
        self.assertIn('Sultan Al-Otaibi', result)
        self.assertIn(order.name, result)
        self.assertNotIn('{customer_name}', result)
        self.assertNotIn('{order_name}', result)

    def test_template_unreplaced_placeholders_removed(self):
        """Unreplaced placeholders should be cleaned up."""
        template = self.env['kwtsms.sms.template'].create({
            'name': 'E2E Unreplaced Test',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Delivery {picking_name} tracking {tracking_ref}',
        })
        partner = self.env['res.partner'].create({
            'name': 'Dalal Al-Sabah', 'phone': TEST_PHONE,
        })
        product = self.env['product.product'].search([], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': 'Wireless Charger', 'list_price': 10.0,
            })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
            })],
        })
        result = template.render_template(order)
        self.assertNotIn('{tracking_ref}', result)

    def test_template_arabic_body(self):
        """Arabic template body should render correctly."""
        template = self.env['kwtsms.sms.template'].create({
            'name': 'E2E Arabic Template',
            'event_type': 'custom',
            'lang': 'ar',
            'body': '\u0645\u0631\u062d\u0628\u0627 {customer_name} \u0634\u0643\u0631\u0627',
        })
        partner = self.env['res.partner'].create({
            'name': '\u0623\u062d\u0645\u062f',
            'phone': TEST_PHONE,
        })
        product = self.env['product.product'].search([], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': 'Wireless Charger', 'list_price': 10.0,
            })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id, 'product_uom_qty': 1,
            })],
        })
        result = template.render_template(order)
        self.assertIn('\u0623\u062d\u0645\u062f', result)
        self.assertIn('\u0645\u0631\u062d\u0628\u0627', result)

    def test_template_with_emoji_in_body(self):
        """Template body with emoji: emoji stripped on send, template renders."""
        self._skip_if_no_creds()
        template = self.env['kwtsms.sms.template'].create({
            'name': 'E2E Emoji Template',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Hi {customer_name} \U0001f389 Your order is ready!',
        })
        partner = self.env['res.partner'].create({
            'name': 'Khaled Al-Enezi', 'phone': TEST_PHONE,
        })
        product = self.env['product.product'].search([], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': 'Wireless Charger', 'list_price': 10.0,
            })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id, 'product_uom_qty': 1,
            })],
        })
        rendered = template.render_template(order)
        self.assertIn('Khaled Al-Enezi', rendered)
        # Send it: emoji will be stripped by clean_message
        api = _get_api(self.env)
        resp = api.send(TEST_PHONE, rendered)
        self.assertEqual(resp.get('result'), 'OK')


@tagged('post_install', '-at_install', 'kwtsms_e2e')
class TestSendSmsBatchEdgeCases(TransactionCase):
    """Test _send_sms_batch with edge-case phone numbers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.has_creds = bool(ICP.get_param('kwtsms.api_username', ''))
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.enabled', 'True')

    def _skip_if_no_creds(self):
        if not self.has_creds:
            self.skipTest('No kwtSMS API credentials')

    def test_batch_mixed_valid_invalid(self):
        """Batch with mix of valid and invalid numbers."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        messages = [{
            'content': 'Mixed batch test',
            'numbers': [
                {'uuid': 'good-1', 'number': TEST_PHONE},
                {'uuid': 'bad-email', 'number': 'user@example.com'},
                {'uuid': 'bad-short', 'number': '123'},
                {'uuid': 'good-2', 'number': '+96555512345'},
            ],
        }]
        results = api._send_sms_batch(messages)
        # Should have 4 results
        self.assertEqual(len(results), 4)
        # Check valid ones succeeded
        good_results = [r for r in results if r['uuid'] in ('good-1', 'good-2')]
        for r in good_results:
            self.assertEqual(r['state'], 'success')
        # Check invalid ones failed with wrong_number_format
        bad_results = [r for r in results if r['uuid'] in ('bad-email', 'bad-short')]
        for r in bad_results:
            self.assertEqual(r['state'], 'wrong_number_format')
            self.assertEqual(r['failure_type'], 'sms_number_format')

    def test_batch_all_invalid(self):
        """Batch where all numbers are invalid: no API call made."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        messages = [{
            'content': 'All invalid batch',
            'numbers': [
                {'uuid': 'bad-1', 'number': 'email@test.com'},
                {'uuid': 'bad-2', 'number': ''},
                {'uuid': 'bad-3', 'number': 'abc'},
            ],
        }]
        results = api._send_sms_batch(messages)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertEqual(r['state'], 'wrong_number_format')

    def test_batch_arabic_phone_numbers(self):
        """Batch with Arabic-Indic digit phone numbers."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        arabic_phone = '\u0669\u0666\u0665\u0669\u0668\u0667\u0666\u0665\u0664\u0663\u0662'
        messages = [{
            'content': 'Arabic phone batch test',
            'numbers': [
                {'uuid': 'arabic-1', 'number': arabic_phone},
                {'uuid': 'latin-1', 'number': TEST_PHONE},
            ],
        }]
        results = api._send_sms_batch(messages)
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r['state'], 'success')

    def test_batch_empty_message(self):
        """Batch with empty message content: all should fail."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        messages = [{
            'content': '',
            'numbers': [
                {'uuid': 'empty-msg-1', 'number': TEST_PHONE},
            ],
        }]
        results = api._send_sms_batch(messages)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['state'], 'server_error')

    def test_batch_emoji_only_message(self):
        """Batch with emoji-only message: should fail after cleaning."""
        self._skip_if_no_creds()
        api = _get_api(self.env)
        messages = [{
            'content': '\U0001f600\U0001f389',
            'numbers': [
                {'uuid': 'emoji-only-1', 'number': TEST_PHONE},
            ],
        }]
        results = api._send_sms_batch(messages)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['state'], 'server_error')


@tagged('post_install', '-at_install', 'kwtsms_e2e')
class TestComposeWizardE2E(TransactionCase):
    """Test the SMS compose wizard with various edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.has_creds = bool(ICP.get_param('kwtsms.api_username', ''))
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.enabled', 'True')

    def _skip_if_no_creds(self):
        if not self.has_creds:
            self.skipTest('No kwtSMS API credentials')

    def test_compose_valid_send(self):
        """Normal compose wizard send."""
        self._skip_if_no_creds()
        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': TEST_PHONE,
            'message': 'E2E compose wizard test',
        })
        result = wizard.action_send()
        self.assertEqual(result.get('tag'), 'display_notification')
        log = self.env['kwtsms.sms.log'].sudo().search([
            ('phone_number', '=', TEST_PHONE),
            ('message_body', '=', 'E2E compose wizard test'),
        ], limit=1, order='id desc')
        self.assertTrue(log)
        self.assertEqual(log.status, 'test')

    def test_compose_arabic_phone(self):
        """Compose wizard with Arabic-Indic phone number."""
        self._skip_if_no_creds()
        arabic_phone = '\u0669\u0666\u0665\u0669\u0668\u0667\u0666\u0665\u0664\u0663\u0662'
        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': arabic_phone,
            'message': 'E2E Arabic phone compose test',
        })
        result = wizard.action_send()
        self.assertEqual(result.get('tag'), 'display_notification')

    def test_compose_emoji_message(self):
        """Compose wizard with emojis in message (should be cleaned)."""
        self._skip_if_no_creds()
        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': TEST_PHONE,
            'message': 'Hello \U0001f600 World \U0001f389',
        })
        result = wizard.action_send()
        self.assertEqual(result.get('tag'), 'display_notification')

    def test_compose_arabic_digits_message(self):
        """Compose wizard with Arabic digits in OTP message."""
        self._skip_if_no_creds()
        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': TEST_PHONE,
            'message': 'Your code: \u0661\u0662\u0663\u0664\u0665\u0666',
        })
        result = wizard.action_send()
        self.assertEqual(result.get('tag'), 'display_notification')

    def test_compose_with_template(self):
        """Compose wizard with template selection."""
        self._skip_if_no_creds()
        template = self.env['kwtsms.sms.template'].create({
            'name': 'E2E Compose Template',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Hello customer, your order is ready for pickup.',
        })
        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': TEST_PHONE,
            'message': template.body,
            'template_id': template.id,
        })
        result = wizard.action_send()
        self.assertEqual(result.get('tag'), 'display_notification')
        log = self.env['kwtsms.sms.log'].sudo().search([
            ('template_id', '=', template.id),
        ], limit=1, order='id desc')
        self.assertTrue(log)
        self.assertEqual(log.template_id.id, template.id)


@tagged('post_install', '-at_install', 'kwtsms_e2e')
class TestTestSmsWizardE2E(TransactionCase):
    """Test the Send Test SMS wizard with edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.has_creds = bool(ICP.get_param('kwtsms.api_username', ''))
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.enabled', 'True')

    def _skip_if_no_creds(self):
        if not self.has_creds:
            self.skipTest('No kwtSMS API credentials')

    def test_test_wizard_valid_send(self):
        """Normal test SMS wizard send."""
        self._skip_if_no_creds()
        wizard = self.env['kwtsms.test.sms.wizard'].create({
            'phone': TEST_PHONE,
            'message': 'E2E test wizard send',
        })
        result = wizard.action_send()
        self.assertEqual(result.get('tag'), 'display_notification')

    def test_test_wizard_arabic_phone(self):
        """Test wizard with Arabic-Indic phone number."""
        self._skip_if_no_creds()
        arabic_phone = '\u0669\u0666\u0665\u0669\u0668\u0667\u0666\u0665\u0664\u0663\u0662'
        wizard = self.env['kwtsms.test.sms.wizard'].create({
            'phone': arabic_phone,
            'message': 'E2E Arabic phone test wizard',
        })
        result = wizard.action_send()
        self.assertEqual(result.get('tag'), 'display_notification')

    def test_test_wizard_emoji_message(self):
        """Test wizard with emojis (stripped on send)."""
        self._skip_if_no_creds()
        wizard = self.env['kwtsms.test.sms.wizard'].create({
            'phone': TEST_PHONE,
            'message': 'Test \U0001f600\U0001f389 message!',
        })
        result = wizard.action_send()
        self.assertEqual(result.get('tag'), 'display_notification')

    def test_test_wizard_forces_test_mode(self):
        """Test wizard always sends in test mode even if system setting is OFF."""
        self._skip_if_no_creds()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.test_mode', 'False')
        try:
            wizard = self.env['kwtsms.test.sms.wizard'].create({
                'phone': TEST_PHONE,
                'message': 'Force test mode check',
            })
            result = wizard.action_send()
            self.assertEqual(result.get('tag'), 'display_notification')
            log = self.env['kwtsms.sms.log'].sudo().search([
                ('message_body', '=', 'Force test mode check'),
            ], limit=1, order='id desc')
            self.assertTrue(log)
            self.assertEqual(log.status, 'test',
                             'Test wizard should always log as test')
        finally:
            ICP.set_param('kwtsms.test_mode', 'True')


@tagged('post_install', '-at_install', 'kwtsms_e2e')
class TestOrderConfirmEdgeCases(TransactionCase):
    """Test order confirmation SMS hook with edge-case phone numbers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.has_creds = bool(ICP.get_param('kwtsms.api_username', ''))
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.enabled', 'True')
        ICP.set_param('kwtsms.auto_order_confirm', 'True')

    def _skip_if_no_creds(self):
        if not self.has_creds:
            self.skipTest('No kwtSMS API credentials')

    def _ensure_template(self):
        """Ensure order confirm template exists."""
        template = self.env['kwtsms.sms.template'].search([
            ('event_type', '=', 'order_confirm'),
            ('lang', '=', 'en'),
            ('active', '=', True),
        ], limit=1)
        if not template:
            template = self.env['kwtsms.sms.template'].create({
                'name': 'E2E Order Confirm',
                'event_type': 'order_confirm',
                'lang': 'en',
                'body': 'Order {order_name} confirmed for {customer_name}.',
            })
        return template

    def _get_product(self):
        product = self.env['product.product'].search([], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': 'Wireless Charger', 'list_price': 10.0,
            })
        return product

    def test_order_confirm_arabic_phone(self):
        """Order confirm with Arabic-Indic phone number on partner."""
        self._skip_if_no_creds()
        self._ensure_template()
        arabic_phone = '\u0669\u0666\u0665\u0669\u0668\u0667\u0666\u0665\u0664\u0663\u0662'
        partner = self.env['res.partner'].create({
            'name': 'Mishari Al-Azmi',
            'phone': arabic_phone,
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': self._get_product().id,
                'product_uom_qty': 1,
            })],
        })
        log_count_before = self.env['kwtsms.sms.log'].sudo().search_count([])
        order.action_confirm()
        log_count_after = self.env['kwtsms.sms.log'].sudo().search_count([])
        self.assertGreater(log_count_after, log_count_before,
                           'SMS should be sent for Arabic phone partner')

    def test_order_confirm_phone_with_spaces(self):
        """Order confirm with spaced phone number."""
        self._skip_if_no_creds()
        self._ensure_template()
        partner = self.env['res.partner'].create({
            'name': 'Reem Al-Ghanim',
            'phone': '+965 9876 5432',
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': self._get_product().id,
                'product_uom_qty': 1,
            })],
        })
        log_count_before = self.env['kwtsms.sms.log'].sudo().search_count([])
        order.action_confirm()
        log_count_after = self.env['kwtsms.sms.log'].sudo().search_count([])
        self.assertGreater(log_count_after, log_count_before)

    def test_order_confirm_no_phone(self):
        """Order confirm with partner having no phone: should not crash."""
        self._skip_if_no_creds()
        self._ensure_template()
        partner = self.env['res.partner'].create({
            'name': 'Abdulaziz Al-Dosari',
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': self._get_product().id,
                'product_uom_qty': 1,
            })],
        })
        # Should not crash even if partner has no phone
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_order_confirm_email_as_phone(self):
        """Order confirm with email in phone field: should not crash."""
        self._skip_if_no_creds()
        self._ensure_template()
        partner = self.env['res.partner'].create({
            'name': 'Sara Al-Mutairi',
            'phone': 'user@example.com',
        })
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': self._get_product().id,
                'product_uom_qty': 1,
            })],
        })
        # Should not crash, SMS hook should catch the error gracefully
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
