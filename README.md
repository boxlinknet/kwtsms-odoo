# kwtSMS Gateway for Odoo

Send SMS messages from Odoo using the [kwtSMS](https://www.kwtsms.com) gateway. Replaces Odoo's built-in IAP SMS credits with a direct kwtSMS integration for Kuwait and international messaging.

## Features

- **SMS Gateway Integration**: Direct kwtSMS API integration (JSON REST API)
- **Replace Odoo IAP**: Use kwtSMS instead of Odoo's expensive IAP credits
- **Business Event Notifications**: Auto-send SMS on order confirmation, invoice, delivery, payment
- **SMS Templates**: Multilingual templates with placeholder variables (English + Arabic)
- **Bulk SMS**: Send to 200+ recipients with automatic batching (comma-separated or one per line)
- **Phone Normalization**: Handles `+965`, `00965`, Arabic digits, spaces, dashes automatically
- **SMS Logs**: Full audit trail of all sent messages with API responses
- **Balance Tracking**: Real-time kwtSMS account balance display
- **Sender ID Management**: Dynamically fetch and select approved Sender IDs
- **Arabic Support**: RTL-aware templates, Unicode character counting
- **Test Mode**: Send with `test=1` during development (no credits consumed)

## Supported Odoo Versions

| Version | Status |
|---------|--------|
| 19.0 | Primary target |
| 18.0 | Planned |
| 16.0 | Planned |

## Requirements

- Odoo 19.0 (Community or Enterprise)
- Python 3.10+
- A kwtSMS account with API access ([kwtsms.com](https://www.kwtsms.com))
- An approved Sender ID (for production use)

## Installation

1. Copy `kwtsms_sms` folder to your Odoo addons directory
2. Update Apps List: Settings > Apps > Update Apps List
3. Search for "kwtSMS" and click Install

## Configuration

1. Go to **Settings > kwtSMS Gateway**
2. Enter your kwtSMS API Username and Password
3. Click **Login / Verify** to connect
4. Select your Sender ID from the dropdown
5. Enable desired notification triggers

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `/API/balance/` | Verify credentials, check balance |
| `/API/senderid/` | List available Sender IDs |
| `/API/coverage/` | List active country coverage |
| `/API/send/` | Send SMS messages |
| `/API/validate/` | Validate phone numbers |

## kwtSMS API Compliance

Built in full compliance with:
- [kwtSMS API Documentation v4.1](https://www.kwtsms.com/doc/KwtSMS.com_API_Documentation_v41.pdf)
- [kwtSMS API Implementation Best Practices](https://www.kwtsms.com/articles/sms-api-implementation-best-practices.html)
- [kwtSMS API Integration Test Checklist](https://www.kwtsms.com/articles/sms-api-integration-test-checklist.html)

## Support

- **kwtSMS Support**: [kwtsms.com/support](https://www.kwtsms.com/support.html)
- **Issues**: Open a GitHub issue on this repository

## License

OPL-1 (Odoo Proprietary License v1.0)
