"""kwtSMS API client integrated with Odoo's SMS framework."""

import json
import logging
import time
import urllib.request
import urllib.error

from odoo.addons.sms.tools.sms_api import SmsApiBase

from .phone_utils import clean_message, normalize_phone, validate_phone

_logger = logging.getLogger(__name__)

API_BASE_URL = 'https://www.kwtsms.com/API'
API_TIMEOUT = 30
BATCH_SIZE = 200
BATCH_DELAY = 0.5
ERR013_MAX_RETRIES = 3
ERR013_BACKOFF = [30, 60, 120]

# Map kwtSMS error codes to Odoo SMS failure types
KWTSMS_ERROR_MAP = {
    'ERR001': 'sms_server',
    'ERR003': 'sms_acc',
    'ERR004': 'sms_acc',
    'ERR005': 'sms_acc',
    'ERR006': 'sms_number_format',
    'ERR009': 'sms_server',
    'ERR010': 'sms_credit',
    'ERR011': 'sms_credit',
    'ERR013': 'sms_server',
    'ERR024': 'sms_server',
    'ERR025': 'sms_number_format',
    'ERR028': 'sms_server',
    'ERR031': 'sms_server',
    'ERR032': 'sms_server',
}

# Map failure types to Odoo-recognized state values
FAILURE_TO_STATE = {
    'sms_server': 'server_error',
    'sms_acc': 'server_error',
    'sms_number_format': 'wrong_number_format',
    'sms_credit': 'insufficient_credit',
    'sms_number_missing': 'sms_number_missing',
    'sms_blacklist': 'sms_blacklist',
}


class KwtSmsApi(SmsApiBase):
    """kwtSMS gateway API client for Odoo SMS framework."""

    def __init__(self, env, account=None):
        super().__init__(env, account=account)
        ICP = self.env['ir.config_parameter'].sudo()
        self._username = ICP.get_param('kwtsms.api_username', '')
        self._password = ICP.get_param('kwtsms.api_password', '')
        self._sender_id = ICP.get_param('kwtsms.sender_id', 'KWT-SMS')
        self._test_mode = ICP.get_param('kwtsms.test_mode', 'True') == 'True'

    def _send_sms_batch(self, messages, delivery_reports_url=False):
        """Send SMS batch through kwtSMS API.

        Called by Odoo's SMS framework.

        Args:
            messages: List of dicts with 'content' and 'numbers' keys.
                      numbers is a list of dicts with 'uuid' and 'number'.
            delivery_reports_url: Optional webhook URL (not used by kwtSMS).

        Returns:
            list: Results per number with uuid, state, credit, failure_type.
        """
        results = []
        for message_data in messages:
            content = clean_message(message_data.get('content', ''))
            numbers = message_data.get('numbers', [])

            if not content:
                for num_info in numbers:
                    results.append({
                        'uuid': num_info.get('uuid'),
                        'state': 'server_error',
                        'credit': 0,
                        'failure_type': 'sms_server',
                    })
                continue

            # Normalize and validate numbers
            valid_sends = []
            for num_info in numbers:
                raw = num_info.get('number', '')
                normalized, error = validate_phone(raw)
                if error:
                    results.append({
                        'uuid': num_info.get('uuid'),
                        'state': 'wrong_number_format',
                        'credit': 0,
                        'failure_type': 'sms_number_format',
                    })
                else:
                    valid_sends.append({
                        'uuid': num_info.get('uuid'),
                        'number': normalized,
                    })

            if not valid_sends:
                continue

            # Batch into chunks of 200
            for i in range(0, len(valid_sends), BATCH_SIZE):
                batch = valid_sends[i:i + BATCH_SIZE]
                mobile_str = ','.join(s['number'] for s in batch)

                payload = {
                    'username': self._username,
                    'password': self._password,
                    'sender': self._sender_id,
                    'mobile': mobile_str,
                    'message': content,
                    'test': '1' if self._test_mode else '0',
                }

                response = self._api_call('send', payload)

                if response.get('result') == 'OK':
                    credit_per_number = 0
                    total_charged = response.get('points-charged', 0)
                    if len(batch) > 0:
                        credit_per_number = total_charged / len(batch)

                    for send_info in batch:
                        results.append({
                            'uuid': send_info['uuid'],
                            'state': 'success',
                            'credit': credit_per_number,
                        })

                    self._log_send(
                        numbers=mobile_str,
                        message=content,
                        response=response,
                        status='test' if self._test_mode else 'success',
                    )
                else:
                    error_code = response.get('code', 'UNKNOWN')
                    failure_type = KWTSMS_ERROR_MAP.get(
                        error_code, 'sms_server'
                    )
                    state = FAILURE_TO_STATE.get(failure_type, 'server_error')
                    for send_info in batch:
                        results.append({
                            'uuid': send_info['uuid'],
                            'state': state,
                            'credit': 0,
                            'failure_type': failure_type,
                        })

                    self._log_send(
                        numbers=mobile_str,
                        message=content,
                        response=response,
                        status='error',
                        error_code=error_code,
                        error_description=response.get('description', ''),
                    )

                # Rate limit between batches
                if i + BATCH_SIZE < len(valid_sends):
                    time.sleep(BATCH_DELAY)

        return results

    def _api_call(self, endpoint, payload):
        """Make a POST request to the kwtSMS API.

        Args:
            endpoint: API endpoint name (e.g. 'send', 'balance').
            payload: Dict payload to send as JSON.

        Returns:
            dict: Parsed JSON response, or error dict on failure.
        """
        url = f'{API_BASE_URL}/{endpoint}/'
        data = json.dumps(payload).encode('utf-8')

        req = urllib.request.Request(
            url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            method='POST',
        )

        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
                body = resp.read().decode('utf-8')
                return json.loads(body)
        except urllib.error.HTTPError as e:
            _logger.error('kwtSMS API HTTP error %s for /%s/', e.code, endpoint)
            return {
                'result': 'ERROR',
                'code': f'HTTP_{e.code}',
                'description': f'HTTP error {e.code}',
            }
        except urllib.error.URLError as e:
            _logger.error('kwtSMS API connection error for /%s/: %s', endpoint, e.reason)
            return {
                'result': 'ERROR',
                'code': 'NETWORK_ERROR',
                'description': 'Connection error. Please try again.',
            }
        except json.JSONDecodeError:
            _logger.error('kwtSMS API returned invalid JSON for /%s/', endpoint)
            return {
                'result': 'ERROR',
                'code': 'PARSE_ERROR',
                'description': 'Invalid response from gateway.',
            }
        except Exception as e:
            _logger.exception('kwtSMS API unexpected error for /%s/: %s', endpoint, e)
            return {
                'result': 'ERROR',
                'code': 'UNKNOWN_ERROR',
                'description': 'An unexpected error occurred.',
            }

    def check_balance(self):
        """Check account balance.

        Returns:
            dict: Balance info or error.
        """
        payload = {
            'username': self._username,
            'password': self._password,
        }
        return self._api_call('balance', payload)

    def fetch_sender_ids(self):
        """Fetch available sender IDs.

        Returns:
            dict: Sender ID list or error.
        """
        payload = {
            'username': self._username,
            'password': self._password,
        }
        return self._api_call('senderid', payload)

    def fetch_coverage(self):
        """Fetch coverage data.

        Returns:
            dict: Coverage info or error.
        """
        payload = {
            'username': self._username,
            'password': self._password,
        }
        return self._api_call('coverage', payload)

    def validate_numbers(self, numbers):
        """Validate phone numbers via kwtSMS API.

        Args:
            numbers: List of phone number strings.

        Returns:
            dict: Validation results with ok, er, nr lists.
        """
        normalized = []
        for phone in numbers:
            norm = normalize_phone(phone)
            if norm:
                normalized.append(norm)

        if not normalized:
            return {'ok': [], 'er': [], 'nr': []}

        payload = {
            'username': self._username,
            'password': self._password,
            'mobile': ','.join(normalized),
        }
        return self._api_call('validate', payload)

    def send_single(self, phone, message, sender_id=None):
        """Send a single SMS directly (not through Odoo framework).

        Used by business event hooks for full control over logging.

        Args:
            phone: Phone number string.
            message: Message text.
            sender_id: Optional sender ID override.

        Returns:
            dict: API response.
        """
        normalized, error = validate_phone(phone)
        if error:
            return {
                'result': 'ERROR',
                'code': 'ERR_VALIDATION',
                'description': f'Invalid phone number: {error}',
            }

        cleaned = clean_message(message)
        if not cleaned:
            return {
                'result': 'ERROR',
                'code': 'ERR_VALIDATION',
                'description': 'Message is empty after cleaning.',
            }

        payload = {
            'username': self._username,
            'password': self._password,
            'sender': sender_id or self._sender_id,
            'mobile': normalized,
            'message': cleaned,
            'test': '1' if self._test_mode else '0',
        }
        return self._api_call('send', payload)

    def _log_send(self, numbers, message, response, status,
                  error_code=None, error_description=None,
                  template_id=None, res_model=None, res_id=None):
        """Log an SMS send attempt to kwtsms.sms.log.

        Args:
            numbers: Comma-separated phone numbers.
            message: Message body sent.
            response: Full API response dict.
            status: Log status (success/error/test/queued).
            error_code: Error code if failed.
            error_description: Error description if failed.
            template_id: Template record ID if used.
            res_model: Related model name.
            res_id: Related record ID.
        """
        try:
            # Strip password from logged response
            safe_response = dict(response)
            safe_response.pop('password', None)

            self.env['kwtsms.sms.log'].sudo().create({
                'phone_number': numbers,
                'message_body': message,
                'template_id': template_id,
                'sender_id': self._sender_id,
                'status': status,
                'api_response': json.dumps(safe_response, ensure_ascii=False),
                'msg_id': response.get('msg-id', ''),
                'points_charged': response.get('points-charged', 0),
                'balance_after': response.get('balance-after', 0),
                'error_code': error_code or '',
                'error_description': error_description or '',
                'test_mode': self._test_mode,
                'res_model': res_model or '',
                'res_id': res_id or 0,
                'company_id': self.env.company.id,
            })
        except Exception as e:
            _logger.error('Failed to log SMS send: %s', e)
