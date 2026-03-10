# kwtSMS Gateway for Odoo
# Integrates kwtSMS API with Odoo's SMS framework

from . import models
from . import tools
from . import controllers
from . import wizard


def _post_init_hook(env):
    """Mark all event-linked templates as system templates.

    Runs on install and upgrade to ensure noupdate records get is_system=True.
    """
    env.cr.execute("""
        UPDATE kwtsms_sms_template
        SET is_system = TRUE
        WHERE event_type != 'custom' AND (is_system IS NULL OR is_system = FALSE)
    """)
