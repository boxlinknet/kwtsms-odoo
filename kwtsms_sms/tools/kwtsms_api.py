"""kwtSMS API client integrated with Odoo's SMS framework."""

import json
import logging
import time
import urllib.request
import urllib.error
from datetime import timedelta

from odoo import fields
from odoo.addons.sms.tools.sms_api import SmsApiBase

from .phone_utils import clean_message, normalize_phone, prepare_phone

_logger = logging.getLogger(__name__)

API_BASE_URL = 'https://www.kwtsms.com/API'
API_TIMEOUT = 30
BATCH_SIZE = 200
BATCH_DELAY = 0.5

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
        self._default_country_code = ICP.get_param('kwtsms.default_country_code', '965')

    # ═══════════════════════════════════════
    # Pre-flight checks (shared by send and _send_sms_batch)
    # ═══════════════════════════════════════

    def _preflight_checks(self):
        """Run pre-send checks: gateway enabled, credentials, cached balance.

        Returns:
            dict or None: Error dict if a check fails, None if all OK.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('kwtsms.enabled', 'True') != 'True':
            return {
                'code': 'ERR_DISABLED',
                'description': 'SMS gateway is disabled. Enable it in kwtSMS Gateway settings.',
            }
        if not self._username or not self._password:
            return {
                'code': 'ERR_NO_CREDENTIALS',
                'description': 'API credentials not configured. Please login first.',
            }
        try:
            config = self.env['kwtsms.gateway.config'].sudo()._get_or_create()
            balance = config.balance_available

            # If last sync is older than 24h, refresh from API
            stale = (
                not config.last_verified
                or config.last_verified < fields.Datetime.now() - timedelta(hours=24)
            )
            if stale:
                resp = self.check_balance()
                if resp.get('result') == 'OK':
                    balance = resp.get('available', 0)
                    config.write({
                        'balance_available': balance,
                        'balance_purchased': resp.get('purchased', 0),
                        'last_verified': fields.Datetime.now(),
                    })
                else:
                    _logger.warning(
                        'kwtSMS: Balance refresh failed: %s',
                        resp.get('description', 'Unknown error'),
                    )

            if balance <= 0:
                return {
                    'code': 'ERR_NO_BALANCE',
                    'description': (
                        'Insufficient SMS balance (%d credits). '
                        'Please top up your kwtSMS account.'
                    ) % balance,
                }
        except Exception as e:
            _logger.warning('kwtSMS: Balance check failed: %s', e)
        return None

    # ═══════════════════════════════════════
    # Unified send (single entry point)
    # ═══════════════════════════════════════

    def send(self, phones, message, sender_id=None, test_mode=None,
             template_id=None, res_model=None, res_id=None):
        """Send SMS to one or more phone numbers.

        Single entry point for ALL SMS sending. Checks gateway status,
        credentials, and cached balance. Validates, normalizes, and
        deduplicates phone numbers. Auto-batches for >200 numbers.
        Logs the result and updates the local balance cache.

        Args:
            phones: Single phone string or list of phone strings.
            message: Message text.
            sender_id: Optional sender ID override.
            test_mode: Override global test mode (True/False).
                       None uses the global setting.
            template_id: Template record ID for logging.
            res_model: Related model name for logging.
            res_id: Related record ID for logging.

        Returns:
            dict: Result with 'result' ('OK'/'ERROR'/'PARTIAL'),
                  valid_count, invalid_count, duplicates_removed,
                  numbers_sent, points-charged, balance-after, msg-id.
        """
        effective_test = test_mode if test_mode is not None else self._test_mode

        # 1. Pre-flight checks (gateway, credentials, balance)
        error = self._preflight_checks()
        if error:
            return {'result': 'ERROR', **error}

        # 2. Normalize phone input
        if phones is None:
            phones = ['']
        elif isinstance(phones, str):
            phones = [phones]

        # 3. Clean message
        cleaned = clean_message(message)
        if not cleaned:
            return {
                'result': 'ERROR',
                'code': 'ERR_VALIDATION',
                'description': 'Message is empty after cleaning.',
            }

        # 4. Validate, normalize, deduplicate phones
        valid = []
        seen = set()
        invalid = []
        duplicates = 0
        for phone in phones:
            normalized, phone_error = prepare_phone(phone, self._default_country_code)
            if phone_error:
                invalid.append({'input': phone, 'reason': phone_error})
            elif normalized in seen:
                duplicates += 1
            else:
                seen.add(normalized)
                valid.append(normalized)

        if not valid:
            desc = 'No valid phone numbers found.'
            if len(phones) == 1 and invalid:
                desc = 'Invalid phone number: %s' % invalid[0]['reason']
            return {
                'result': 'ERROR',
                'code': 'ERR_VALIDATION',
                'description': desc,
                'invalid': invalid,
            }

        # 5. Coverage check (filter out uncovered numbers)
        try:
            config = self.env['kwtsms.gateway.config'].sudo()._get_or_create()
            prefixes = config.get_coverage_prefixes()
            if prefixes:
                prefix_set = set(str(p) for p in prefixes)
                uncovered = []
                for number in valid:
                    covered = any(
                        number[:length] in prefix_set
                        for length in (3, 2, 1)
                    )
                    if not covered:
                        uncovered.append(number)
                if uncovered and len(uncovered) == len(valid):
                    return {
                        'result': 'ERROR',
                        'code': 'ERR_NO_COVERAGE',
                        'description': 'Destination country is not covered by your kwtSMS account.',
                    }
                elif uncovered:
                    for num in uncovered:
                        valid.remove(num)
                        invalid.append({'input': num, 'reason': 'country not covered'})
        except Exception as e:
            _logger.warning('kwtSMS: Coverage check failed: %s', e)

        # 6. Send (single batch or bulk)
        effective_sender = sender_id or self._sender_id

        if len(valid) > BATCH_SIZE:
            result = self._send_bulk(valid, cleaned, effective_sender, effective_test)
        else:
            mobile_str = ','.join(valid)
            payload = {
                'username': self._username,
                'password': self._password,
                'sender': effective_sender,
                'mobile': mobile_str,
                'message': cleaned,
                'test': '1' if effective_test else '0',
            }
            response = self._api_call('send', payload)

            if response.get('result') == 'OK':
                self._update_balance_from_response(response)
                result = {
                    'result': 'OK',
                    'numbers_sent': mobile_str,
                    'points-charged': response.get('points-charged', 0),
                    'balance-after': response.get('balance-after', 0),
                    'msg-id': response.get('msg-id', ''),
                }
            else:
                result = {
                    'result': 'ERROR',
                    'code': response.get('code', 'UNKNOWN'),
                    'description': response.get('description', ''),
                    'numbers_sent': mobile_str,
                }

        # 7. Attach validation stats
        result['valid_count'] = len(valid)
        result['invalid_count'] = len(invalid)
        result['duplicates_removed'] = duplicates
        if invalid:
            result['invalid'] = invalid

        # 8. Log the send
        status = 'error'
        if result.get('result') in ('OK', 'PARTIAL'):
            status = 'test' if effective_test else 'success'

        self._log_send(
            numbers=result.get('numbers_sent', ','.join(valid)),
            message=cleaned,
            response=result,
            status=status,
            error_code=result.get('code') if status == 'error' else None,
            error_description=result.get('description') if status == 'error' else None,
            template_id=template_id,
            res_model=res_model,
            res_id=res_id,
        )

        return result

    def _send_bulk(self, numbers, message, sender_id, test_mode):
        """Send SMS to >200 numbers in batches with rate-limit delay.

        Private method called by send() when len(numbers) > BATCH_SIZE.
        Balance is already checked once by send() before calling this.

        Args:
            numbers: List of validated, normalized phone strings.
            message: Cleaned message text.
            sender_id: Sender ID to use.
            test_mode: Whether to send in test mode.

        Returns:
            dict: Aggregated result across all batches.
        """
        all_responses = []
        total_charged = 0
        last_balance = 0
        all_sent = []
        has_failure = False

        for i in range(0, len(numbers), BATCH_SIZE):
            batch = numbers[i:i + BATCH_SIZE]
            mobile_str = ','.join(batch)

            payload = {
                'username': self._username,
                'password': self._password,
                'sender': sender_id,
                'mobile': mobile_str,
                'message': message,
                'test': '1' if test_mode else '0',
            }

            response = self._api_call('send', payload)
            all_responses.append(response)

            if response.get('result') == 'OK':
                total_charged += response.get('points-charged', 0)
                last_balance = response.get('balance-after', 0)
                self._update_balance_from_response(response)
                all_sent.extend(batch)
            else:
                has_failure = True

            # Rate limit between batches
            if i + BATCH_SIZE < len(numbers):
                time.sleep(BATCH_DELAY)

        # Determine final result
        if not has_failure:
            final_result = 'OK'
        elif all_sent:
            final_result = 'PARTIAL'
        else:
            final_result = 'ERROR'

        result = {
            'result': final_result,
            'numbers_sent': ','.join(all_sent) if all_sent else ','.join(numbers),
            'points-charged': total_charged,
            'balance-after': last_balance,
        }

        if all_responses:
            result['msg-id'] = all_responses[0].get('msg-id', '')

        if final_result != 'OK':
            for resp in all_responses:
                if resp.get('result') != 'OK':
                    result['code'] = resp.get('code', 'UNKNOWN')
                    result['description'] = resp.get('description', '')
                    break

        return result

    # ═══════════════════════════════════════
    # Odoo SMS framework adapter
    # ═══════════════════════════════════════

    def _send_sms_batch(self, messages, delivery_reports_url=False):
        """Send SMS batch through kwtSMS API.

        Called by Odoo's SMS framework. Uses the same pre-flight checks
        as send() but returns uuid-based results per Odoo's contract.

        Args:
            messages: List of dicts with 'content' and 'numbers' keys.
                      numbers is a list of dicts with 'uuid' and 'number'.
            delivery_reports_url: Optional webhook URL (not used by kwtSMS).

        Returns:
            list: Results per number with uuid, state, credit, failure_type.
        """
        results = []

        # Pre-flight checks
        error = self._preflight_checks()
        if error:
            failure_map = {
                'ERR_DISABLED': ('server_error', 'sms_server'),
                'ERR_NO_CREDENTIALS': ('server_error', 'sms_acc'),
                'ERR_NO_BALANCE': ('insufficient_credit', 'sms_credit'),
            }
            state, failure_type = failure_map.get(
                error.get('code'), ('server_error', 'sms_server')
            )
            for message_data in messages:
                for num_info in message_data.get('numbers', []):
                    results.append({
                        'uuid': num_info.get('uuid'),
                        'state': state,
                        'credit': 0,
                        'failure_type': failure_type,
                    })
            return results

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

            # Normalize, validate, deduplicate, and prepend country code
            valid_sends = []
            seen = set()
            for num_info in numbers:
                raw = num_info.get('number', '')
                normalized, phone_error = prepare_phone(raw, self._default_country_code)
                if phone_error:
                    results.append({
                        'uuid': num_info.get('uuid'),
                        'state': 'wrong_number_format',
                        'credit': 0,
                        'failure_type': 'sms_number_format',
                    })
                elif normalized in seen:
                    # Duplicate: mark as success (first occurrence will be sent)
                    results.append({
                        'uuid': num_info.get('uuid'),
                        'state': 'success',
                        'credit': 0,
                    })
                else:
                    seen.add(normalized)
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

                    self._update_balance_from_response(response)
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

    # ═══════════════════════════════════════
    # API transport
    # ═══════════════════════════════════════

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
            # Always try to read and return the gateway's own error message
            try:
                body_text = e.read().decode('utf-8', errors='replace')
                body_json = json.loads(body_text)
                if isinstance(body_json, dict):
                    if not body_json.get('result'):
                        body_json['result'] = 'ERROR'
                    if not body_json.get('code'):
                        body_json['code'] = 'HTTP_%s' % e.code
                    return body_json
            except Exception:
                _logger.debug('kwtSMS: Could not parse HTTP %s body: %s',
                              e.code, body_text[:200] if body_text else '(empty)')
            return {
                'result': 'ERROR',
                'code': 'HTTP_%s' % e.code,
                'description': 'Gateway returned HTTP %s. Please try again.' % e.code,
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

    # ═══════════════════════════════════════
    # Account info (no send, no pre-flight)
    # ═══════════════════════════════════════

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

    # ═══════════════════════════════════════
    # Internal helpers
    # ═══════════════════════════════════════

    def _update_balance_from_response(self, response):
        """Update gateway config balance from a successful send response."""
        balance_after = response.get('balance-after')
        if balance_after is not None:
            try:
                config = self.env['kwtsms.gateway.config'].sudo()._get_or_create()
                config.write({'balance_available': int(balance_after)})
            except Exception as e:
                _logger.warning('kwtSMS: Could not update balance: %s', e)

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
