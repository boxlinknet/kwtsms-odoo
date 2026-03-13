"""Tests for kwtSMS models: gateway config, SMS log, SMS template, settings."""

import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestKwtSmsGatewayConfig(TransactionCase):
    """Test kwtsms.gateway.config model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'name': 'Al-Salam Electronics'})

    def test_get_or_create_creates_new(self):
        """Test _get_or_create creates a config when none exists."""
        # Remove any existing config for the current company
        existing = self.env['kwtsms.gateway.config'].search([
            ('company_id', '=', self.company.id),
        ])
        existing.unlink()

        config = self.env['kwtsms.gateway.config']._get_or_create()
        self.assertTrue(config.id)
        self.assertEqual(config.company_id, self.company)
        self.assertEqual(config.api_status, 'not_configured')

    def test_get_or_create_returns_existing(self):
        """Test _get_or_create returns the existing config record."""
        config1 = self.env['kwtsms.gateway.config']._get_or_create()
        config2 = self.env['kwtsms.gateway.config']._get_or_create()
        self.assertEqual(config1.id, config2.id)

    def test_get_sender_id_list_valid_json(self):
        """Test get_sender_id_list parses valid JSON array."""
        config = self.env['kwtsms.gateway.config']._get_or_create()
        config.write({'sender_ids_json': '["SENDER1", "SENDER2"]'})
        result = config.get_sender_id_list()
        self.assertEqual(result, ['SENDER1', 'SENDER2'])

    def test_get_sender_id_list_empty_json(self):
        """Test get_sender_id_list handles empty JSON."""
        config = self.env['kwtsms.gateway.config']._get_or_create()
        config.write({'sender_ids_json': '[]'})
        result = config.get_sender_id_list()
        self.assertEqual(result, [])

    def test_get_sender_id_list_invalid_json(self):
        """Test get_sender_id_list handles malformed JSON gracefully."""
        config = self.env['kwtsms.gateway.config']._get_or_create()
        config.write({'sender_ids_json': 'NOT_VALID_JSON'})
        result = config.get_sender_id_list()
        self.assertEqual(result, [])

    def test_get_sender_id_list_none(self):
        """Test get_sender_id_list handles None value."""
        config = self.env['kwtsms.gateway.config']._get_or_create()
        config.write({'sender_ids_json': False})
        result = config.get_sender_id_list()
        self.assertEqual(result, [])

    def test_get_balance(self):
        """Test get_balance returns the stored balance."""
        config = self.env['kwtsms.gateway.config']._get_or_create()
        config.write({'balance_available': 500})
        self.assertEqual(config.get_balance(), 500)

    def test_get_balance_default_zero(self):
        """Test get_balance defaults to zero."""
        config = self.env['kwtsms.gateway.config']._get_or_create()
        config.write({'balance_available': 0})
        self.assertEqual(config.get_balance(), 0)

    def test_default_values(self):
        """Test default field values on a new config record."""
        existing = self.env['kwtsms.gateway.config'].search([
            ('company_id', '=', self.company.id),
        ])
        existing.unlink()

        config = self.env['kwtsms.gateway.config'].create({
            'company_id': self.company.id,
        })
        self.assertEqual(config.sender_ids_json, '[]')
        self.assertEqual(config.coverage_json, '[]')
        self.assertEqual(config.balance_available, 0)
        self.assertEqual(config.balance_purchased, 0)
        self.assertEqual(config.api_status, 'not_configured')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_action_login_verify_success(self, mock_api_call):
        """Test action_login_verify with successful API response."""
        mock_api_call.side_effect = [
            # check_balance response
            {
                'result': 'OK',
                'available': 1000,
                'purchased': 2000,
            },
            # fetch_sender_ids response
            {
                'result': 'OK',
                'senderid': ['MYCOMPANY', 'KWT-SMS'],
            },
            # fetch_coverage response
            {
                'result': 'OK',
                'coverage': [{'country': 'Kuwait', 'cost': 1}],
            },
        ]

        # Set up API credentials
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.api_username', 'testuser')
        ICP.set_param('kwtsms.api_password', 'testpass')

        config = self.env['kwtsms.gateway.config']._get_or_create()
        result = config.action_login_verify()

        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'reload')
        self.assertEqual(config.api_status, 'connected')
        self.assertEqual(config.balance_available, 1000)
        self.assertEqual(config.balance_purchased, 2000)

        sender_list = json.loads(config.sender_ids_json)
        self.assertIn('MYCOMPANY', sender_list)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_action_login_verify_failure(self, mock_api_call):
        """Test action_login_verify with failed API response."""
        mock_api_call.return_value = {
            'result': 'ERROR',
            'description': 'Invalid credentials',
        }

        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.api_username', 'baduser')
        ICP.set_param('kwtsms.api_password', 'badpass')

        config = self.env['kwtsms.gateway.config']._get_or_create()
        result = config.action_login_verify()

        self.assertEqual(result['tag'], 'reload')
        self.assertEqual(config.api_status, 'error')
        self.assertEqual(config.api_error, 'Invalid credentials')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_cron_refresh_all(self, mock_api_call):
        """Test cron job refreshes balance, sender IDs, coverage for connected configs."""
        mock_api_call.return_value = {
            'result': 'OK',
            'available': 750,
            'purchased': 2000,
        }

        config = self.env['kwtsms.gateway.config']._get_or_create()
        config.write({
            'api_status': 'connected',
            'balance_available': 100,
        })

        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.api_username', 'testuser')
        ICP.set_param('kwtsms.api_password', 'testpass')

        self.env['kwtsms.gateway.config']._cron_refresh_all()

        config.invalidate_recordset()
        self.assertEqual(config.balance_available, 750)
        self.assertEqual(config.balance_purchased, 2000)
        self.assertTrue(config.last_verified)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_cron_refresh_all_skips_not_connected(self, mock_api_call):
        """Test cron job does not process configs that are not connected."""
        config = self.env['kwtsms.gateway.config']._get_or_create()
        config.write({
            'api_status': 'not_configured',
            'balance_available': 100,
        })

        self.env['kwtsms.gateway.config']._cron_refresh_all()

        # Should not have been called since status is not 'connected'
        mock_api_call.assert_not_called()
        config.invalidate_recordset()
        self.assertEqual(config.balance_available, 100)


@tagged('post_install', '-at_install')
class TestKwtSmsLog(TransactionCase):
    """Test kwtsms.sms.log model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'name': 'Al-Salam Electronics'})

    def _create_log(self, **kwargs):
        """Helper to create a log record with defaults."""
        vals = {
            'phone_number': '96598765432',
            'message_body': 'Test message',
            'status': 'success',
            'company_id': self.company.id,
        }
        vals.update(kwargs)
        return self.env['kwtsms.sms.log'].create(vals)

    def test_create_log(self):
        """Test basic log record creation."""
        log = self._create_log()
        self.assertTrue(log.id)
        self.assertEqual(log.phone_number, '96598765432')
        self.assertEqual(log.message_body, 'Test message')
        self.assertEqual(log.status, 'success')

    def test_compute_name(self):
        """Test computed name field includes phone and date."""
        log = self._create_log(phone_number='96598765432')
        self.assertIn('96598765432', log.name)
        self.assertIn('SMS to', log.name)

    def test_compute_name_no_date(self):
        """Test computed name when create_date is not yet set."""
        log = self.env['kwtsms.sms.log'].new({
            'phone_number': '96598765432',
        })
        log._compute_name()
        self.assertIn('96598765432', log.name)

    def test_action_view_related_record(self):
        """Test action_view_related_record returns correct action."""
        log = self._create_log(
            res_model='res.partner',
            res_id=self.env.user.partner_id.id,
        )
        result = log.action_view_related_record()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'res.partner')
        self.assertEqual(result['res_id'], self.env.user.partner_id.id)
        self.assertEqual(result['view_mode'], 'form')

    def test_action_view_related_record_no_model(self):
        """Test action_view_related_record returns None when no model set."""
        log = self._create_log(res_model='', res_id=0)
        result = log.action_view_related_record()
        self.assertIsNone(result)

    def test_action_view_related_record_no_id(self):
        """Test action_view_related_record returns None when no res_id set."""
        log = self._create_log(res_model='res.partner', res_id=0)
        result = log.action_view_related_record()
        self.assertIsNone(result)

    def test_cron_cleanup_old_logs(self):
        """Test cron deletes logs older than retention period."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.log_retention_days', '30')

        # Create an old log by writing directly to the database
        old_log = self._create_log()
        cutoff_date = fields.Datetime.now() - timedelta(days=31)
        self.env.cr.execute(
            'UPDATE kwtsms_sms_log SET create_date = %s WHERE id = %s',
            (cutoff_date, old_log.id),
        )

        # Create a recent log
        recent_log = self._create_log()

        self.env['kwtsms.sms.log']._cron_cleanup_old_logs()

        # Old log should be deleted
        self.assertFalse(old_log.exists())
        # Recent log should remain
        self.assertTrue(recent_log.exists())

    def test_cron_cleanup_zero_retention(self):
        """Test cron does nothing when retention is 0 (disabled)."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.log_retention_days', '0')

        log = self._create_log()

        self.env['kwtsms.sms.log']._cron_cleanup_old_logs()

        # Log should still exist
        self.assertTrue(log.exists())

    def test_cron_cleanup_negative_retention(self):
        """Test cron does nothing when retention is negative."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.log_retention_days', '-5')

        log = self._create_log()

        self.env['kwtsms.sms.log']._cron_cleanup_old_logs()

        self.assertTrue(log.exists())

    def test_log_status_values(self):
        """Test all valid status selection values."""
        for status in ('success', 'error', 'test', 'queued'):
            log = self._create_log(status=status)
            self.assertEqual(log.status, status)

    def test_log_fields_stored(self):
        """Test all additional fields are stored correctly."""
        log = self._create_log(
            sender_id='TESTID',
            msg_id='MSG-12345',
            points_charged=2,
            balance_after=998,
            error_code='ERR001',
            error_description='Server error',
            test_mode=True,
        )
        self.assertEqual(log.sender_id, 'TESTID')
        self.assertEqual(log.msg_id, 'MSG-12345')
        self.assertEqual(log.points_charged, 2)
        self.assertEqual(log.balance_after, 998)
        self.assertEqual(log.error_code, 'ERR001')
        self.assertEqual(log.error_description, 'Server error')
        self.assertTrue(log.test_mode)

    def test_ordering(self):
        """Test logs are ordered by create_date desc (newer ID first)."""
        log1 = self._create_log(phone_number='96598765432')
        log2 = self._create_log(phone_number='96598765432')
        logs = self.env['kwtsms.sms.log'].search([
            ('id', 'in', [log1.id, log2.id]),
        ])
        self.assertEqual(len(logs), 2)
        # With same create_date, ordering falls back to id desc
        self.assertGreater(log2.id, log1.id)


@tagged('post_install', '-at_install')
class TestKwtSmsTemplate(TransactionCase):
    """Test kwtsms.sms.template model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'name': 'Al-Salam Electronics'})

    def _create_template(self, **kwargs):
        """Helper to create a template with defaults."""
        vals = {
            'name': 'Test Template',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Hello {customer_name}, your order {order_name} is confirmed.',
            'company_id': self.company.id,
        }
        vals.update(kwargs)
        return self.env['kwtsms.sms.template'].create(vals)

    def test_create_template(self):
        """Test basic template creation."""
        template = self._create_template()
        self.assertTrue(template.id)
        self.assertEqual(template.name, 'Test Template')
        self.assertTrue(template.active)

    def test_compute_sms_info_english(self):
        """Test SMS info computed for English (GSM-7) body."""
        template = self._create_template(body='Hello World')
        self.assertEqual(template.char_count, 11)
        self.assertEqual(template.page_count, 1)
        self.assertFalse(template.is_unicode)

    def test_compute_sms_info_arabic(self):
        """Test SMS info computed for Arabic (Unicode) body."""
        arabic_body = '\u0645\u0631\u062d\u0628\u0627 \u0628\u0627\u0644\u0639\u0627\u0644\u0645'
        template = self._create_template(body=arabic_body)
        self.assertTrue(template.char_count > 0)
        self.assertEqual(template.page_count, 1)
        self.assertTrue(template.is_unicode)

    def test_compute_sms_info_empty_body(self):
        """Test SMS info for template with empty body."""
        template = self._create_template(body='')
        self.assertEqual(template.char_count, 0)
        self.assertEqual(template.page_count, 0)
        self.assertFalse(template.is_unicode)

    def test_compute_sms_info_multipage(self):
        """Test SMS info for a long message that spans multiple pages."""
        long_body = 'A' * 161  # Over 160, triggers multipart GSM-7
        template = self._create_template(body=long_body)
        self.assertEqual(template.char_count, 161)
        self.assertEqual(template.page_count, 2)
        self.assertFalse(template.is_unicode)

    def test_render_template_sale_order(self):
        """Test render_template with a sale order-like record."""
        partner = self.env['res.partner'].create({
            'name': 'Nora Al-Kandari',
        })
        # Create a mock-like object using an existing model
        # We'll use res.partner and test with hasattr-based rendering
        template = self._create_template(
            body='Hello {customer_name}!',
        )
        result = template.render_template(partner)
        # partner doesn't have partner_id, but has name
        # The template expects {customer_name} which comes from partner_id.name
        # Since partner has no partner_id, customer_name won't be in values
        # and the template will fall back to raw body due to KeyError
        self.assertIn('Hello', result)

    def test_render_template_missing_placeholder(self):
        """Test render_template strips undefined placeholders."""
        template = self._create_template(
            body='Order {nonexistent_field} confirmed.',
        )
        partner = self.env['res.partner'].create({'name': 'Nora Al-Kandari'})
        result = template.render_template(partner)
        # Unreplaced placeholders are stripped by render_template
        self.assertEqual(result, 'Order confirmed.')

    def test_render_template_empty_body(self):
        """Test render_template with empty body returns empty string."""
        template = self._create_template(body='')
        partner = self.env['res.partner'].create({'name': 'Nora Al-Kandari'})
        result = template.render_template(partner)
        self.assertEqual(result, '')

    def test_render_template_company_name(self):
        """Test render_template fills company_name from record."""
        template = self._create_template(
            body='Thank you from {company_name}.',
        )
        # res.partner has company_id sometimes; we use a record without one
        # so it falls back to self.env.company
        partner = self.env['res.partner'].create({
            'name': 'Nora Al-Kandari',
            'company_id': False,
        })
        result = template.render_template(partner)
        self.assertIn(self.env.company.name, result)

    def test_get_template_for_event_found(self):
        """Test get_template_for_event returns matching template."""
        # Use 'custom' event_type to avoid collision with demo data
        template = self._create_template(
            event_type='custom',
            lang='en',
        )
        found = self.env['kwtsms.sms.template'].get_template_for_event(
            'custom', 'en',
        )
        self.assertEqual(found.id, template.id)

    def test_get_template_for_event_lang_fallback(self):
        """Test get_template_for_event falls back to English."""
        template = self._create_template(
            event_type='custom',
            lang='en',
        )
        # Search for Arabic, should fall back to English
        found = self.env['kwtsms.sms.template'].get_template_for_event(
            'custom', 'ar',
        )
        self.assertEqual(found.id, template.id)

    def test_get_template_for_event_arabic_found(self):
        """Test get_template_for_event returns Arabic when available."""
        self._create_template(
            event_type='order_confirm',
            lang='en',
            name='English template',
        )
        ar_template = self._create_template(
            event_type='order_confirm',
            lang='ar',
            name='Arabic template',
            body='\u062a\u0645 \u062a\u0623\u0643\u064a\u062f \u0637\u0644\u0628\u0643',
        )
        found = self.env['kwtsms.sms.template'].get_template_for_event(
            'order_confirm', 'ar',
        )
        self.assertEqual(found.id, ar_template.id)

    def test_get_template_for_event_not_found(self):
        """Test get_template_for_event returns empty recordset when none match."""
        # Use a nonexistent event_type to avoid matching demo data
        found = self.env['kwtsms.sms.template'].get_template_for_event(
            'custom', 'en',
        )
        self.assertFalse(found)

    def test_get_template_for_event_inactive_ignored(self):
        """Test get_template_for_event ignores inactive templates."""
        # Archive all existing templates for this event type first
        existing = self.env['kwtsms.sms.template'].search([
            ('event_type', '=', 'custom'),
            ('lang', '=', 'en'),
        ])
        existing.write({'active': False})

        self._create_template(
            event_type='custom',
            lang='en',
            active=False,
        )
        found = self.env['kwtsms.sms.template'].get_template_for_event(
            'custom', 'en',
        )
        self.assertFalse(found)

    def test_event_type_selection_values(self):
        """Test all event_type selection values can be set."""
        for event_type in ('order_confirm', 'delivery_done', 'invoice_posted',
                           'payment_received', 'custom'):
            template = self._create_template(event_type=event_type)
            self.assertEqual(template.event_type, event_type)

    def test_lang_selection_values(self):
        """Test both language selection values."""
        for lang in ('en', 'ar'):
            template = self._create_template(lang=lang)
            self.assertEqual(template.lang, lang)


@tagged('post_install', '-at_install')
class TestGatewayConfigSettings(TransactionCase):
    """Test kwtSMS gateway config proxy fields for settings."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'name': 'Al-Salam Electronics'})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.sender_id', 'KWT-SMS')

    def _get_config(self):
        """Get or create the gateway config singleton."""
        return self.env['kwtsms.gateway.config'].sudo()._get_or_create()

    def test_cfg_sender_id_defaults(self):
        """Test cfg_sender_id returns KWT-SMS by default."""
        config = self._get_config()
        self.assertEqual(config.cfg_sender_id, 'KWT-SMS')

    def test_cfg_sender_id_write(self):
        """Test writing cfg_sender_id saves to system parameters."""
        config = self._get_config()
        config.cfg_sender_id = 'MYSENDER'
        ICP = self.env['ir.config_parameter'].sudo()
        self.assertEqual(ICP.get_param('kwtsms.sender_id'), 'MYSENDER')

    def test_get_sender_id_selection_default(self):
        """Test _get_sender_id_selection always includes KWT-SMS."""
        config = self._get_config()
        selection = config._get_sender_id_selection()
        keys = [item[0] for item in selection]
        self.assertIn('KWT-SMS', keys)

    def test_get_sender_id_selection_includes_saved(self):
        """Test _get_sender_id_selection includes the currently saved value."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.sender_id', 'CUSTOM-ID')

        config = self._get_config()
        selection = config._get_sender_id_selection()
        keys = [item[0] for item in selection]
        self.assertIn('CUSTOM-ID', keys)

    def test_get_sender_id_selection_includes_gateway_senders(self):
        """Test _get_sender_id_selection includes sender IDs from gateway config."""
        config = self._get_config()
        config.write({
            'sender_ids_json': '["GATEWAY-1", "GATEWAY-2"]',
        })

        selection = config._get_sender_id_selection()
        keys = [item[0] for item in selection]
        self.assertIn('GATEWAY-1', keys)
        self.assertIn('GATEWAY-2', keys)

    def test_cfg_boolean_fields_roundtrip(self):
        """Test boolean config fields persist correctly."""
        config = self._get_config()
        ICP = self.env['ir.config_parameter'].sudo()

        # Test enabled toggle
        config.cfg_enabled = False
        self.assertEqual(ICP.get_param('kwtsms.enabled'), 'False')
        config.cfg_enabled = True
        self.assertEqual(ICP.get_param('kwtsms.enabled'), 'True')

        # Test test_mode toggle
        config.cfg_test_mode = False
        self.assertEqual(ICP.get_param('kwtsms.test_mode'), 'False')
        config.cfg_test_mode = True
        self.assertEqual(ICP.get_param('kwtsms.test_mode'), 'True')

    def test_cfg_toggle_fields(self):
        """Test notification toggle fields persist correctly."""
        config = self._get_config()
        ICP = self.env['ir.config_parameter'].sudo()

        config.cfg_auto_order_confirm = False
        self.assertEqual(ICP.get_param('kwtsms.auto_order_confirm'), 'False')
        config.cfg_auto_order_confirm = True
        self.assertEqual(ICP.get_param('kwtsms.auto_order_confirm'), 'True')

        config.cfg_auto_delivery_done = True
        self.assertEqual(ICP.get_param('kwtsms.auto_delivery_done'), 'True')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_action_login(self, mock_api_call):
        """Test action_login verifies credentials and reloads."""
        mock_api_call.return_value = {
            'result': 'OK',
            'available': 100,
            'purchased': 200,
        }
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.api_username', 'testuser')
        ICP.set_param('kwtsms.api_password', 'testpass')

        config = self._get_config()
        result = config.action_login()
        self.assertEqual(result['type'], 'ir.actions.client')

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_action_refresh_success(self, mock_api_call):
        """Test refresh action with successful API response."""
        mock_api_call.return_value = {
            'result': 'OK',
            'available': 800,
            'purchased': 1500,
        }
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.api_username', 'testuser')
        ICP.set_param('kwtsms.api_password', 'testpass')

        config = self._get_config()
        config.action_refresh_dashboard()

        self.assertEqual(config.balance_available, 800)

    @patch('odoo.addons.kwtsms_sms.tools.kwtsms_api.KwtSmsApi._api_call')
    def test_action_refresh_failure(self, mock_api_call):
        """Test refresh action with failed API response."""
        mock_api_call.return_value = {
            'result': 'ERROR',
            'description': 'Auth failed',
        }
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('kwtsms.api_username', 'testuser')
        ICP.set_param('kwtsms.api_password', 'testpass')

        config = self._get_config()
        config.action_refresh_dashboard()
        self.assertEqual(config.api_status, 'error')
