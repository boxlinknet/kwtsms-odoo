# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 19.0.x | Yes |
| 18.0.x | Planned |
| 16.0.x | Planned |

## Reporting a Vulnerability

If you discover a security vulnerability in this module, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

### How to Report

1. Email: mo@boxlink.net
2. Include: module version, Odoo version, description of the vulnerability, steps to reproduce

### What to Expect

- Acknowledgment within 48 hours
- Assessment and fix timeline within 5 business days
- Credit in the changelog (unless you prefer anonymity)

## Security Measures

This module implements the following security practices:

### Credential Protection
- API credentials stored in `ir.config_parameter` (server-side only)
- Credentials never exposed to frontend HTML or JavaScript
- Passwords masked in all log entries
- All API communication over HTTPS with POST method only

### Input Validation
- Phone numbers normalized and validated before API calls
- SQL injection prevention via Odoo ORM (no raw SQL)
- XSS prevention via Odoo's built-in output escaping
- CSRF protection via Odoo's session tokens

### Access Control
- Settings restricted to users with `base.group_system` (Administrator)
- SMS logs restricted by security groups
- Record rules enforce multi-company isolation

### Anti-Abuse
- Rate limiting on OTP requests
- Balance check before sending (prevents unnecessary API calls)
- Test mode for development (no real SMS sent)

### Logging
- All SMS attempts logged with sanitized payloads
- Full phone numbers stored in database (not masked) per requirement
- API credentials always stripped from log entries
