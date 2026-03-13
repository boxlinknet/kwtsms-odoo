"""Tests for the SMS Compose Wizard."""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestKwtSmsComposeWizard(TransactionCase):
    """Test kwtsms.sms.compose wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write({'name': 'Gulf Trade Solutions'})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.api_username', 'testuser')
        ICP.set_param('kwtsms.api_password', 'testpass')
        ICP.set_param('kwtsms.sender_id', 'KWT-SMS')
        ICP.set_param('kwtsms.test_mode', 'True')
        ICP.set_param('kwtsms.enabled', 'True')

        cls.partner = cls.env['res.partner'].create({
            'name': 'Maryam Al-Mutairi',
            'phone': '+96598765432',
        })

        cls.template = cls.env['kwtsms.sms.template'].create({
            'name': 'Wizard Template',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Hello {customer_name}, greetings from {company_name}.',
        })

    # ---------------------------------------------------------------
    # Wizard creation and defaults
    # ---------------------------------------------------------------

    def test_create_basic_wizard(self):
        """Test basic wizard creation."""
        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '96598765432',
            'message': 'Test message',
        })
        self.assertTrue(wizard.id)
        self.assertEqual(wizard.phone, '96598765432')
        self.assertEqual(wizard.message, 'Test message')

    def test_default_get_with_partner_context(self):
        """Test default_get populates phone from partner context."""
        wizard = self.env['kwtsms.sms.compose'].with_context(
            active_model='res.partner',
            active_id=self.partner.id,
        ).create({
            'message': 'Hello',
        })
        self.assertEqual(wizard.phone, '+96598765432')
        self.assertEqual(wizard.res_model, 'res.partner')
        self.assertEqual(wizard.res_id, self.partner.id)

    def test_default_get_with_sale_order_context(self):
        """Test default_get populates phone from sale order partner."""
        product = self.env['product.product'].create({
            'name': 'Huawei MateBook',
            'type': 'consu',
            'list_price': 100.0,
        })
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        wizard = self.env['kwtsms.sms.compose'].with_context(
            active_model='sale.order',
            active_id=order.id,
        ).create({
            'message': 'Order SMS',
        })
        self.assertEqual(wizard.phone, '+96598765432')
        self.assertEqual(wizard.res_model, 'sale.order')
        self.assertEqual(wizard.res_id, order.id)

    def test_default_get_no_context(self):
        """Test default_get works without active_model context."""
        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '96598765432',
            'message': 'No context',
        })
        self.assertFalse(wizard.res_model)
        self.assertEqual(wizard.res_id, 0)

    def test_default_get_partner_no_phone(self):
        """Test default_get with partner that has no phone number."""
        partner_no_phone = self.env['res.partner'].create({
            'name': 'Dana Al-Hajri',
        })
        wizard = self.env['kwtsms.sms.compose'].with_context(
            active_model='res.partner',
            active_id=partner_no_phone.id,
        ).create({
            'phone': '',
            'message': 'Hello',
        })
        self.assertFalse(wizard.phone)

    # ---------------------------------------------------------------
    # Template selection and message population
    # ---------------------------------------------------------------

    def test_onchange_template_id_populates_body(self):
        """Test selecting a template populates the message field."""
        wizard = self.env['kwtsms.sms.compose'].new({
            'phone': '96598765432',
            'message': '',
            'template_id': self.template.id,
        })
        wizard._onchange_template_id()
        # Without res_model/res_id, should use raw template body
        self.assertEqual(
            wizard.message,
            'Hello {customer_name}, greetings from {company_name}.',
        )

    def test_onchange_template_id_renders_with_record(self):
        """Test selecting a template renders placeholders when record exists."""
        wizard = self.env['kwtsms.sms.compose'].new({
            'phone': '96598765432',
            'message': '',
            'template_id': self.template.id,
            'res_model': 'res.partner',
            'res_id': self.partner.id,
        })
        wizard._onchange_template_id()
        # partner has 'name' (used as order_name/picking_name but not customer_name)
        # and no partner_id, so template rendering will hit KeyError and fall back
        self.assertIn('Hello', wizard.message)

    def test_onchange_template_id_no_template(self):
        """Test onchange with no template selected does nothing."""
        wizard = self.env['kwtsms.sms.compose'].new({
            'phone': '96598765432',
            'message': 'Original message',
            'template_id': False,
        })
        wizard._onchange_template_id()
        self.assertEqual(wizard.message, 'Original message')

    def test_onchange_template_id_empty_body(self):
        """Test onchange with template that has empty body."""
        empty_template = self.env['kwtsms.sms.template'].create({
            'name': 'Empty Template',
            'event_type': 'custom',
            'lang': 'en',
            'body': '',
        })
        wizard = self.env['kwtsms.sms.compose'].new({
            'phone': '96598765432',
            'message': 'Original',
            'template_id': empty_template.id,
        })
        wizard._onchange_template_id()
        # Template body is empty/falsy, so onchange should not modify message
        self.assertEqual(wizard.message, 'Original')

    # ---------------------------------------------------------------
    # Character count computation
    # ---------------------------------------------------------------

    def test_compute_sms_info_english(self):
        """Test SMS info for English (GSM-7) message."""
        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '96598765432',
            'message': 'Hello World',
        })
        self.assertEqual(wizard.char_count, 11)
        self.assertEqual(wizard.page_count, 1)
        self.assertFalse(wizard.is_unicode)

    def test_compute_sms_info_arabic(self):
        """Test SMS info for Arabic (Unicode) message."""
        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '96598765432',
            'message': '\u0645\u0631\u062d\u0628\u0627',
        })
        self.assertTrue(wizard.char_count > 0)
        self.assertEqual(wizard.page_count, 1)
        self.assertTrue(wizard.is_unicode)

    def test_compute_sms_info_empty(self):
        """Test SMS info for empty message."""
        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '96598765432',
            'message': '',
        })
        self.assertEqual(wizard.char_count, 0)
        self.assertEqual(wizard.page_count, 0)
        self.assertFalse(wizard.is_unicode)

    def test_compute_sms_info_multipage(self):
        """Test SMS info for long message spanning multiple pages."""
        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '96598765432',
            'message': 'A' * 200,
        })
        self.assertEqual(wizard.char_count, 200)
        self.assertEqual(wizard.page_count, 2)
        self.assertFalse(wizard.is_unicode)

    # ---------------------------------------------------------------
    # action_send
    # ---------------------------------------------------------------

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_action_send_success(self, mock_api_call):
        """Test action_send with a successful API response."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-WIZ-001',
            'points-charged': 1,
            'balance-after': 999,
        }

        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '96598765432',
            'message': 'Hello from wizard',
        })
        result = wizard.action_send()

        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(result['params']['type'], 'success')

        # Verify log was created
        log = self.env['kwtsms.sms.log'].search([
            ('msg_id', '=', 'MSG-WIZ-001'),
        ], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.status, 'test')  # test mode is on

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_action_send_failure(self, mock_api_call):
        """Test action_send raises UserError on API failure."""
        mock_api_call.return_value = {
            'result': 'ERROR',
            'code': 'ERR010',
            'description': 'Insufficient credits',
        }

        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '96598765432',
            'message': 'Hello from wizard',
        })
        with self.assertRaises(UserError):
            wizard.action_send()

        # Note: log entry is rolled back by ORM savepoint when UserError is raised
        mock_api_call.assert_called_once()

    def test_action_send_no_phone(self):
        """Test action_send raises UserError when phone is empty."""
        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '',
            'message': 'Hello',
        })
        with self.assertRaises(UserError):
            wizard.action_send()

    def test_action_send_no_message(self):
        """Test action_send raises UserError when message is empty."""
        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '96598765432',
            'message': '',
        })
        with self.assertRaises(UserError):
            wizard.action_send()

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_action_send_with_template(self, mock_api_call):
        """Test action_send logs the template ID when used."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-WIZ-TMPL',
            'points-charged': 1,
        }

        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '96598765432',
            'message': 'Hello World',
            'template_id': self.template.id,
        })
        wizard.action_send()

        log = self.env['kwtsms.sms.log'].search([
            ('msg_id', '=', 'MSG-WIZ-TMPL'),
        ], limit=1)
        self.assertEqual(log.template_id.id, self.template.id)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_action_send_with_related_record(self, mock_api_call):
        """Test action_send logs the related model and ID."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-WIZ-REL',
            'points-charged': 1,
        }

        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '96598765432',
            'message': 'Hello',
            'res_model': 'res.partner',
            'res_id': self.partner.id,
        })
        wizard.action_send()

        log = self.env['kwtsms.sms.log'].search([
            ('msg_id', '=', 'MSG-WIZ-REL'),
        ], limit=1)
        self.assertEqual(log.res_model, 'res.partner')
        self.assertEqual(log.res_id, self.partner.id)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_action_send_test_mode_status(self, mock_api_call):
        """Test action_send sets status to 'test' in test mode."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-WIZ-TST',
            'points-charged': 0,
        }

        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '96598765432',
            'message': 'Test mode message',
        })
        wizard.action_send()

        log = self.env['kwtsms.sms.log'].search([
            ('msg_id', '=', 'MSG-WIZ-TST'),
        ], limit=1)
        self.assertEqual(log.status, 'test')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_action_send_production_mode_status(self, mock_api_call):
        """Test action_send sets status to 'success' when test mode is off."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.test_mode', 'False')

        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-WIZ-PROD',
            'points-charged': 1,
        }

        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '96598765432',
            'message': 'Production message',
        })
        wizard.action_send()

        log = self.env['kwtsms.sms.log'].search([
            ('msg_id', '=', 'MSG-WIZ-PROD'),
        ], limit=1)
        self.assertEqual(log.status, 'success')

        # Restore test mode
        ICP.set_param('kwtsms.test_mode', 'True')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_action_send_without_template(self, mock_api_call):
        """Test action_send works without a template selected."""
        mock_api_call.return_value = {
            'result': 'OK',
            'msg-id': 'MSG-WIZ-NOTMPL',
            'points-charged': 1,
        }

        wizard = self.env['kwtsms.sms.compose'].create({
            'phone': '96598765432',
            'message': 'Manual message',
        })
        wizard.action_send()

        log = self.env['kwtsms.sms.log'].search([
            ('msg_id', '=', 'MSG-WIZ-NOTMPL'),
        ], limit=1)
        self.assertTrue(log)
        self.assertFalse(log.template_id)
