# kwtSMS Gateway for Odoo

[![CI](https://github.com/boxlinknet/kwtsms-odoo/actions/workflows/ci.yml/badge.svg)](https://github.com/boxlinknet/kwtsms-odoo/actions/workflows/ci.yml)
![Odoo 19.0](https://img.shields.io/badge/Odoo-19.0-714B67)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![License: OPL-1](https://img.shields.io/badge/License-OPL--1-blue)

Send SMS messages from Odoo using the [kwtSMS](https://www.kwtsms.com) gateway. Replaces Odoo's built-in IAP SMS credits with a direct kwtSMS integration for Kuwait and international messaging.

## Features

- **SMS Gateway Integration**: Direct kwtSMS API integration (JSON REST API)
- **Replace Odoo IAP**: Use kwtSMS instead of Odoo's expensive IAP credits
- **Business Event Notifications**: Auto-send SMS on order confirmation, order cancellation, delivery, invoice posting, and payment received
- **SMS Templates**: Multilingual templates with placeholder variables (English + Arabic)
- **Dashboard**: Balance display, SMS stats, quick actions, notification status at a glance
- **Bulk SMS**: Send to 200+ recipients with automatic batching (comma-separated or one per line)
- **SMS Sender Dialog**: Send SMS from any record in Odoo (contacts, orders, invoices)
- **Phone Normalization**: Handles `+965`, `00965`, Arabic digits, spaces, dashes automatically
- **SMS Logs**: Full audit trail of all sent messages with API responses
- **Balance Tracking**: Real-time kwtSMS account balance display
- **Sender ID Management**: Dynamically fetch and select approved Sender IDs
- **Arabic Support**: RTL-aware templates, Unicode character counting, full Arabic UI translation
- **Test Mode**: Send with `test=1` during development (no credits consumed)
- **Test SMS Widget**: Send a test SMS directly from the Gateway page

## Supported Odoo Versions

| Version | Status |
|---------|--------|
| 19.0 | Supported (primary) |
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

1. Open the **kwtSMS Gateway** app from the main menu
2. Navigate to **Gateway** (via the top menu)
3. Enter your kwtSMS API Username and Password
4. Click **Login** to verify credentials and fetch your account data
5. Select your **Sender ID** from the dropdown (auto-populated after login)
6. Keep **Test Mode ON** during development (SMS queued but not delivered, no credits used)
7. Enable the **SMS Notification** toggles you need (Sales, Inventory, Accounting)
8. Use **Send Test SMS** on the Gateway page to verify end-to-end
9. Switch **Test Mode OFF** when ready for production

## SMS Notification Events

| Event | Model | Trigger |
|-------|-------|---------|
| Order Confirmed | sale.order | action_confirm() |
| Order Cancelled | sale.order | action_cancel() |
| Delivery Done | stock.picking | _action_done() (outgoing only) |
| Invoice Posted | account.move | action_post() (customer invoices only) |
| Payment Received | account.payment | action_post() (inbound only) |

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
