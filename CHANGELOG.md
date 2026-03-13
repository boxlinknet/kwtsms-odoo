# Changelog

All notable changes to the kwtSMS Gateway for Odoo module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with Odoo version prefix (e.g., 19.0.1.0.0).

## [Unreleased]

## [0.2.2] - 2026-03-13

### Added
- **Phase 2 business event hooks**: Order cancellation (sale.order), invoice posted (account.move), payment received (account.payment)
- Dashboard view (priority 10, default landing page) with balance, stats, quick actions, notification status
- Help page with setup guide, placeholder reference, external resource links
- Test SMS OWL widget embedded directly on Gateway page
- 5 marketplace screenshots (dashboard, gateway, templates, logs, help)
- Full Arabic translation: 160 entries, 0 untranslated
- Accessibility: `title` attributes on all Font Awesome `<i>` tags (Odoo 19 requirement)

### Changed
- License confirmed as OPL-1 in manifest (matches LICENSE file)
- Gateway page is now the configuration hub: credentials, sender ID, notification toggles, test SMS
- All hooks check `kwtsms.enabled` setting before attempting SMS
- Module version bumped to 19.0.2.2.0

### Fixed
- Dashboard navigation: menu items correctly open dashboard, gateway, and help views
- Gateway enabled enforcement: all send paths respect the enabled toggle
- Removed draft HTML banner files from static/description

## [0.2.1] - 2026-03-11

### Changed
- **Unified `send()` API**: Merged `send_single()` and `send_multi()` into one `send()` method that accepts a single phone string or a list, with automatic dedup and batching
- All SMS sending (business hooks, SMS Sender, test wizard) now goes through `send()`
- Duplicate phone numbers are removed in all send paths, including Odoo framework `_send_sms_batch()`

## [0.2.0] - 2026-03-10

### Added
- **Bulk SMS sending**: SMS Sender now supports multiple phone numbers, comma-separated or one per line
- Partial success handling: valid numbers are sent even when some are invalid, with detailed feedback
- Full browser-based test suite with 15 tests and 26 before/after screenshots

### Changed
- SMS Sender phone field changed from `Char` to `Text` for multi-line input
- SMS Sender shows per-number validation results when bulk sending with invalid numbers
- "Gateway Enabled" pill restyled to match "Connected" pill (consistent light green)
- User-facing labels renamed from "Wizard" to "SMS Sender"

### Fixed
- Template body field now displays full width in form view
- `clean_message()` properly strips HTML tags (converts `<br>` to newline first)
- Post-init hook migrates old `#placeholder#` notation to `{placeholder}` in templates
- Odoo asset cache stale after CSS updates

## [0.1.0] - 2026-03-09

### Added
- Initial module scaffolding and architecture
- kwtSMS gateway integration (send, balance, senderid, coverage, validate)
- Gateway configuration page with credentials, test mode, notifications
- Dashboard with balance, stats, quick actions, notification status
- SMS notification hooks for sale orders and stock deliveries
- Phone number normalization and validation (Arabic/Hindi digits, GCC prefixes)
- Multilingual SMS templates (English + Arabic) for 5 event types
- SMS message logging with full API responses
- Bulk SMS with automatic batching (200+ numbers)
- Test mode support (`test=1`)
- SMS Sender dialog for ad-hoc messaging from any record
- Help page with API documentation and FAQ
