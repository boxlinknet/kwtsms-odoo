"""Tests for kwtSMS security: access rights, record rules, groups."""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestKwtSmsAccessRights(TransactionCase):
    """Test access rights defined in ir.model.access.csv."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_user = cls.env.ref('base.group_user')
        cls.group_system = cls.env.ref('base.group_system')
        cls.group_manager = cls.env.ref('kwtsms_sms.group_kwtsms_manager')

        # Create test users with different permission levels
        cls.basic_user = cls.env['res.users'].create({
            'name': 'Layla Al-Hamad',
            'login': 'layla@alsalam-electronics.kw',
            'email': 'layla@alsalam-electronics.kw',
            'group_ids': [(6, 0, [cls.group_user.id])],
        })
        cls.manager_user = cls.env['res.users'].create({
            'name': 'Tariq Al-Bloushi',
            'login': 'tariq@alsalam-electronics.kw',
            'email': 'tariq@alsalam-electronics.kw',
            'group_ids': [(6, 0, [cls.group_manager.id])],
        })
        cls.system_user = cls.env['res.users'].create({
            'name': 'Fahad Al-Kandari',
            'login': 'fahad@alsalam-electronics.kw',
            'email': 'fahad@alsalam-electronics.kw',
            'group_ids': [(6, 0, [cls.group_system.id])],
        })

    # ---------------------------------------------------------------
    # kwtsms.gateway.config access rights
    # ---------------------------------------------------------------

    def test_gateway_config_user_can_read(self):
        """Test basic users can read gateway config."""
        config = self.env['kwtsms.gateway.config'].sudo().create({
            'company_id': self.env.company.id,
        })
        # Should not raise
        config.with_user(self.basic_user).read(['api_status'])

    def test_gateway_config_user_cannot_write(self):
        """Test basic users cannot write to gateway config."""
        config = self.env['kwtsms.gateway.config'].sudo().create({
            'company_id': self.env.company.id,
        })
        with self.assertRaises(AccessError):
            config.with_user(self.basic_user).write({'balance_available': 999})

    def test_gateway_config_user_cannot_create(self):
        """Test basic users cannot create gateway config."""
        with self.assertRaises(AccessError):
            self.env['kwtsms.gateway.config'].with_user(self.basic_user).create({
                'company_id': self.env.company.id,
            })

    def test_gateway_config_user_cannot_unlink(self):
        """Test basic users cannot delete gateway config."""
        config = self.env['kwtsms.gateway.config'].sudo().create({
            'company_id': self.env.company.id,
        })
        with self.assertRaises(AccessError):
            config.with_user(self.basic_user).unlink()

    def test_gateway_config_system_full_access(self):
        """Test system users have full CRUD on gateway config."""
        # Create
        config = self.env['kwtsms.gateway.config'].with_user(self.system_user).create({
            'company_id': self.env.company.id,
        })
        # Read
        config.with_user(self.system_user).read(['api_status'])
        # Write
        config.with_user(self.system_user).write({'balance_available': 500})
        # Unlink
        config.with_user(self.system_user).unlink()

    # ---------------------------------------------------------------
    # kwtsms.sms.log access rights
    # ---------------------------------------------------------------

    def test_log_user_can_read(self):
        """Test basic users can read SMS logs."""
        log = self.env['kwtsms.sms.log'].sudo().create({
            'phone_number': '96598765432',
            'message_body': 'Test message',
            'status': 'success',
            'company_id': self.env.company.id,
        })
        # Should not raise
        log.with_user(self.basic_user).read(['phone_number'])

    def test_log_user_cannot_write(self):
        """Test basic users cannot write to SMS logs."""
        log = self.env['kwtsms.sms.log'].sudo().create({
            'phone_number': '96598765432',
            'message_body': 'Test message',
            'status': 'success',
            'company_id': self.env.company.id,
        })
        with self.assertRaises(AccessError):
            log.with_user(self.basic_user).write({'status': 'error'})

    def test_log_user_cannot_create(self):
        """Test basic users cannot create SMS logs."""
        with self.assertRaises(AccessError):
            self.env['kwtsms.sms.log'].with_user(self.basic_user).create({
                'phone_number': '96598765432',
                'message_body': 'Test',
                'status': 'success',
            })

    def test_log_user_cannot_unlink(self):
        """Test basic users cannot delete SMS logs."""
        log = self.env['kwtsms.sms.log'].sudo().create({
            'phone_number': '96598765432',
            'message_body': 'Test message',
            'status': 'success',
            'company_id': self.env.company.id,
        })
        with self.assertRaises(AccessError):
            log.with_user(self.basic_user).unlink()

    def test_log_system_full_access(self):
        """Test system users have full CRUD on SMS logs."""
        log = self.env['kwtsms.sms.log'].with_user(self.system_user).create({
            'phone_number': '96598765432',
            'message_body': 'Test message',
            'status': 'success',
            'company_id': self.env.company.id,
        })
        log.with_user(self.system_user).read(['phone_number'])
        log.with_user(self.system_user).write({'status': 'error'})
        log.with_user(self.system_user).unlink()

    # ---------------------------------------------------------------
    # kwtsms.sms.template access rights
    # ---------------------------------------------------------------

    def test_template_user_can_read(self):
        """Test basic users can read SMS templates."""
        template = self.env['kwtsms.sms.template'].sudo().create({
            'name': 'Test Template',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Test body',
            'company_id': self.env.company.id,
        })
        # Should not raise
        template.with_user(self.basic_user).read(['name'])

    def test_template_user_cannot_write(self):
        """Test basic users cannot write to SMS templates."""
        template = self.env['kwtsms.sms.template'].sudo().create({
            'name': 'Test Template',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Test body',
            'company_id': self.env.company.id,
        })
        with self.assertRaises(AccessError):
            template.with_user(self.basic_user).write({'name': 'Modified'})

    def test_template_user_cannot_create(self):
        """Test basic users cannot create SMS templates."""
        with self.assertRaises(AccessError):
            self.env['kwtsms.sms.template'].with_user(self.basic_user).create({
                'name': 'Unauthorized',
                'event_type': 'custom',
                'lang': 'en',
                'body': 'Test',
            })

    def test_template_manager_can_read(self):
        """Test managers can read SMS templates."""
        template = self.env['kwtsms.sms.template'].sudo().create({
            'name': 'Test Template',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Test body',
            'company_id': self.env.company.id,
        })
        template.with_user(self.manager_user).read(['name'])

    def test_template_manager_can_write(self):
        """Test managers can write SMS templates."""
        template = self.env['kwtsms.sms.template'].sudo().create({
            'name': 'Test Template',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Test body',
            'company_id': self.env.company.id,
        })
        template.with_user(self.manager_user).write({'name': 'Updated Name'})
        self.assertEqual(template.name, 'Updated Name')

    def test_template_manager_can_create(self):
        """Test managers can create SMS templates."""
        template = self.env['kwtsms.sms.template'].with_user(
            self.manager_user,
        ).create({
            'name': 'Manager Template',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Manager body',
            'company_id': self.env.company.id,
        })
        self.assertTrue(template.id)

    def test_template_manager_cannot_unlink(self):
        """Test managers cannot delete SMS templates (only system can)."""
        template = self.env['kwtsms.sms.template'].sudo().create({
            'name': 'Test Template',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Test body',
            'company_id': self.env.company.id,
        })
        with self.assertRaises(AccessError):
            template.with_user(self.manager_user).unlink()

    def test_template_system_full_access(self):
        """Test system users have full CRUD on SMS templates."""
        template = self.env['kwtsms.sms.template'].with_user(
            self.system_user,
        ).create({
            'name': 'System Template',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'System body',
            'company_id': self.env.company.id,
        })
        template.with_user(self.system_user).read(['name'])
        template.with_user(self.system_user).write({'name': 'Updated'})
        template.with_user(self.system_user).unlink()

    # ---------------------------------------------------------------
    # kwtsms.sms.compose wizard access rights
    # ---------------------------------------------------------------

    def test_compose_user_cannot_create(self):
        """Test basic users without manager group cannot create compose wizard."""
        with self.assertRaises(AccessError):
            self.env['kwtsms.sms.compose'].with_user(self.basic_user).create({
                'phone': '96598765432',
                'message': 'Test',
            })

    def test_compose_manager_can_create(self):
        """Test managers can create compose wizard."""
        wizard = self.env['kwtsms.sms.compose'].with_user(
            self.manager_user,
        ).create({
            'phone': '96598765432',
            'message': 'Hello from manager',
        })
        self.assertTrue(wizard.id)

    def test_compose_system_can_create(self):
        """Test system users can create compose wizard."""
        wizard = self.env['kwtsms.sms.compose'].with_user(
            self.system_user,
        ).create({
            'phone': '96598765432',
            'message': 'Hello from system',
        })
        self.assertTrue(wizard.id)


@tagged('post_install', '-at_install')
class TestKwtSmsRecordRules(TransactionCase):
    """Test record rules for multi-company isolation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create two companies
        cls.company_a = cls.env['res.company'].create({
            'name': 'Al-Salam Electronics',
        })
        cls.company_b = cls.env['res.company'].create({
            'name': 'Gulf Star Trading',
        })

        # Create users in each company
        cls.user_a = cls.env['res.users'].create({
            'name': 'Nasser Al-Otaibi',
            'login': 'nasser@alsalam-electronics.kw',
            'email': 'nasser@alsalam-electronics.kw',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.user_b = cls.env['res.users'].create({
            'name': 'Amina Al-Fadhli',
            'login': 'amina@gulfstar-trading.kw',
            'email': 'amina@gulfstar-trading.kw',
            'company_id': cls.company_b.id,
            'company_ids': [(6, 0, [cls.company_b.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

    def test_log_company_isolation(self):
        """Test users can only see logs from their own company."""
        log_a = self.env['kwtsms.sms.log'].sudo().create({
            'phone_number': '96598765432',
            'message_body': 'Company A message',
            'status': 'success',
            'company_id': self.company_a.id,
        })
        log_b = self.env['kwtsms.sms.log'].sudo().create({
            'phone_number': '96598765432',
            'message_body': 'Company B message',
            'status': 'success',
            'company_id': self.company_b.id,
        })

        # User A should see Company A logs
        logs_a = self.env['kwtsms.sms.log'].with_user(self.user_a).search([])
        self.assertIn(log_a.id, logs_a.ids)
        self.assertNotIn(log_b.id, logs_a.ids)

        # User B should see Company B logs
        logs_b = self.env['kwtsms.sms.log'].with_user(self.user_b).search([])
        self.assertIn(log_b.id, logs_b.ids)
        self.assertNotIn(log_a.id, logs_b.ids)

    def test_log_no_company_visible_to_all(self):
        """Test log records with no company are visible to all users."""
        log_global = self.env['kwtsms.sms.log'].sudo().create({
            'phone_number': '96598765432',
            'message_body': 'Global message',
            'status': 'success',
            'company_id': False,
        })

        logs_a = self.env['kwtsms.sms.log'].with_user(self.user_a).search([])
        self.assertIn(log_global.id, logs_a.ids)

        logs_b = self.env['kwtsms.sms.log'].with_user(self.user_b).search([])
        self.assertIn(log_global.id, logs_b.ids)

    def test_template_company_isolation(self):
        """Test users can only see templates from their own company."""
        tmpl_a = self.env['kwtsms.sms.template'].sudo().create({
            'name': 'Template A',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Company A',
            'company_id': self.company_a.id,
        })
        tmpl_b = self.env['kwtsms.sms.template'].sudo().create({
            'name': 'Template B',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Company B',
            'company_id': self.company_b.id,
        })

        # User A sees Company A template
        templates_a = self.env['kwtsms.sms.template'].with_user(
            self.user_a,
        ).search([])
        self.assertIn(tmpl_a.id, templates_a.ids)
        self.assertNotIn(tmpl_b.id, templates_a.ids)

        # User B sees Company B template
        templates_b = self.env['kwtsms.sms.template'].with_user(
            self.user_b,
        ).search([])
        self.assertIn(tmpl_b.id, templates_b.ids)
        self.assertNotIn(tmpl_a.id, templates_b.ids)

    def test_template_no_company_visible_to_all(self):
        """Test template records with no company are visible to all users."""
        tmpl_global = self.env['kwtsms.sms.template'].sudo().create({
            'name': 'Global Template',
            'event_type': 'custom',
            'lang': 'en',
            'body': 'Global',
            'company_id': False,
        })

        templates_a = self.env['kwtsms.sms.template'].with_user(
            self.user_a,
        ).search([])
        self.assertIn(tmpl_global.id, templates_a.ids)

        templates_b = self.env['kwtsms.sms.template'].with_user(
            self.user_b,
        ).search([])
        self.assertIn(tmpl_global.id, templates_b.ids)

    def test_gateway_config_company_isolation(self):
        """Test users can only see gateway config for their own company."""
        config_a = self.env['kwtsms.gateway.config'].sudo().create({
            'company_id': self.company_a.id,
        })
        config_b = self.env['kwtsms.gateway.config'].sudo().create({
            'company_id': self.company_b.id,
        })

        # User A sees Company A config
        configs_a = self.env['kwtsms.gateway.config'].with_user(
            self.user_a,
        ).search([])
        self.assertIn(config_a.id, configs_a.ids)
        self.assertNotIn(config_b.id, configs_a.ids)

        # User B sees Company B config
        configs_b = self.env['kwtsms.gateway.config'].with_user(
            self.user_b,
        ).search([])
        self.assertIn(config_b.id, configs_b.ids)
        self.assertNotIn(config_a.id, configs_b.ids)


@tagged('post_install', '-at_install')
class TestKwtSmsManagerGroup(TransactionCase):
    """Test kwtSMS Manager group membership and implied groups."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_manager = cls.env.ref('kwtsms_sms.group_kwtsms_manager')
        cls.group_user = cls.env.ref('base.group_user')

    def test_manager_implies_user(self):
        """Test that kwtSMS Manager group implies base.group_user."""
        self.assertIn(
            self.group_user.id,
            self.group_manager.implied_ids.ids,
        )

    def test_manager_user_has_user_group(self):
        """Test that a user in manager group also has user group."""
        user = self.env['res.users'].create({
            'name': 'Jassim Al-Hajri',
            'login': 'jassim@alsalam-electronics.kw',
            'email': 'jassim@alsalam-electronics.kw',
            'group_ids': [(6, 0, [self.group_manager.id])],
        })
        self.assertTrue(user.has_group('base.group_user'))
        self.assertTrue(user.has_group('kwtsms_sms.group_kwtsms_manager'))
