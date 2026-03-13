"""Tests for SMS sending integration: API, batch sending, business event hooks."""

import json
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestKwtSmsApi(TransactionCase):
    """Test KwtSmsApi class methods with mocked external calls."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.api_username', 'testuser')
        ICP.set_param('kwtsms.api_password', 'testpass')
        ICP.set_param('kwtsms.sender_id', 'KWT-SMS')
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.enabled', 'True')

    def _get_api(self):
        """Create and return a KwtSmsApi instance."""
        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        return KwtSmsApi(self.env)

    # ---------------------------------------------------------------
    # send tests
    # ---------------------------------------------------------------

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_success(self, mock_api_call):
        """Test send with a successful API response."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-001',
            'points-charged': 1,
            'balance-after': 999,
        }

        api = self._get_api()
        result = api.send('96598765432', 'Hello test')

        self.assertEqual(result['result'], 'OK')
        self.assertEqual(result['msg-id'], 'MSG-001')
        mock_api_call.assert_called_once()

        # Verify payload sent
        call_args = mock_api_call.call_args
        self.assertEqual(call_args[0][0], 'send')
        payload = call_args[0][1]
        self.assertEqual(payload['username'], 'testuser')
        self.assertEqual(payload['mobile'], '96598765432')
        self.assertEqual(payload['message'], 'Hello test')
        self.assertEqual(payload['test'], '1')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_failure(self, mock_api_call):
        """Test send with a failed API response."""
        mock_api_call.return_value = {
            'result': 'ERROR',
            'code': 'ERR010',
            'description': 'Insufficient credits',
        }

        api = self._get_api()
        result = api.send('96598765432', 'Hello test')

        self.assertEqual(result['result'], 'ERROR')
        self.assertEqual(result['code'], 'ERR010')

    def test_send_invalid_phone(self):
        """Test send with an invalid phone number."""
        api = self._get_api()
        result = api.send('123', 'Hello')

        self.assertEqual(result['result'], 'ERROR')
        self.assertEqual(result['code'], 'ERR_VALIDATION')

    def test_send_empty_message(self):
        """Test send with an empty message."""
        api = self._get_api()
        result = api.send('96598765432', '')

        self.assertEqual(result['result'], 'ERROR')
        self.assertEqual(result['code'], 'ERR_VALIDATION')

    def test_send_none_phone(self):
        """Test send with None phone."""
        api = self._get_api()
        result = api.send(None, 'Hello')

        self.assertEqual(result['result'], 'ERROR')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_custom_sender_id(self, mock_api_call):
        """Test send with custom sender ID override."""
        mock_api_call.return_value = {'result': 'OK'}

        api = self._get_api()
        api.send('96598765432', 'Hello', sender_id='CUSTOM')

        payload = mock_api_call.call_args[0][1]
        self.assertEqual(payload['sender'], 'CUSTOM')

    # ---------------------------------------------------------------
    # _send_sms_batch tests (Odoo framework integration)
    # ---------------------------------------------------------------

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_sms_batch_success(self, mock_api_call):
        """Test _send_sms_batch with valid numbers and successful API."""
        mock_api_call.return_value = {
            'result': 'OK',
            'points-charged': 2,
            'balance-after': 998,
        }

        api = self._get_api()
        messages = [{
            'content': 'Hello batch test',
            'numbers': [
                {'uuid': 'uuid-1', 'number': '96598765432'},
                {'uuid': 'uuid-2', 'number': '+96598765432'},
            ],
        }]
        results = api._send_sms_batch(messages)

        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r['state'], 'success')
            self.assertIn('credit', r)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_sms_batch_api_error(self, mock_api_call):
        """Test _send_sms_batch maps API errors to correct failure types."""
        mock_api_call.return_value = {
            'result': 'ERROR',
            'code': 'ERR010',
            'description': 'Insufficient credits',
        }

        api = self._get_api()
        messages = [{
            'content': 'Hello',
            'numbers': [
                {'uuid': 'uuid-1', 'number': '96598765432'},
            ],
        }]
        results = api._send_sms_batch(messages)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['state'], 'insufficient_credit')
        self.assertEqual(results[0]['failure_type'], 'sms_credit')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_sms_batch_invalid_numbers(self, mock_api_call):
        """Test _send_sms_batch handles invalid phone numbers."""
        api = self._get_api()
        messages = [{
            'content': 'Hello',
            'numbers': [
                {'uuid': 'uuid-bad', 'number': '123'},
                {'uuid': 'uuid-email', 'number': 'user@email.com'},
            ],
        }]
        results = api._send_sms_batch(messages)

        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r['state'], 'wrong_number_format')
            self.assertEqual(r['failure_type'], 'sms_number_format')

        # API should not have been called since all numbers are invalid
        mock_api_call.assert_not_called()

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_sms_batch_mixed_valid_invalid(self, mock_api_call):
        """Test _send_sms_batch with mix of valid and invalid numbers."""
        mock_api_call.return_value = {
            'result': 'OK',
            'points-charged': 1,
            'balance-after': 999,
        }

        api = self._get_api()
        messages = [{
            'content': 'Hello',
            'numbers': [
                {'uuid': 'uuid-valid', 'number': '96598765432'},
                {'uuid': 'uuid-bad', 'number': '123'},
            ],
        }]
        results = api._send_sms_batch(messages)

        self.assertEqual(len(results), 2)

        # Find results by uuid
        valid_result = next(r for r in results if r['uuid'] == 'uuid-valid')
        bad_result = next(r for r in results if r['uuid'] == 'uuid-bad')

        self.assertEqual(valid_result['state'], 'success')
        self.assertEqual(bad_result['state'], 'wrong_number_format')

    def test_send_sms_batch_empty_content(self):
        """Test _send_sms_batch with empty message content."""
        api = self._get_api()
        messages = [{
            'content': '',
            'numbers': [
                {'uuid': 'uuid-1', 'number': '96598765432'},
            ],
        }]
        results = api._send_sms_batch(messages)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['state'], 'server_error')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_sms_batch_multiple_messages(self, mock_api_call):
        """Test _send_sms_batch with multiple message groups."""
        mock_api_call.return_value = {
            'result': 'OK',
            'points-charged': 1,
            'balance-after': 998,
        }

        api = self._get_api()
        messages = [
            {
                'content': 'Message one',
                'numbers': [{'uuid': 'uuid-1', 'number': '96598765432'}],
            },
            {
                'content': 'Message two',
                'numbers': [{'uuid': 'uuid-2', 'number': '96598765432'}],
            },
        ]
        results = api._send_sms_batch(messages)

        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r['state'], 'success')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_sms_batch_error_code_mapping(self, mock_api_call):
        """Test error code to failure type mapping."""
        error_cases = [
            ('ERR003', 'sms_acc', 'server_error'),
            ('ERR006', 'sms_number_format', 'wrong_number_format'),
            ('ERR010', 'sms_credit', 'insufficient_credit'),
            ('ERR013', 'sms_server', 'server_error'),
            ('UNKNOWN', 'sms_server', 'server_error'),
        ]

        api = self._get_api()
        for error_code, expected_failure, expected_state in error_cases:
            mock_api_call.return_value = {
                'result': 'ERROR',
                'code': error_code,
                'description': 'Test error',
            }
            messages = [{
                'content': 'Hello',
                'numbers': [{'uuid': f'uuid-{error_code}', 'number': '96598765432'}],
            }]
            results = api._send_sms_batch(messages)
            self.assertEqual(
                results[0]['failure_type'], expected_failure,
                'Error code %s should map to failure type %s' % (error_code, expected_failure),
            )
            self.assertEqual(
                results[0]['state'], expected_state,
                'Error code %s should map to state %s' % (error_code, expected_state),
            )

    # ---------------------------------------------------------------
    # _log_send tests
    # ---------------------------------------------------------------

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_log_send_creates_log_entry(self, mock_api_call):
        """Test that _log_send creates a kwtsms.sms.log record."""
        api = self._get_api()
        api._log_send(
            numbers='96598765432',
            message='Test log message',
            response={'result': 'OK', 'msg-id': 'MSG-100', 'points-charged': 1},
            status='success',
        )

        log = self.env['kwtsms.sms.log'].search([
            ('msg_id', '=', 'MSG-100'),
        ], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.phone_number, '96598765432')
        self.assertEqual(log.message_body, 'Test log message')
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.points_charged, 1)
        self.assertTrue(log.test_mode)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_log_send_strips_password(self, mock_api_call):
        """Test that _log_send does not store passwords in the log."""
        api = self._get_api()
        api._log_send(
            numbers='96598765432',
            message='Test',
            response={
                'result': 'OK',
                'password': 'secret123',
                'msg-id': 'MSG-PW',
            },
            status='success',
        )

        log = self.env['kwtsms.sms.log'].search([
            ('msg_id', '=', 'MSG-PW'),
        ], limit=1)
        logged_response = json.loads(log.api_response)
        self.assertNotIn('password', logged_response)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_log_send_with_error(self, mock_api_call):
        """Test _log_send records error details."""
        api = self._get_api()
        api._log_send(
            numbers='96598765432',
            message='Test',
            response={'result': 'ERROR', 'code': 'ERR010'},
            status='error',
            error_code='ERR010',
            error_description='Insufficient credits',
        )

        log = self.env['kwtsms.sms.log'].search([
            ('error_code', '=', 'ERR010'),
        ], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.status, 'error')
        self.assertEqual(log.error_description, 'Insufficient credits')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_log_send_with_related_record(self, mock_api_call):
        """Test _log_send stores related model and record ID."""
        partner = self.env['res.partner'].create({'name': 'Youssef Al-Enezi'})

        api = self._get_api()
        api._log_send(
            numbers='96598765432',
            message='Test',
            response={'result': 'OK', 'msg-id': 'MSG-REL'},
            status='success',
            res_model='res.partner',
            res_id=partner.id,
        )

        log = self.env['kwtsms.sms.log'].search([
            ('msg_id', '=', 'MSG-REL'),
        ], limit=1)
        self.assertEqual(log.res_model, 'res.partner')
        self.assertEqual(log.res_id, partner.id)

    # ---------------------------------------------------------------
    # check_balance, fetch_sender_ids, fetch_coverage
    # ---------------------------------------------------------------

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_check_balance(self, mock_api_call):
        """Test check_balance sends correct payload."""
        mock_api_call.return_value = {
            'result': 'OK',
            'available': 500,
            'purchased': 1000,
        }

        api = self._get_api()
        result = api.check_balance()

        self.assertEqual(result['result'], 'OK')
        mock_api_call.assert_called_once_with('balance', {
            'username': 'testuser',
            'password': 'testpass',
        })

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_fetch_sender_ids(self, mock_api_call):
        """Test fetch_sender_ids sends correct payload."""
        mock_api_call.return_value = {
            'result': 'OK',
            'senderid': ['KWT-SMS', 'MYCOMPANY'],
        }

        api = self._get_api()
        result = api.fetch_sender_ids()

        self.assertEqual(result['result'], 'OK')
        mock_api_call.assert_called_once_with('senderid', {
            'username': 'testuser',
            'password': 'testpass',
        })

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_fetch_coverage(self, mock_api_call):
        """Test fetch_coverage sends correct payload."""
        mock_api_call.return_value = {
            'result': 'OK',
            'coverage': [{'country': 'Kuwait'}],
        }

        api = self._get_api()
        result = api.fetch_coverage()

        self.assertEqual(result['result'], 'OK')
        mock_api_call.assert_called_once_with('coverage', {
            'username': 'testuser',
            'password': 'testpass',
        })

    # ---------------------------------------------------------------
    # validate_numbers
    # ---------------------------------------------------------------

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_validate_numbers(self, mock_api_call):
        """Test validate_numbers with valid and invalid numbers."""
        mock_api_call.return_value = {
            'ok': ['96598765432'],
            'er': [],
            'nr': [],
        }

        api = self._get_api()
        result = api.validate_numbers(['+96598765432'])

        self.assertIn('ok', result)
        payload = mock_api_call.call_args[0][1]
        self.assertEqual(payload['mobile'], '96598765432')

    def test_validate_numbers_all_invalid(self):
        """Test validate_numbers with all invalid numbers."""
        api = self._get_api()
        result = api.validate_numbers(['abc', '', None])

        # Should return empty lists without calling API
        self.assertEqual(result, {'ok': [], 'er': [], 'nr': []})

    # ---------------------------------------------------------------
    # API init / test mode
    # ---------------------------------------------------------------

    def test_api_test_mode_on(self):
        """Test API initializes with test mode from config."""
        api = self._get_api()
        self.assertTrue(api._test_mode)

    def test_api_test_mode_off(self):
        """Test API reads test mode = False when configured."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.test_mode', 'False')

        api = self._get_api()
        self.assertFalse(api._test_mode)

        # Restore
        ICP.set_param('kwtsms.test_mode', 'True')

    def test_api_credentials_loaded(self):
        """Test API loads credentials from config parameters."""
        api = self._get_api()
        self.assertEqual(api._username, 'testuser')
        self.assertEqual(api._password, 'testpass')
        self.assertEqual(api._sender_id, 'KWT-SMS')

    # ---------------------------------------------------------------
    # Balance guard tests
    # ---------------------------------------------------------------

    def _get_gateway_config(self):
        """Get or create gateway config for tests."""
        return self.env['kwtsms.gateway.config'].sudo()._get_or_create()

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_blocked_when_zero_balance(self, mock_api_call):
        """Test send returns ERR_NO_BALANCE when balance is zero."""
        config = self._get_gateway_config()
        config.write({'balance_available': 0})

        api = self._get_api()
        result = api.send('96598765432', 'Hello test')

        self.assertEqual(result['result'], 'ERROR')
        self.assertEqual(result['code'], 'ERR_NO_BALANCE')
        mock_api_call.assert_not_called()

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_blocked_when_zero_balance_test_mode(self, mock_api_call):
        """Test balance guard fires in test mode too (credits held, recoverable)."""
        config = self._get_gateway_config()
        config.write({'balance_available': 0})

        # Confirm test mode is on
        api = self._get_api()
        self.assertTrue(api._test_mode)

        result = api.send('96598765432', 'Hello test')

        self.assertEqual(result['result'], 'ERROR')
        self.assertEqual(result['code'], 'ERR_NO_BALANCE')
        mock_api_call.assert_not_called()

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_blocked_when_negative_balance(self, mock_api_call):
        """Test send returns ERR_NO_BALANCE when balance is negative."""
        config = self._get_gateway_config()
        config.write({'balance_available': -5})

        api = self._get_api()
        result = api.send('96598765432', 'Hello test')

        self.assertEqual(result['result'], 'ERROR')
        self.assertEqual(result['code'], 'ERR_NO_BALANCE')
        mock_api_call.assert_not_called()

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_proceeds_when_positive_balance(self, mock_api_call):
        """Test send proceeds to API when balance is positive."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-BAL',
            'points-charged': 1,
            'balance-after': 99,
        }

        config = self._get_gateway_config()
        config.write({'balance_available': 100})

        api = self._get_api()
        result = api.send('96598765432', 'Hello test')

        self.assertEqual(result['result'], 'OK')
        mock_api_call.assert_called_once()

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_balance_guard_fails_safely(self, mock_api_call):
        """Test send proceeds if balance guard config lookup fails."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-SAFE',
            'points-charged': 1,
            'balance-after': 99,
        }

        api = self._get_api()
        # Patch _get_or_create to raise an exception
        with patch.object(
            type(self.env['kwtsms.gateway.config']),
            '_get_or_create',
            side_effect=Exception('DB error'),
        ):
            result = api.send('96598765432', 'Hello test')

        # Should proceed despite config error
        self.assertEqual(result['result'], 'OK')
        mock_api_call.assert_called_once()

    # ---------------------------------------------------------------
    # Coverage guard tests
    # ---------------------------------------------------------------

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_blocked_when_all_numbers_uncovered(self, mock_api_call):
        """Test send returns ERR_NO_COVERAGE when no numbers match coverage."""
        config = self._get_gateway_config()
        config.write({
            'balance_available': 100,
            'coverage_json': json.dumps(['965', '966']),
        })

        api = self._get_api()
        # 44 is UK prefix, not in coverage
        result = api.send('447911123456', 'Hello')

        self.assertEqual(result['result'], 'ERROR')
        self.assertEqual(result['code'], 'ERR_NO_COVERAGE')
        mock_api_call.assert_not_called()

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_partial_coverage_filters_uncovered(self, mock_api_call):
        """Test partial coverage: covered numbers sent, uncovered in invalid list."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-COV',
            'points-charged': 1,
            'balance-after': 99,
        }

        config = self._get_gateway_config()
        config.write({
            'balance_available': 100,
            'coverage_json': json.dumps(['965']),
        })

        api = self._get_api()
        # 965 is covered, 44 is not
        result = api.send(['96598765432', '447911123456'], 'Hello')

        self.assertEqual(result['result'], 'OK')
        mock_api_call.assert_called_once()

        # Verify only the covered number was sent
        payload = mock_api_call.call_args[0][1]
        self.assertEqual(payload['mobile'], '96598765432')

        # Uncovered number should be in invalid list
        self.assertTrue(result.get('invalid'))
        uncovered_inputs = [i['input'] for i in result['invalid']]
        self.assertIn('447911123456', uncovered_inputs)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_coverage_guard_inactive_when_no_data(self, mock_api_call):
        """Test coverage guard is inactive when no coverage data loaded."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-NOCOV',
            'points-charged': 1,
            'balance-after': 99,
        }

        config = self._get_gateway_config()
        config.write({
            'balance_available': 100,
            'coverage_json': '[]',
        })

        api = self._get_api()
        # UK number should pass through when no coverage data
        result = api.send('447911123456', 'Hello')

        self.assertEqual(result['result'], 'OK')
        mock_api_call.assert_called_once()

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_coverage_prefix_matching_lengths(self, mock_api_call):
        """Test coverage prefix matching checks 3, 2, then 1 digit prefixes."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-PFX',
            'points-charged': 1,
            'balance-after': 99,
        }

        config = self._get_gateway_config()
        # Only 3-digit prefix "965" in coverage
        config.write({
            'balance_available': 100,
            'coverage_json': json.dumps(['965']),
        })

        api = self._get_api()
        result = api.send('96598765432', 'Hello')
        self.assertEqual(result['result'], 'OK')
        mock_api_call.assert_called()

        # Now test with 2-digit prefix
        mock_api_call.reset_mock()
        config.write({'coverage_json': json.dumps(['96'])})

        result = api.send('96598765432', 'Hello')
        self.assertEqual(result['result'], 'OK')
        mock_api_call.assert_called()

        # Now test with 1-digit prefix
        mock_api_call.reset_mock()
        config.write({'coverage_json': json.dumps(['9'])})

        result = api.send('96598765432', 'Hello')
        self.assertEqual(result['result'], 'OK')
        mock_api_call.assert_called()

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_send_coverage_guard_fails_safely(self, mock_api_call):
        """Test send proceeds if coverage guard config lookup fails."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-CSAFE',
            'points-charged': 1,
            'balance-after': 99,
        }

        config = self._get_gateway_config()
        config.write({'balance_available': 100})

        api = self._get_api()
        # Patch get_coverage_prefixes to raise
        with patch.object(
            type(self.env['kwtsms.gateway.config']),
            'get_coverage_prefixes',
            side_effect=Exception('JSON parse error'),
        ):
            result = api.send('96598765432', 'Hello test')

        self.assertEqual(result['result'], 'OK')
        mock_api_call.assert_called_once()


@tagged('post_install', '-at_install')
class TestSaleOrderSmsIntegration(TransactionCase):
    """Test sale.order SMS notification on confirmation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write({'name': 'Kuwait Digital Store'})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.enabled', 'True')
        ICP.set_param('kwtsms.auto_order_confirm', 'True')
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.api_username', 'testuser')
        ICP.set_param('kwtsms.api_password', 'testpass')
        ICP.set_param('kwtsms.sender_id', 'KWT-SMS')

        cls.partner = cls.env['res.partner'].create({
            'name': 'Ahmad Al-Sabah',
            'phone': '+96598765432',
        })

        # Create a product for the sale order
        cls.product = cls.env['product.product'].create({
            'name': 'Samsung Galaxy S24',
            'type': 'consu',
            'list_price': 100.0,
        })

        # Create a template for order confirmation
        cls.template = cls.env['kwtsms.sms.template'].create({
            'name': 'Order Confirm EN',
            'event_type': 'order_confirm',
            'lang': 'en',
            'body': 'Dear {customer_name}, order {order_name} is confirmed.',
        })

    def _create_sale_order(self):
        """Helper to create a sale order."""
        self.env.invalidate_all()
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_order_confirm_sends_sms(self, mock_api_call):
        """Test that confirming a sale order sends an SMS."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-SO-001',
            'points-charged': 1,
            'balance-after': 999,
        }

        order = self._create_sale_order()
        order.action_confirm()

        # Verify API was called
        self.assertTrue(mock_api_call.called)

        # Verify log was created
        log = self.env['kwtsms.sms.log'].search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
        ], limit=1)
        self.assertTrue(log)
        self.assertIn('96598765432', log.phone_number)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_order_confirm_sms_disabled(self, mock_api_call):
        """Test that SMS is not sent when auto_order_confirm is disabled."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.auto_order_confirm', 'False')

        order = self._create_sale_order()
        order.action_confirm()

        mock_api_call.assert_not_called()

        # Restore
        ICP.set_param('kwtsms.auto_order_confirm', 'True')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_order_confirm_gateway_disabled(self, mock_api_call):
        """Test that SMS is not sent when gateway is disabled."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.enabled', 'False')

        order = self._create_sale_order()
        order.action_confirm()

        mock_api_call.assert_not_called()

        # Restore
        ICP.set_param('kwtsms.enabled', 'True')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_order_confirm_no_phone(self, mock_api_call):
        """Test that SMS is skipped when partner has no phone."""
        partner_no_phone = self.env['res.partner'].create({
            'name': 'Khalid Al-Dosari',
        })
        order = self.env['sale.order'].create({
            'partner_id': partner_no_phone.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        order.action_confirm()

        mock_api_call.assert_not_called()

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_order_confirm_no_template(self, mock_api_call):
        """Test that SMS is skipped when no matching template exists."""
        # Deactivate ALL order_confirm templates (including demo data)
        all_order_templates = self.env['kwtsms.sms.template'].search([
            ('event_type', '=', 'order_confirm'),
        ])
        all_order_templates.write({'active': False})

        order = self._create_sale_order()
        order.action_confirm()

        mock_api_call.assert_not_called()

        # Restore
        all_order_templates.write({'active': True})

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_order_confirm_sms_failure_does_not_block(self, mock_api_call):
        """Test that SMS failure does not prevent order confirmation."""
        mock_api_call.side_effect = Exception('Network timeout')

        order = self._create_sale_order()
        # Should not raise despite SMS failure
        order.action_confirm()

        # Order should still be confirmed
        self.assertEqual(order.state, 'sale')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_order_confirm_api_error_does_not_block(self, mock_api_call):
        """Test that API error response does not block order confirmation."""
        mock_api_call.return_value = {
            'result': 'ERROR',
            'code': 'ERR010',
            'description': 'Insufficient credits',
        }

        order = self._create_sale_order()
        order.action_confirm()

        # Order should still be confirmed
        self.assertEqual(order.state, 'sale')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_order_confirm_arabic_partner(self, mock_api_call):
        """Test that Arabic language is detected from partner."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-AR',
            'points-charged': 1,
        }

        ar_template = self.env['kwtsms.sms.template'].create({
            'name': 'Order Confirm AR',
            'event_type': 'order_confirm',
            'lang': 'ar',
            'body': '\u062a\u0645 \u062a\u0623\u0643\u064a\u062f \u0637\u0644\u0628\u0643 {order_name}',
        })

        ar_partner = self.env['res.partner'].create({
            'name': 'Hessa Al-Fahad',
            'phone': '+96598765432',
            'lang': 'ar_001',
        })
        # Create order with English partner, then swap via SQL to avoid
        # ORM translatable field cache issues with Arabic context.
        order = self._create_sale_order()
        self.env.cr.execute(
            "UPDATE sale_order SET partner_id = %s WHERE id = %s",
            (ar_partner.id, order.id),
        )
        order.invalidate_recordset(['partner_id'])
        order.action_confirm()

        # Find the log entry
        log = self.env['kwtsms.sms.log'].search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
        ], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.template_id.id, ar_template.id)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_order_confirm_test_mode_status(self, mock_api_call):
        """Test that log status is 'test' when test mode is enabled."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-TEST',
            'points-charged': 0,
        }

        order = self._create_sale_order()
        order.action_confirm()

        log = self.env['kwtsms.sms.log'].search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
        ], limit=1)
        self.assertEqual(log.status, 'test')
        self.assertTrue(log.test_mode)


@tagged('post_install', '-at_install')
class TestStockPickingSmsIntegration(TransactionCase):
    """Test stock.picking SMS notification on delivery completion."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write({'name': 'Kuwait Digital Store'})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.enabled', 'True')
        ICP.set_param('kwtsms.auto_delivery_done', 'True')
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.api_username', 'testuser')
        ICP.set_param('kwtsms.api_password', 'testpass')
        ICP.set_param('kwtsms.sender_id', 'KWT-SMS')

        cls.partner = cls.env['res.partner'].create({
            'name': 'Fatima Al-Rashidi',
            'phone': '+96598765432',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Apple iPad Pro',
            'type': 'consu',
            'list_price': 50.0,
        })

        cls.template = cls.env['kwtsms.sms.template'].create({
            'name': 'Delivery Done EN',
            'event_type': 'delivery_done',
            'lang': 'en',
            'body': 'Dear {customer_name}, your delivery {picking_name} is complete.',
        })

    def _create_outgoing_picking(self):
        """Helper to create an outgoing stock picking."""
        self.env.invalidate_all()
        picking_type = self.env.ref('stock.picking_type_out')
        location_src = self.env.ref('stock.stock_location_stock')
        location_dest = self.env.ref('stock.stock_location_customers')

        picking = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': picking_type.id,
            'location_id': location_src.id,
            'location_dest_id': location_dest.id,
            'move_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'product_uom': self.product.uom_id.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
            })],
        })
        return picking

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_delivery_done_sends_sms(self, mock_api_call):
        """Test that completing a delivery sends an SMS."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-DEL-001',
            'points-charged': 1,
        }

        picking = self._create_outgoing_picking()
        picking.action_confirm()
        picking.move_ids.quantity = 1.0
        picking.move_ids.picked = True
        picking.button_validate()

        log = self.env['kwtsms.sms.log'].search([
            ('res_model', '=', 'stock.picking'),
            ('res_id', '=', picking.id),
        ], limit=1)
        self.assertTrue(log)
        self.assertIn('96598765432', log.phone_number)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_delivery_done_sms_disabled(self, mock_api_call):
        """Test that SMS is not sent when auto_delivery_done is disabled."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.auto_delivery_done', 'False')

        picking = self._create_outgoing_picking()
        picking.action_confirm()
        picking.move_ids.quantity = 1.0
        picking.move_ids.picked = True
        picking.button_validate()

        mock_api_call.assert_not_called()

        # Restore
        ICP.set_param('kwtsms.auto_delivery_done', 'True')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_delivery_failure_does_not_block(self, mock_api_call):
        """Test that SMS failure does not prevent delivery completion."""
        mock_api_call.side_effect = Exception('Network error')

        picking = self._create_outgoing_picking()
        picking.action_confirm()
        picking.move_ids.quantity = 1.0
        picking.move_ids.picked = True

        # Should not raise despite SMS failure
        picking.button_validate()

        # Picking should still be done
        self.assertEqual(picking.state, 'done')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_delivery_no_partner_phone(self, mock_api_call):
        """Test that SMS is skipped when delivery partner has no phone."""
        partner_no_phone = self.env['res.partner'].create({
            'name': 'Omar Al-Shammari',
        })
        picking_type = self.env.ref('stock.picking_type_out')
        location_src = self.env.ref('stock.stock_location_stock')
        location_dest = self.env.ref('stock.stock_location_customers')

        self.env.invalidate_all()
        picking = self.env['stock.picking'].create({
            'partner_id': partner_no_phone.id,
            'picking_type_id': picking_type.id,
            'location_id': location_src.id,
            'location_dest_id': location_dest.id,
            'move_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'product_uom': self.product.uom_id.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
            })],
        })
        picking.action_confirm()
        picking.move_ids.quantity = 1.0
        picking.move_ids.picked = True
        picking.button_validate()

        mock_api_call.assert_not_called()


@tagged('post_install', '-at_install')
class TestResCompanySmsRouting(TransactionCase):
    """Test res.company._get_sms_api_class override."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'name': 'Kuwait Digital Store'})

    def test_returns_kwtsms_when_configured(self):
        """Test _get_sms_api_class returns KwtSmsApi when enabled."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.enabled', 'True')
        ICP.set_param('kwtsms.api_username', 'testuser')

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        result = self.company._get_sms_api_class()
        self.assertEqual(result, KwtSmsApi)

    def test_returns_default_when_disabled(self):
        """Test _get_sms_api_class returns default when gateway is disabled."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.enabled', 'False')
        ICP.set_param('kwtsms.api_username', 'testuser')

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        result = self.company._get_sms_api_class()
        self.assertNotEqual(result, KwtSmsApi)

    def test_returns_default_when_no_username(self):
        """Test _get_sms_api_class returns default when no username set."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.enabled', 'True')
        ICP.set_param('kwtsms.api_username', '')

        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        result = self.company._get_sms_api_class()
        self.assertNotEqual(result, KwtSmsApi)
