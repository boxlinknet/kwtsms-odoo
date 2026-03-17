"""OTP cryptographic utilities: generation, hashing, verification."""

import hashlib
import hmac
import secrets


def generate_otp(length=6):
    """Generate a random numeric OTP code.

    Args:
        length: Number of digits (minimum 6).

    Returns:
        tuple: (plain_code, hashed_code)
    """
    if length < 6:
        length = 6
    # Generate random digits
    code = ''.join(str(secrets.randbelow(10)) for _ in range(length))
    return code, hash_otp(code)


def hash_otp(code):
    """SHA-256 hash an OTP code.

    Args:
        code: Plain text OTP code string.

    Returns:
        str: Hex digest of SHA-256 hash.
    """
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def verify_otp(user_input, stored_hash):
    """Verify OTP using constant-time comparison.

    Prevents timing side-channel attacks.

    Args:
        user_input: Code entered by user.
        stored_hash: SHA-256 hash stored in database.

    Returns:
        bool: True if codes match.
    """
    input_hash = hashlib.sha256(user_input.encode('utf-8')).hexdigest()
    return hmac.compare_digest(input_hash, stored_hash)


def generate_device_token():
    """Generate a 256-bit device trust token.

    Returns:
        tuple: (plain_token, hashed_token)
    """
    token = secrets.token_hex(32)  # 64 hex chars = 256 bits
    return token, hash_device_token(token)


def hash_device_token(token):
    """SHA-256 hash a device token.

    Args:
        token: Plain text device token.

    Returns:
        str: Hex digest of SHA-256 hash.
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def hash_user_agent(ua_string):
    """SHA-256 hash a User-Agent string for device binding.

    Args:
        ua_string: Browser User-Agent header value.

    Returns:
        str: Hex digest of SHA-256 hash.
    """
    return hashlib.sha256((ua_string or '').encode('utf-8')).hexdigest()
