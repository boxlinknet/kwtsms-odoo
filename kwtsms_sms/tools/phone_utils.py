"""Phone number normalization, validation, and message cleaning utilities.

Includes country-specific format validation (local length + mobile prefix)
ported from kwtsms-shopify phone.ts. Numbers with no matching country code
pass through with generic E.164 validation only (7-15 digits).
"""

import re

# Arabic-Indic and Extended Arabic-Indic digit translation table
_DIGIT_TRANS = str.maketrans(
    '\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669'  # Arabic-Indic
    '\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9',  # Extended
    '01234567890123456789',
)

# ---------------------------------------------------------------------------
# Country-specific phone validation rules
# ---------------------------------------------------------------------------
# Each entry: { 'local_lengths': [int], 'mobile_start': [str] or None }
# local_lengths = valid digit counts AFTER the country code
# mobile_start  = valid first character(s) of the local number (None = any)
#
# Sources: ITU-T E.164, Wikipedia telephone numbering articles,
#          HowToCallAbroad.com, CountryCode.com
# Synced from kwtsms-shopify phone.ts PHONE_RULES
# ---------------------------------------------------------------------------
PHONE_RULES = {
    # === GCC ===
    '965': {'local_lengths': [8], 'mobile_start': ['4', '5', '6', '9']},
    '966': {'local_lengths': [9], 'mobile_start': ['5']},
    '971': {'local_lengths': [9], 'mobile_start': ['5']},
    '973': {'local_lengths': [8], 'mobile_start': ['3', '6']},
    '974': {'local_lengths': [8], 'mobile_start': ['3', '5', '6', '7']},
    '968': {'local_lengths': [8], 'mobile_start': ['7', '9']},
    # === Levant ===
    '962': {'local_lengths': [9], 'mobile_start': ['7']},
    '961': {'local_lengths': [7, 8], 'mobile_start': ['3', '7', '8']},
    '970': {'local_lengths': [9], 'mobile_start': ['5']},
    '964': {'local_lengths': [10], 'mobile_start': ['7']},
    '963': {'local_lengths': [9], 'mobile_start': ['9']},
    # === Other Arab ===
    '967': {'local_lengths': [9], 'mobile_start': ['7']},
    '20':  {'local_lengths': [10], 'mobile_start': ['1']},
    '218': {'local_lengths': [9], 'mobile_start': ['9']},
    '216': {'local_lengths': [8], 'mobile_start': ['2', '4', '5', '9']},
    '212': {'local_lengths': [9], 'mobile_start': ['6', '7']},
    '213': {'local_lengths': [9], 'mobile_start': ['5', '6', '7']},
    '249': {'local_lengths': [9], 'mobile_start': ['9']},
    # === Non-Arab Middle East ===
    '98':  {'local_lengths': [10], 'mobile_start': ['9']},
    '90':  {'local_lengths': [10], 'mobile_start': ['5']},
    '972': {'local_lengths': [9], 'mobile_start': ['5']},
    # === South Asia ===
    '91':  {'local_lengths': [10], 'mobile_start': ['6', '7', '8', '9']},
    '92':  {'local_lengths': [10], 'mobile_start': ['3']},
    '880': {'local_lengths': [10], 'mobile_start': ['1']},
    '94':  {'local_lengths': [9], 'mobile_start': ['7']},
    '960': {'local_lengths': [7], 'mobile_start': ['7', '9']},
    # === East Asia ===
    '86':  {'local_lengths': [11], 'mobile_start': ['1']},
    '81':  {'local_lengths': [10], 'mobile_start': ['7', '8', '9']},
    '82':  {'local_lengths': [10], 'mobile_start': ['1']},
    '886': {'local_lengths': [9], 'mobile_start': ['9']},
    # === Southeast Asia ===
    '65':  {'local_lengths': [8], 'mobile_start': ['8', '9']},
    '60':  {'local_lengths': [9, 10], 'mobile_start': ['1']},
    '62':  {'local_lengths': [9, 10, 11, 12], 'mobile_start': ['8']},
    '63':  {'local_lengths': [10], 'mobile_start': ['9']},
    '66':  {'local_lengths': [9], 'mobile_start': ['6', '8', '9']},
    '84':  {'local_lengths': [9], 'mobile_start': ['3', '5', '7', '8', '9']},
    '95':  {'local_lengths': [9], 'mobile_start': ['9']},
    '855': {'local_lengths': [8, 9], 'mobile_start': ['1', '6', '7', '8', '9']},
    '976': {'local_lengths': [8], 'mobile_start': ['6', '8', '9']},
    # === Europe ===
    '44':  {'local_lengths': [10], 'mobile_start': ['7']},
    '33':  {'local_lengths': [9], 'mobile_start': ['6', '7']},
    '49':  {'local_lengths': [10, 11], 'mobile_start': ['1']},
    '39':  {'local_lengths': [10], 'mobile_start': ['3']},
    '34':  {'local_lengths': [9], 'mobile_start': ['6', '7']},
    '31':  {'local_lengths': [9], 'mobile_start': ['6']},
    '32':  {'local_lengths': [9], 'mobile_start': None},
    '41':  {'local_lengths': [9], 'mobile_start': ['7']},
    '43':  {'local_lengths': [10], 'mobile_start': ['6']},
    '47':  {'local_lengths': [8], 'mobile_start': ['4', '9']},
    '48':  {'local_lengths': [9], 'mobile_start': None},
    '30':  {'local_lengths': [10], 'mobile_start': ['6']},
    '420': {'local_lengths': [9], 'mobile_start': ['6', '7']},
    '46':  {'local_lengths': [9], 'mobile_start': ['7']},
    '45':  {'local_lengths': [8], 'mobile_start': None},
    '40':  {'local_lengths': [9], 'mobile_start': ['7']},
    '36':  {'local_lengths': [9], 'mobile_start': None},
    '380': {'local_lengths': [9], 'mobile_start': None},
    # === Americas ===
    '1':   {'local_lengths': [10], 'mobile_start': None},
    '52':  {'local_lengths': [10], 'mobile_start': None},
    '55':  {'local_lengths': [11], 'mobile_start': None},
    '57':  {'local_lengths': [10], 'mobile_start': ['3']},
    '54':  {'local_lengths': [10], 'mobile_start': ['9']},
    '56':  {'local_lengths': [9], 'mobile_start': ['9']},
    '58':  {'local_lengths': [10], 'mobile_start': ['4']},
    '51':  {'local_lengths': [9], 'mobile_start': ['9']},
    '593': {'local_lengths': [9], 'mobile_start': ['9']},
    '53':  {'local_lengths': [8], 'mobile_start': ['5', '6']},
    # === Africa ===
    '27':  {'local_lengths': [9], 'mobile_start': ['6', '7', '8']},
    '234': {'local_lengths': [10], 'mobile_start': ['7', '8', '9']},
    '254': {'local_lengths': [9], 'mobile_start': ['1', '7']},
    '233': {'local_lengths': [9], 'mobile_start': ['2', '5']},
    '251': {'local_lengths': [9], 'mobile_start': ['7', '9']},
    '255': {'local_lengths': [9], 'mobile_start': ['6', '7']},
    '256': {'local_lengths': [9], 'mobile_start': ['7']},
    '237': {'local_lengths': [9], 'mobile_start': ['6']},
    '225': {'local_lengths': [10], 'mobile_start': None},
    '221': {'local_lengths': [9], 'mobile_start': ['7']},
    '252': {'local_lengths': [9], 'mobile_start': ['6', '7']},
    '250': {'local_lengths': [9], 'mobile_start': ['7']},
    # === Oceania ===
    '61':  {'local_lengths': [9], 'mobile_start': ['4']},
    '64':  {'local_lengths': [8, 9, 10], 'mobile_start': ['2']},
}

COUNTRY_NAMES = {
    '965': 'Kuwait', '966': 'Saudi Arabia', '971': 'UAE',
    '973': 'Bahrain', '974': 'Qatar', '968': 'Oman',
    '962': 'Jordan', '961': 'Lebanon', '970': 'Palestine',
    '964': 'Iraq', '963': 'Syria', '967': 'Yemen',
    '98': 'Iran', '90': 'Turkey', '972': 'Israel',
    '20': 'Egypt', '218': 'Libya', '216': 'Tunisia',
    '212': 'Morocco', '213': 'Algeria', '249': 'Sudan',
    '91': 'India', '92': 'Pakistan', '880': 'Bangladesh',
    '94': 'Sri Lanka', '960': 'Maldives',
    '86': 'China', '81': 'Japan', '82': 'South Korea', '886': 'Taiwan',
    '65': 'Singapore', '60': 'Malaysia', '62': 'Indonesia',
    '63': 'Philippines', '66': 'Thailand', '84': 'Vietnam',
    '95': 'Myanmar', '855': 'Cambodia', '976': 'Mongolia',
    '44': 'UK', '33': 'France', '49': 'Germany', '39': 'Italy',
    '34': 'Spain', '31': 'Netherlands', '32': 'Belgium',
    '41': 'Switzerland', '43': 'Austria', '47': 'Norway',
    '48': 'Poland', '30': 'Greece', '420': 'Czech Republic',
    '46': 'Sweden', '45': 'Denmark', '40': 'Romania',
    '36': 'Hungary', '380': 'Ukraine',
    '1': 'USA/Canada', '52': 'Mexico', '55': 'Brazil',
    '57': 'Colombia', '54': 'Argentina', '56': 'Chile',
    '58': 'Venezuela', '51': 'Peru', '593': 'Ecuador', '53': 'Cuba',
    '27': 'South Africa', '234': 'Nigeria', '254': 'Kenya',
    '233': 'Ghana', '251': 'Ethiopia', '255': 'Tanzania',
    '256': 'Uganda', '237': 'Cameroon', '225': 'Ivory Coast',
    '221': 'Senegal', '252': 'Somalia', '250': 'Rwanda',
    '61': 'Australia', '64': 'New Zealand',
}

# GSM 7-bit character set (basic + extension)
_GSM7_BASIC = (
    '@\u00a3$\u00a5\u00e8\u00e9\u00f9\u00ec\u00f2\u00c7\n\u00d8\u00f8\r\u00c5\u00e5'
    '\u0394_\u03a6\u0393\u039b\u03a9\u03a0\u03a8\u03a3\u0398\u039e\x1b\u00c6\u00e6'
    '\u00df\u00c9 !"#\u00a4%&\'()*+,-./0123456789:;<=>?'
    '\u00a1ABCDEFGHIJKLMNOPQRSTUVWXYZ\u00c4\u00d6\u00d1\u00dc\u00a7'
    '\u00bfabcdefghijklmnopqrstuvwxyz\u00e4\u00f6\u00f1\u00fc\u00e0'
)
_GSM7_EXT = '|^{}[~]\\€'
_GSM7_CHARS = set(_GSM7_BASIC + _GSM7_EXT)

# Emoji regex pattern (covers most Unicode emoji ranges)
_EMOJI_PATTERN = re.compile(
    '['
    '\U0001f600-\U0001f64f'  # Emoticons
    '\U0001f300-\U0001f5ff'  # Misc symbols and pictographs
    '\U0001f680-\U0001f6ff'  # Transport and map
    '\U0001f1e0-\U0001f1ff'  # Flags
    '\U0001f900-\U0001f9ff'  # Supplemental symbols
    '\U0001fa00-\U0001fa6f'  # Chess symbols
    '\U0001fa70-\U0001faff'  # Symbols extended-A
    '\U00002702-\U000027b0'  # Dingbats
    '\U000024c2-\U0001f251'  # Enclosed characters
    '\U0000200d'             # Zero-width joiner
    '\U0000fe0f'             # Variation selector
    ']+',
    flags=re.UNICODE,
)

# Hidden control characters to strip
_CONTROL_CHARS = re.compile(
    '['
    '\u200b'  # Zero-width space
    '\u200c'  # Zero-width non-joiner
    '\u200d'  # Zero-width joiner (also in emoji pattern)
    '\u200e'  # Left-to-right mark
    '\u200f'  # Right-to-left mark
    '\u202a'  # Left-to-right embedding
    '\u202b'  # Right-to-left embedding
    '\u202c'  # Pop directional formatting
    '\u202d'  # Left-to-right override
    '\u202e'  # Right-to-left override
    '\u2060'  # Word joiner
    '\u2061'  # Function application
    '\u2062'  # Invisible times
    '\u2063'  # Invisible separator
    '\u2064'  # Invisible plus
    '\ufeff'  # BOM / zero-width no-break space
    '\u00ad'  # Soft hyphen
    '\ufff9'  # Interlinear annotation anchor
    '\ufffa'  # Interlinear annotation separator
    '\ufffb'  # Interlinear annotation terminator
    ']+',
)


def normalize_phone(phone):
    """Normalize a phone number to digits only.

    Converts Arabic/Hindi digits to Latin, strips non-digits and leading zeros.

    Args:
        phone (str): Raw phone number string.

    Returns:
        str: Cleaned phone number with digits only.
    """
    if not phone:
        return ''
    phone = phone.translate(_DIGIT_TRANS)
    phone = re.sub(r'\D', '', phone)
    phone = phone.lstrip('0')
    return phone


def find_country_code(normalized):
    """Find the country code prefix from a normalized phone number.

    Tries 3-digit codes first, then 2-digit, then 1-digit (longest match wins).

    Args:
        normalized (str): Digits-only phone number.

    Returns:
        str or None: Matched country code, or None if no match.
    """
    for length in (3, 2, 1):
        if len(normalized) >= length:
            prefix = normalized[:length]
            if prefix in PHONE_RULES:
                return prefix
    return None


def validate_phone_format(normalized):
    """Validate a normalized number against country-specific format rules.

    Checks local number length and mobile starting digits.
    Numbers with no matching country code pass through (generic E.164 only).

    Args:
        normalized (str): Digits-only phone number.

    Returns:
        tuple: (True, None) on success, (False, error_message) on failure.
    """
    cc = find_country_code(normalized)
    if not cc:
        return (True, None)

    rule = PHONE_RULES[cc]
    local = normalized[len(cc):]
    country = COUNTRY_NAMES.get(cc, '+%s' % cc)

    if local and len(local) not in rule['local_lengths']:
        expected = ' or '.join(str(n) for n in rule['local_lengths'])
        return (False, 'invalid %s number: expected %s digits after +%s, got %s'
                % (country, expected, cc, len(local)))

    mobile_start = rule.get('mobile_start')
    if mobile_start and local:
        if not any(local.startswith(p) for p in mobile_start):
            return (False,
                    'invalid %s mobile number: after +%s must start with %s'
                    % (country, cc, ', '.join(mobile_start)))

    return (True, None)


def validate_phone(phone):
    """Validate a phone number.

    Runs basic checks (empty, email, length) then country-specific format
    validation (local length + mobile prefix) when a country code is recognized.

    Args:
        phone (str): Raw phone number string.

    Returns:
        tuple: (normalized_number, None) on success,
               (None, error_reason) on failure.
    """
    if phone is None:
        return (None, 'phone number is None')
    if not isinstance(phone, str) or not phone.strip():
        return (None, 'phone number is empty')
    if '@' in phone:
        return (None, 'looks like an email')

    normalized = normalize_phone(phone)
    if not normalized:
        return (None, 'no digits found')
    if len(normalized) < 7:
        return (None, 'too short')
    if len(normalized) > 15:
        return (None, 'too long')

    # Country-specific format validation
    valid, error = validate_phone_format(normalized)
    if not valid:
        return (None, error)

    return (normalized, None)


def prepare_phone(phone, default_country_code=None):
    """Normalize, validate, and prepend default country code if needed.

    If the normalized number is 9 digits or fewer and a default country code
    is provided, the code is prepended (e.g. '98765432' with code '965'
    becomes '96598765432').

    Args:
        phone (str): Raw phone number string.
        default_country_code (str): Country code to prepend for local numbers.

    Returns:
        tuple: (prepared_number, None) on success,
               (None, error_reason) on failure.
    """
    normalized, error = validate_phone(phone)
    if error:
        return (None, error)

    if (default_country_code
            and not normalized.startswith(default_country_code)
            and len(normalized) <= 9):
        normalized = default_country_code + normalized

    return (normalized, None)


def validate_phone_list(phones):
    """Validate a list of phone numbers.

    Args:
        phones (list): List of raw phone number strings.

    Returns:
        tuple: (valid_numbers, invalid_list) where invalid_list contains
               dicts with 'input' and 'reason' keys.
    """
    valid = []
    invalid = []
    for phone in phones:
        number, error = validate_phone(phone)
        if number:
            valid.append(number)
        else:
            invalid.append({'input': phone, 'reason': error})
    return (valid, invalid)


def clean_message(message):
    """Clean an SMS message for sending.

    Strips HTML tags, emojis, hidden control characters, and converts
    Arabic/Hindi digits. Preserves Arabic letters.

    Args:
        message (str): Raw message text.

    Returns:
        str: Cleaned message ready for sending.
    """
    if not message:
        return ''
    # Strip HTML tags (convert <br> variants to newline first)
    message = re.sub(r'<br\s*/?>', '\n', message, flags=re.IGNORECASE)
    message = re.sub(r'<[^>]+>', '', message)
    # Decode common HTML entities
    message = (message
               .replace('&amp;', '&')
               .replace('&lt;', '<')
               .replace('&gt;', '>')
               .replace('&nbsp;', ' ')
               .replace('&quot;', '"')
               .replace('&#39;', "'"))
    # Strip emojis
    message = _EMOJI_PATTERN.sub('', message)
    # Strip hidden control characters
    message = _CONTROL_CHARS.sub('', message)
    # Convert Arabic/Hindi digits to Latin
    message = message.translate(_DIGIT_TRANS)
    # Clean up extra whitespace from removals
    message = re.sub(r'  +', ' ', message).strip()
    return message


def is_gsm7(message):
    """Check if a message contains only GSM 7-bit characters.

    Args:
        message (str): Message text.

    Returns:
        bool: True if all characters are in the GSM 7-bit charset.
    """
    return all(c in _GSM7_CHARS for c in message)


def count_sms_parts(message):
    """Count SMS parts/pages for a message.

    Args:
        message (str): Message text.

    Returns:
        tuple: (char_count, page_count, is_unicode)
    """
    if not message:
        return (0, 0, False)

    char_count = len(message)
    unicode_msg = not is_gsm7(message)

    if unicode_msg:
        # Unicode: 70 chars single, 67 per part multipart
        if char_count <= 70:
            page_count = 1
        else:
            page_count = (char_count + 66) // 67  # ceil division
    else:
        # GSM-7: 160 chars single, 153 per part multipart
        if char_count <= 160:
            page_count = 1
        else:
            page_count = (char_count + 152) // 153  # ceil division

    # kwtSMS max 7 pages
    page_count = min(page_count, 7)

    return (char_count, page_count, unicode_msg)
