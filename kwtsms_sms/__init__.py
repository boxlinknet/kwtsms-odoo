# kwtSMS Gateway for Odoo
# Integrates kwtSMS API with Odoo's SMS framework

from . import models
from . import tools
from . import controllers
from . import wizard


def _post_init_hook(env):
    """Fix system templates on install.

    Marks event-linked templates as system and migrates #..# notation to {..}.
    """
    env.cr.execute("""
        UPDATE kwtsms_sms_template
        SET is_system = TRUE
        WHERE event_type != 'custom' AND (is_system IS NULL OR is_system = FALSE)
    """)
    # Migrate old #placeholder# notation to {placeholder}
    env.cr.execute("""
        UPDATE kwtsms_sms_template
        SET body = jsonb_set(body, '{en_US}',
            to_jsonb(
                regexp_replace(
                    regexp_replace(body->>'en_US', '#(\\w+)#', '{\\1}', 'g'),
                    '#(\\w+)#', '{\\1}', 'g'
                )
            )
        )
        WHERE body->>'en_US' LIKE '%#%#%'
    """)
