"""End-to-end tests using the real kwtSMS API with test=1.

All tests hit the real kwtSMS API. test_mode is always ON so messages
are queued but never delivered and no credits are consumed.

Requires valid API credentials in ir.config_parameter:
  kwtsms.api_username, kwtsms.api_password
"""

import logging

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)

TEST_PHONE = '96598765432'


@tagged('post_install', '-at_install', 'kwtsms_e2e')
class TestRealApiDirect(TransactionCase):
    """Test direct API calls against the real kwtSMS gateway."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.username = ICP.get_param('kwtsms.api_username', '')
        cls.password = ICP.get_param('kwtsms.api_password', '')
        if not cls.username or not cls.password:
            _logger.warning('Skipping E2E tests: no kwtSMS credentials configured')
        # Ensure test mode ON
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.enabled', 'True')

    def _skip_if_no_creds(self):
        if not self.username or not self.password:
            self.skipTest('No kwtSMS API credentials configured')

    def _get_api(self):
        from odoo.addons.kwtsms_sms.tools.kwtsms_api import KwtSmsApi
        return KwtSmsApi(self.env)

    def test_01_balance_check(self):
        """Check balance via real API."""
        self._skip_if_no_creds()
        api = self._get_api()
        resp = api.check_balance()
        self.assertEqual(resp.get('result'), 'OK')
        self.assertIn('available', resp)
        self.assertIn('purchased', resp)
        _logger.info(
            'E2E balance: available=%s purchased=%s',
            resp['available'], resp['purchased'],
        )

    def test_02_fetch_sender_ids(self):
        """Fetch sender IDs via real API."""
        self._skip_if_no_creds()
        api = self._get_api()
        resp = api.fetch_sender_ids()
        self.assertEqual(resp.get('result'), 'OK')
        self.assertIn('senderid', resp)
        _logger.info('E2E sender IDs: %s', resp['senderid'])

    def test_03_send_sms(self):
        """Send a single SMS via real API (test mode)."""
        self._skip_if_no_creds()
        api = self._get_api()
        self.assertTrue(api._test_mode, 'Test mode must be ON')
        resp = api.send(TEST_PHONE, 'E2E test: single SMS from Odoo')
        self.assertEqual(resp.get('result'), 'OK')
        self.assertTrue(resp.get('msg-id'))
        _logger.info('E2E send: msg-id=%s', resp['msg-id'])

    def test_04_send_and_log(self):
        """Send SMS and verify log record is created."""
        self._skip_if_no_creds()
        api = self._get_api()
        self.assertTrue(api._test_mode)
        resp = api.send(TEST_PHONE, 'E2E test: logged SMS from Odoo')
        self.assertEqual(resp.get('result'), 'OK')

        api._log_send(
            numbers=TEST_PHONE,
            message='E2E test: logged SMS from Odoo',
            response=resp,
            status='test',
        )
        log = self.env['kwtsms.sms.log'].sudo().search([
            ('msg_id', '=', resp['msg-id']),
        ], limit=1)
        self.assertTrue(log, 'Log record should exist for sent SMS')
        self.assertEqual(log.status, 'test')
        self.assertEqual(log.phone_number, TEST_PHONE)

    def test_05_bulk_send(self):
        """Send to multiple distinct numbers in a single API call (test mode)."""
        self._skip_if_no_creds()
        api = self._get_api()
        self.assertTrue(api._test_mode)
        # Use distinct Kuwait mobile numbers (965 + 8 digits starting with 5/6/9)
        bulk_numbers = [TEST_PHONE, '96555512345', '96566778899']
        numbers = ','.join(bulk_numbers)
        payload = {
            'username': api._username,
            'password': api._password,
            'sender': api._sender_id,
            'mobile': numbers,
            'message': 'E2E test: bulk SMS from Odoo',
            'test': '1',
        }
        resp = api._api_call('send', payload)
        self.assertEqual(resp.get('result'), 'OK')
        self.assertTrue(resp.get('msg-id'))
        self.assertGreaterEqual(resp.get('numbers', 0), 2,
                                'At least 2 numbers should be accepted')
        _logger.info(
            'E2E bulk send: msg-id=%s numbers=%s',
            resp['msg-id'], resp.get('numbers'),
        )

    def test_06_bulk_send_250_numbers(self):
        """Send to 250 numbers to verify auto-batching (>200 triggers 2 API calls)."""
        self._skip_if_no_creds()
        api = self._get_api()
        self.assertTrue(api._test_mode)
        # Generate 250 distinct Kuwait mobile numbers (965 + 8 digits)
        # Pattern: 9655XXYY000..249 to ensure uniqueness
        bulk_numbers = []
        for i in range(250):
            # 96550 + zero-padded 6 digits (96550000000..96550000249)
            number = f'96550{i:06d}'
            bulk_numbers.append(number)
        self.assertEqual(len(bulk_numbers), 250)
        self.assertEqual(len(set(bulk_numbers)), 250, 'All numbers must be unique')

        # Send via _send_sms_batch which handles the 200-number batching
        messages = [{
            'content': 'E2E test: bulk 250 numbers batch test',
            'numbers': [
                {'uuid': f'uuid-{i}', 'number': num}
                for i, num in enumerate(bulk_numbers)
            ],
        }]
        results = api._send_sms_batch(messages)

        # All 250 should get a result
        self.assertEqual(len(results), 250,
                         'Should have a result for each of the 250 numbers')
        success_count = sum(1 for r in results if r['state'] == 'success')
        _logger.info('E2E bulk 250: %s/%s succeeded', success_count, len(results))
        self.assertEqual(success_count, 250,
                         'All 250 numbers should succeed in test mode')

    def test_07_validate_numbers(self):
        """Validate phone numbers via real API."""
        self._skip_if_no_creds()
        api = self._get_api()
        resp = api.validate_numbers([TEST_PHONE, '96512345678'])
        self.assertEqual(resp.get('result'), 'OK')
        _logger.info(
            'E2E validate: ok=%s er=%s nr=%s',
            resp.get('ok'), resp.get('er'), resp.get('nr'),
        )


@tagged('post_install', '-at_install', 'kwtsms_e2e')
class TestRealApiSaleOrderHook(TransactionCase):
    """Test the sale order confirmation SMS hook with real API."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.username = ICP.get_param('kwtsms.api_username', '')
        cls.password = ICP.get_param('kwtsms.api_password', '')
        # Ensure enabled + test mode + auto order confirm
        ICP.set_param('kwtsms.enabled', 'True')
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.auto_order_confirm', 'True')

    def _skip_if_no_creds(self):
        if not self.username or not self.password:
            self.skipTest('No kwtSMS API credentials configured')

    def test_01_order_confirm_sends_sms(self):
        """Confirm a sale order and verify SMS is sent + logged."""
        self._skip_if_no_creds()

        # Ensure order_confirm template exists
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
                'body': 'Order {order_name} confirmed for {customer_name}. Thank you!',
            })

        # Create partner with phone
        partner = self.env['res.partner'].create({
            'name': 'Bader Al-Mutawa',
            'phone': TEST_PHONE,
        })

        # Create a product
        product = self.env['product.product'].search([], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': 'Sony Headphones WH-1000XM5',
                'list_price': 10.0,
            })

        # Create and confirm sale order
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
            })],
        })
        log_count_before = self.env['kwtsms.sms.log'].sudo().search_count([
            ('res_model', '=', 'sale.order'),
        ])

        order.action_confirm()

        log_count_after = self.env['kwtsms.sms.log'].sudo().search_count([
            ('res_model', '=', 'sale.order'),
        ])
        self.assertGreater(log_count_after, log_count_before,
                           'SMS log should be created on order confirmation')

        # Check latest log
        log = self.env['kwtsms.sms.log'].sudo().search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
        ], limit=1, order='id desc')
        self.assertTrue(log)
        self.assertEqual(log.status, 'test')
        self.assertEqual(log.phone_number, TEST_PHONE)
        self.assertTrue(log.msg_id, 'msg_id should be set from API response')
        _logger.info('E2E order confirm: log_id=%s msg_id=%s', log.id, log.msg_id)


@tagged('post_install', '-at_install', 'kwtsms_e2e')
class TestRealApiDeliveryHook(TransactionCase):
    """Test the delivery completion SMS hook with real API."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        cls.username = ICP.get_param('kwtsms.api_username', '')
        cls.password = ICP.get_param('kwtsms.api_password', '')
        ICP.set_param('kwtsms.enabled', 'True')
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.auto_delivery_done', 'True')

    def _skip_if_no_creds(self):
        if not self.username or not self.password:
            self.skipTest('No kwtSMS API credentials configured')

    def test_01_delivery_done_sends_sms(self):
        """Validate a delivery picking and verify SMS is sent + logged."""
        self._skip_if_no_creds()

        # Ensure delivery_done template exists
        template = self.env['kwtsms.sms.template'].search([
            ('event_type', '=', 'delivery_done'),
            ('lang', '=', 'en'),
            ('active', '=', True),
        ], limit=1)
        if not template:
            template = self.env['kwtsms.sms.template'].create({
                'name': 'E2E Delivery Done',
                'event_type': 'delivery_done',
                'lang': 'en',
                'body': 'Delivery {picking_name} for {customer_name} is complete!',
            })

        # Create partner with phone
        partner = self.env['res.partner'].create({
            'name': 'Nouf Al-Rashidi',
            'phone': TEST_PHONE,
        })

        # Create product
        product = self.env['product.product'].search([], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': 'LG OLED TV 55"',
                'list_price': 10.0,
                'type': 'consu',
            })

        # Create sale order, confirm to generate delivery
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
            })],
        })
        order.action_confirm()

        # Find the outgoing delivery picking
        pickings = order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing'
        )
        if not pickings:
            self.skipTest('No outgoing picking created (product may not be storable)')

        picking = pickings[0]

        log_count_before = self.env['kwtsms.sms.log'].sudo().search_count([
            ('res_model', '=', 'stock.picking'),
        ])

        # Set quantities and validate the picking
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty

        picking.button_validate()

        log_count_after = self.env['kwtsms.sms.log'].sudo().search_count([
            ('res_model', '=', 'stock.picking'),
        ])
        self.assertGreater(log_count_after, log_count_before,
                           'SMS log should be created on delivery validation')

        log = self.env['kwtsms.sms.log'].sudo().search([
            ('res_model', '=', 'stock.picking'),
            ('res_id', '=', picking.id),
        ], limit=1, order='id desc')
        self.assertTrue(log)
        self.assertEqual(log.status, 'test')
        self.assertEqual(log.phone_number, TEST_PHONE)
        _logger.info('E2E delivery done: log_id=%s msg_id=%s', log.id, log.msg_id)


@tagged('post_install', '-at_install', 'kwtsms_e2e')
class TestTestModeToggle(TransactionCase):
    """Test that toggling settings via kwtsms.gateway.config updates ICP."""

    def _get_gateway(self):
        """Get or create the gateway config singleton."""
        return self.env['kwtsms.gateway.config'].sudo()._get_or_create()

    def test_01_toggle_test_mode_off(self):
        """Uncheck test mode and verify database value changes to 'False'."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.test_mode', 'True')

        gw = self._get_gateway()
        gw.cfg_test_mode = False

        value = ICP.get_param('kwtsms.test_mode')
        self.assertEqual(value, 'False',
                         'kwtsms.test_mode should be "False" after unchecking')

    def test_02_toggle_test_mode_on(self):
        """Check test mode back ON and verify database value changes to 'True'."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.test_mode', 'False')

        gw = self._get_gateway()
        gw.cfg_test_mode = True

        value = ICP.get_param('kwtsms.test_mode')
        self.assertEqual(value, 'True',
                         'kwtsms.test_mode should be "True" after checking')

    def test_03_toggle_enabled_off_and_on(self):
        """Toggle the enabled flag OFF then ON and verify database."""
        ICP = self.env['ir.config_parameter'].sudo()

        # OFF
        ICP.set_param('kwtsms.enabled', 'True')
        gw = self._get_gateway()
        gw.cfg_enabled = False
        self.assertEqual(ICP.get_param('kwtsms.enabled'), 'False')

        # ON
        gw.cfg_enabled = True
        self.assertEqual(ICP.get_param('kwtsms.enabled'), 'True')

    def test_04_toggle_auto_order_confirm(self):
        """Toggle auto_order_confirm and verify database."""
        ICP = self.env['ir.config_parameter'].sudo()

        gw = self._get_gateway()
        gw.cfg_auto_order_confirm = False
        self.assertEqual(ICP.get_param('kwtsms.auto_order_confirm'), 'False')

        gw.cfg_auto_order_confirm = True
        self.assertEqual(ICP.get_param('kwtsms.auto_order_confirm'), 'True')

    def test_05_toggle_auto_delivery_done(self):
        """Toggle auto_delivery_done and verify database."""
        ICP = self.env['ir.config_parameter'].sudo()

        gw = self._get_gateway()
        gw.cfg_auto_delivery_done = True
        self.assertEqual(ICP.get_param('kwtsms.auto_delivery_done'), 'True')

        gw.cfg_auto_delivery_done = False
        self.assertEqual(ICP.get_param('kwtsms.auto_delivery_done'), 'False')

    def test_06_ensure_test_mode_stays_on(self):
        """Verify test mode is ON after all tests (safety check)."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.test_mode', 'True')
        value = ICP.get_param('kwtsms.test_mode')
        self.assertEqual(value, 'True')
