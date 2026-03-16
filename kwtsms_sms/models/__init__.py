from . import kwtsms_notification_mixin
from . import kwtsms_admin_notification_mixin
from . import kwtsms_gateway
from . import kwtsms_sms_log
from . import kwtsms_sms_template
from . import res_company
from . import sale_order
from . import stock_picking
from . import account_move
from . import account_payment

try:
    from . import crm_lead
except ImportError:
    pass  # crm module not installed, CRM hooks disabled
