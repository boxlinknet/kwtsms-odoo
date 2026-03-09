"""Phone number normalization, validation, and message cleaning utilities."""

import re

# Arabic-Indic and Extended Arabic-Indic digit translation table
_DIGIT_TRANS = str.maketrans(
    '\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669'  # Arabic-Indic
    '\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9',  # Extended
    '01234567890123456789',
)

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


def validate_phone(phone):
    """Validate a phone number.

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

    Strips emojis, hidden control characters, and converts Arabic/Hindi digits.
    Preserves Arabic letters.

    Args:
        message (str): Raw message text.

    Returns:
        str: Cleaned message ready for sending.
    """
    if not message:
        return ''
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
