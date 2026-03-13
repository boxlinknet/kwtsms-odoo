"""Tests for phone_utils module.

Covers normalization, validation, message cleaning, and SMS part counting.
Test cases aligned with kwtSMS JS client (github.com/boxlinknet/kwtsms-js).
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.kwtsms_sms.tools.phone_utils import (
    normalize_phone,
    validate_phone,
    validate_phone_list,
    find_country_code,
    validate_phone_format,
    clean_message,
    count_sms_parts,
)


@tagged('post_install', '-at_install')
class TestNormalizePhone(TransactionCase):
    """Test phone number normalization."""

    def test_strip_plus(self):
        self.assertEqual(normalize_phone('+96598765432'), '96598765432')

    def test_strip_double_zero(self):
        self.assertEqual(normalize_phone('0096598765432'), '96598765432')

    def test_strip_spaces(self):
        self.assertEqual(normalize_phone('965 9876 5432'), '96598765432')

    def test_strip_dashes(self):
        self.assertEqual(normalize_phone('965-9876-5432'), '96598765432')

    def test_strip_dots(self):
        self.assertEqual(normalize_phone('965.9876.5432'), '96598765432')

    def test_strip_parentheses(self):
        self.assertEqual(normalize_phone('(965) 98765432'), '96598765432')

    def test_arabic_indic_digits(self):
        """Arabic-Indic digits U+0660-U+0669."""
        self.assertEqual(
            normalize_phone('\u0669\u0666\u0665\u0669\u0668\u0667\u0666\u0665\u0664\u0663\u0662'),
            '96598765432',
        )

    def test_persian_digits(self):
        """Extended Arabic-Indic / Persian digits U+06F0-U+06F9."""
        self.assertEqual(
            normalize_phone('\u06f9\u06f6\u06f5\u06f9\u06f8\u06f7\u06f6\u06f5\u06f4\u06f3\u06f2'),
            '96598765432',
        )

    def test_mixed_arabic_latin(self):
        """Mixed Arabic-Indic and Latin digits."""
        self.assertEqual(normalize_phone('965\u0669\u0668\u0667\u0666\u0665\u0664\u0663\u0662'), '96598765432')

    def test_arabic_indic_with_plus(self):
        self.assertEqual(
            normalize_phone('+\u0669\u0666\u0665\u0669\u0668\u0667\u0666\u0665\u0664\u0663\u0662'),
            '96598765432',
        )

    def test_arabic_indic_with_double_zero(self):
        self.assertEqual(
            normalize_phone('\u0660\u0660\u0669\u0666\u0665\u0669\u0668\u0667\u0666\u0665\u0664\u0663\u0662'),
            '96598765432',
        )

    def test_arabic_indic_with_spaces(self):
        self.assertEqual(
            normalize_phone('\u0669\u0666\u0665 \u0669\u0668\u0667\u0666 \u0665\u0664\u0663\u0662'),
            '96598765432',
        )

    def test_arabic_indic_with_dashes(self):
        self.assertEqual(
            normalize_phone('\u0669\u0666\u0665-\u0669\u0668\u0667\u0666-\u0665\u0664\u0663\u0662'),
            '96598765432',
        )

    def test_mixed_arabic_latin_dashes(self):
        self.assertEqual(normalize_phone('+\u0669\u0666\u0665-9876-5432'), '96598765432')

    def test_empty_string(self):
        self.assertEqual(normalize_phone(''), '')

    def test_none(self):
        self.assertEqual(normalize_phone(None), '')


@tagged('post_install', '-at_install')
class TestValidatePhone(TransactionCase):
    """Test phone number validation."""

    def test_valid_with_plus(self):
        number, error = validate_phone('+96598765432')
        self.assertEqual(number, '96598765432')
        self.assertIsNone(error)

    def test_valid_with_double_zero(self):
        number, error = validate_phone('0096598765432')
        self.assertEqual(number, '96598765432')
        self.assertIsNone(error)

    def test_valid_with_spaces(self):
        number, error = validate_phone('965 9876 5432')
        self.assertEqual(number, '96598765432')
        self.assertIsNone(error)

    def test_valid_arabic_indic(self):
        number, error = validate_phone('\u0669\u0666\u0665\u0669\u0668\u0667\u0666\u0665\u0664\u0663\u0662')
        self.assertEqual(number, '96598765432')
        self.assertIsNone(error)

    def test_valid_min_length_7_digits(self):
        """7-digit number with no matching country code passes generic check."""
        number, error = validate_phone('2991234')
        self.assertEqual(number, '2991234')
        self.assertIsNone(error)

    def test_valid_max_length_15_digits(self):
        """15-digit number with no matching country code passes generic check."""
        number, error = validate_phone('299123456789012')
        self.assertEqual(number, '299123456789012')
        self.assertIsNone(error)

    def test_empty_string(self):
        number, error = validate_phone('')
        self.assertIsNone(number)
        self.assertEqual(error, 'phone number is empty')

    def test_whitespace_only(self):
        number, error = validate_phone('   ')
        self.assertIsNone(number)
        self.assertEqual(error, 'phone number is empty')

    def test_none_value(self):
        number, error = validate_phone(None)
        self.assertIsNone(number)
        self.assertEqual(error, 'phone number is None')

    def test_email_address(self):
        number, error = validate_phone('user@email.com')
        self.assertIsNone(number)
        self.assertEqual(error, 'looks like an email')

    def test_too_short_6_digits(self):
        number, error = validate_phone('123456')
        self.assertIsNone(number)
        self.assertEqual(error, 'too short')

    def test_too_short_3_digits(self):
        number, error = validate_phone('123')
        self.assertIsNone(number)
        self.assertEqual(error, 'too short')

    def test_too_long_16_digits(self):
        number, error = validate_phone('1234567890123456')
        self.assertIsNone(number)
        self.assertEqual(error, 'too long')

    def test_no_digits(self):
        number, error = validate_phone('abc')
        self.assertIsNone(number)
        self.assertEqual(error, 'no digits found')

    def test_no_digits_symbols_only(self):
        number, error = validate_phone('+-.()')
        self.assertIsNone(number)
        self.assertEqual(error, 'no digits found')


@tagged('post_install', '-at_install')
class TestFindCountryCode(TransactionCase):
    """Test country code detection from normalized numbers."""

    def test_kuwait_965(self):
        self.assertEqual(find_country_code('96598765432'), '965')

    def test_saudi_966(self):
        self.assertEqual(find_country_code('966512345678'), '966')

    def test_uae_971(self):
        self.assertEqual(find_country_code('971501234567'), '971')

    def test_egypt_20(self):
        self.assertEqual(find_country_code('201012345678'), '20')

    def test_usa_1(self):
        self.assertEqual(find_country_code('12125551234'), '1')

    def test_uk_44(self):
        self.assertEqual(find_country_code('447911123456'), '44')

    def test_india_91(self):
        self.assertEqual(find_country_code('919876543210'), '91')

    def test_unknown_country_returns_none(self):
        """Number with no matching country code returns None."""
        self.assertIsNone(find_country_code('2991234567'))

    def test_three_digit_code_priority(self):
        """3-digit codes are matched before 2-digit (e.g. 965 not 96)."""
        self.assertEqual(find_country_code('96598765432'), '965')


@tagged('post_install', '-at_install')
class TestValidatePhoneFormat(TransactionCase):
    """Test country-specific phone format validation."""

    # --- Kuwait (965) ---
    def test_kuwait_valid_9x(self):
        valid, error = validate_phone_format('96598765432')
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_kuwait_valid_5x(self):
        valid, error = validate_phone_format('96551234567')
        self.assertTrue(valid)

    def test_kuwait_valid_6x(self):
        valid, error = validate_phone_format('96566778899')
        self.assertTrue(valid)

    def test_kuwait_valid_4x(self):
        valid, error = validate_phone_format('96541234567')
        self.assertTrue(valid)

    def test_kuwait_wrong_length(self):
        """Kuwait expects 8 local digits, 7 should fail."""
        valid, error = validate_phone_format('9659876543')
        self.assertFalse(valid)
        self.assertIn('Kuwait', error)
        self.assertIn('8 digits', error)

    def test_kuwait_wrong_prefix(self):
        """Kuwait mobile must start with 4,5,6,9. Starting with 1 fails."""
        valid, error = validate_phone_format('96512345678')
        self.assertFalse(valid)
        self.assertIn('mobile', error)

    # --- Saudi Arabia (966) ---
    def test_saudi_valid(self):
        valid, error = validate_phone_format('966512345678')
        self.assertTrue(valid)

    def test_saudi_wrong_prefix(self):
        """Saudi mobile must start with 5."""
        valid, error = validate_phone_format('966912345678')
        self.assertFalse(valid)
        self.assertIn('Saudi', error)

    def test_saudi_wrong_length(self):
        valid, error = validate_phone_format('96651234567')
        self.assertFalse(valid)
        self.assertIn('9 digits', error)

    # --- UAE (971) ---
    def test_uae_valid(self):
        valid, error = validate_phone_format('971501234567')
        self.assertTrue(valid)

    def test_uae_wrong_prefix(self):
        valid, error = validate_phone_format('971901234567')
        self.assertFalse(valid)
        self.assertIn('UAE', error)

    # --- Egypt (20) ---
    def test_egypt_valid(self):
        valid, error = validate_phone_format('201012345678')
        self.assertTrue(valid)

    def test_egypt_wrong_prefix(self):
        valid, error = validate_phone_format('205012345678')
        self.assertFalse(valid)

    # --- USA (1) ---
    def test_usa_valid(self):
        valid, error = validate_phone_format('12125551234')
        self.assertTrue(valid)

    def test_usa_wrong_length(self):
        """USA expects 10 local digits."""
        valid, error = validate_phone_format('1212555123')
        self.assertFalse(valid)
        self.assertIn('10 digits', error)

    # --- UK (44) ---
    def test_uk_valid(self):
        valid, error = validate_phone_format('447911123456')
        self.assertTrue(valid)

    def test_uk_wrong_prefix(self):
        """UK mobile must start with 7."""
        valid, error = validate_phone_format('441911123456')
        self.assertFalse(valid)

    # --- Unknown country passes through ---
    def test_unknown_country_passes(self):
        """Numbers not matching any country code pass generic check."""
        valid, error = validate_phone_format('2991234567')
        self.assertTrue(valid)
        self.assertIsNone(error)


@tagged('post_install', '-at_install')
class TestValidatePhoneCountryIntegration(TransactionCase):
    """Test that validate_phone() integrates country-specific checks."""

    def test_valid_kuwait(self):
        number, error = validate_phone('+96598765432')
        self.assertEqual(number, '96598765432')
        self.assertIsNone(error)

    def test_invalid_kuwait_prefix(self):
        """Kuwait number starting with 1 should be rejected."""
        number, error = validate_phone('+96512345678')
        self.assertIsNone(number)
        self.assertIn('mobile', error)

    def test_invalid_kuwait_length(self):
        """Kuwait number with wrong local length should be rejected."""
        number, error = validate_phone('+9659876543')
        self.assertIsNone(number)
        self.assertIn('8 digits', error)

    def test_valid_saudi(self):
        number, error = validate_phone('+966512345678')
        self.assertEqual(number, '966512345678')
        self.assertIsNone(error)

    def test_valid_usa(self):
        number, error = validate_phone('+12125551234')
        self.assertEqual(number, '12125551234')
        self.assertIsNone(error)

    def test_valid_unknown_country(self):
        """Unknown country code with valid E.164 length passes."""
        number, error = validate_phone('2991234567')
        self.assertEqual(number, '2991234567')
        self.assertIsNone(error)

    def test_valid_bahrain(self):
        number, error = validate_phone('+97336123456')
        self.assertEqual(number, '97336123456')
        self.assertIsNone(error)

    def test_valid_qatar(self):
        number, error = validate_phone('+97433123456')
        self.assertEqual(number, '97433123456')
        self.assertIsNone(error)

    def test_valid_oman(self):
        number, error = validate_phone('+96892123456')
        self.assertEqual(number, '96892123456')
        self.assertIsNone(error)

    def test_valid_jordan(self):
        number, error = validate_phone('+962791234567')
        self.assertEqual(number, '962791234567')
        self.assertIsNone(error)

    def test_invalid_jordan_prefix(self):
        number, error = validate_phone('+962591234567')
        self.assertIsNone(number)
        self.assertIn('mobile', error)


@tagged('post_install', '-at_install')
class TestValidatePhoneList(TransactionCase):
    """Test phone list validation."""

    def test_mixed_list(self):
        valid, invalid = validate_phone_list([
            '+96598765432',
            'user@email.com',
            '123',
        ])
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0], '96598765432')
        self.assertEqual(len(invalid), 2)

    def test_all_valid(self):
        valid, invalid = validate_phone_list([
            '96598765432',
            '+96555512345',
            '0096566778899',
        ])
        self.assertEqual(len(valid), 3)
        self.assertEqual(len(invalid), 0)

    def test_all_invalid(self):
        valid, invalid = validate_phone_list([
            'user@email.com',
            '123',
            '',
        ])
        self.assertEqual(len(valid), 0)
        self.assertEqual(len(invalid), 3)

    def test_empty_list(self):
        valid, invalid = validate_phone_list([])
        self.assertEqual(len(valid), 0)
        self.assertEqual(len(invalid), 0)


@tagged('post_install', '-at_install')
class TestCleanMessage(TransactionCase):
    """Test message cleaning."""

    def test_strip_single_emoji(self):
        result = clean_message('Hello World \U0001f600')
        self.assertNotIn('\U0001f600', result)
        self.assertIn('Hello World', result)

    def test_strip_multiple_emojis(self):
        result = clean_message('Hi \U0001f600\U0001f389\U0001f680 there')
        self.assertNotIn('\U0001f600', result)
        self.assertNotIn('\U0001f389', result)
        self.assertNotIn('\U0001f680', result)
        self.assertIn('Hi', result)
        self.assertIn('there', result)

    def test_strip_emoji_at_end(self):
        result = clean_message('Order confirmed \U0001f389')
        self.assertEqual(result, 'Order confirmed')

    def test_arabic_indic_digits_converted(self):
        result = clean_message('OTP: \u0661\u0662\u0663\u0664\u0665\u0666')
        self.assertEqual(result, 'OTP: 123456')

    def test_persian_digits_converted(self):
        result = clean_message('Code: \u06f1\u06f2\u06f3\u06f4\u06f5\u06f6')
        self.assertEqual(result, 'Code: 123456')

    def test_zero_width_space_stripped(self):
        result = clean_message('Hello\u200bWorld')
        self.assertEqual(result, 'HelloWorld')

    def test_bom_stripped(self):
        result = clean_message('\ufeffHello World')
        self.assertEqual(result, 'Hello World')

    def test_soft_hyphen_stripped(self):
        result = clean_message('soft\u00adhyphen')
        self.assertEqual(result, 'softhyphen')

    def test_ltr_rtl_marks_stripped(self):
        result = clean_message('Hello\u200eWorld\u200f!')
        self.assertEqual(result, 'HelloWorld!')

    def test_directional_formatting_stripped(self):
        result = clean_message('Test\u202aLTR\u202c')
        self.assertEqual(result, 'TestLTR')

    def test_word_joiner_stripped(self):
        result = clean_message('No\u2060Break')
        self.assertEqual(result, 'NoBreak')

    def test_arabic_text_preserved(self):
        arabic = '\u0645\u0631\u062d\u0628\u0627'  # marhaba
        result = clean_message(arabic)
        self.assertEqual(result, arabic)

    def test_arabic_text_with_emoji_stripped(self):
        """Arabic text with emoji: text preserved, emoji stripped."""
        arabic = '\u0645\u0631\u062d\u0628\u0627'
        result = clean_message(arabic + ' \U0001f600')
        self.assertEqual(result, arabic)

    def test_newlines_preserved(self):
        result = clean_message('Line 1\nLine 2')
        self.assertEqual(result, 'Line 1\nLine 2')

    def test_mixed_content(self):
        """Real-world message: Arabic + digits + emoji + control chars."""
        msg = '\ufeff\u0645\u0631\u062d\u0628\u0627 \U0001f600 OTP: \u0661\u0662\u0663\u200b'
        result = clean_message(msg)
        self.assertIn('\u0645\u0631\u062d\u0628\u0627', result)  # Arabic preserved
        self.assertIn('OTP: 123', result)  # Digits converted
        self.assertNotIn('\U0001f600', result)  # Emoji stripped
        self.assertNotIn('\ufeff', result)  # BOM stripped
        self.assertNotIn('\u200b', result)  # ZWS stripped

    def test_empty_message(self):
        self.assertEqual(clean_message(''), '')
        self.assertEqual(clean_message(None), '')

    def test_whitespace_collapsed(self):
        """Multiple spaces from removals should be collapsed."""
        result = clean_message('Hello   World')
        self.assertEqual(result, 'Hello World')

    # --- HTML tag stripping ---

    def test_strip_simple_html_tags(self):
        result = clean_message('<b>Bold</b> and <i>italic</i>')
        self.assertEqual(result, 'Bold and italic')

    def test_strip_html_paragraph(self):
        result = clean_message('<p>Hello World</p>')
        self.assertEqual(result, 'Hello World')

    def test_strip_html_div_span(self):
        result = clean_message('<div><span>Nested</span></div>')
        self.assertEqual(result, 'Nested')

    def test_html_br_to_newline(self):
        result = clean_message('Line 1<br>Line 2')
        self.assertEqual(result, 'Line 1\nLine 2')

    def test_html_br_slash_to_newline(self):
        result = clean_message('Line 1<br/>Line 2')
        self.assertEqual(result, 'Line 1\nLine 2')

    def test_html_br_space_slash_to_newline(self):
        result = clean_message('Line 1<br />Line 2')
        self.assertEqual(result, 'Line 1\nLine 2')

    def test_strip_html_with_attributes(self):
        result = clean_message('<a href="https://example.com">Click</a>')
        self.assertEqual(result, 'Click')

    def test_strip_html_with_class(self):
        result = clean_message('<span class="red bold">Text</span>')
        self.assertEqual(result, 'Text')

    def test_html_entities_decoded(self):
        result = clean_message('5 &gt; 3 &amp; 3 &lt; 5')
        self.assertEqual(result, '5 > 3 & 3 < 5')

    def test_html_nbsp_to_space(self):
        result = clean_message('Hello&nbsp;World')
        self.assertEqual(result, 'Hello World')

    def test_html_quot_decoded(self):
        result = clean_message('He said &quot;hello&quot;')
        self.assertEqual(result, 'He said "hello"')

    def test_html_rich_text_paste(self):
        """Simulates pasting from a rich text editor."""
        html = '<div style="font-family: Arial;"><p><b>Order</b> #123 confirmed!</p></div>'
        result = clean_message(html)
        self.assertEqual(result, 'Order #123 confirmed!')

    def test_strip_script_tag(self):
        """Script tags should be stripped (content preserved as plain text)."""
        result = clean_message('<script>alert("xss")</script>Hello')
        self.assertEqual(result, 'alert("xss")Hello')

    def test_html_only_tags_empty_result(self):
        """Message with only HTML tags and no text content."""
        result = clean_message('<br><br><br>')
        self.assertEqual(result, '')

    # --- Emoji edge cases ---

    def test_compound_emoji_family(self):
        """Compound emoji (family) with ZWJ sequences."""
        result = clean_message('Hi \U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466 there')
        self.assertIn('Hi', result)
        self.assertIn('there', result)
        self.assertNotIn('\U0001f468', result)

    def test_flag_emoji(self):
        """Country flag emoji (regional indicators)."""
        result = clean_message('Kuwait \U0001f1f0\U0001f1fc is great')
        self.assertIn('Kuwait', result)
        self.assertIn('is great', result)

    def test_emoji_only_message(self):
        """Message containing only emojis should return empty."""
        result = clean_message('\U0001f600\U0001f389\U0001f680')
        self.assertEqual(result, '')

    def test_emoji_with_skin_tone(self):
        """Emoji with skin tone modifier."""
        result = clean_message('Hello \U0001f44b\U0001f3fd World')
        self.assertIn('Hello', result)
        self.assertIn('World', result)

    def test_emoji_number_keycap(self):
        """Number keycap emojis (digit + variation selector + keycap)."""
        result = clean_message('Press 1\ufe0f\u20e3 now')
        self.assertIn('Press', result)
        self.assertIn('now', result)

    # --- Combined HTML + emoji ---

    def test_html_with_emoji(self):
        """HTML tags and emojis both stripped."""
        result = clean_message('<b>Hello</b> \U0001f600 <i>World</i>')
        self.assertEqual(result, 'Hello World')

    def test_html_emoji_arabic_digits(self):
        """Combined: HTML + emoji + Arabic digits."""
        msg = '<p>OTP: \u0661\u0662\u0663 \U0001f600</p>'
        result = clean_message(msg)
        self.assertEqual(result, 'OTP: 123')


@tagged('post_install', '-at_install')
class TestCountSmsParts(TransactionCase):
    """Test SMS parts counting."""

    def test_short_english(self):
        chars, pages, is_unicode = count_sms_parts('Hello')
        self.assertEqual(chars, 5)
        self.assertEqual(pages, 1)
        self.assertFalse(is_unicode)

    def test_160_chars_english(self):
        msg = 'A' * 160
        chars, pages, is_unicode = count_sms_parts(msg)
        self.assertEqual(chars, 160)
        self.assertEqual(pages, 1)
        self.assertFalse(is_unicode)

    def test_161_chars_english(self):
        msg = 'A' * 161
        chars, pages, is_unicode = count_sms_parts(msg)
        self.assertEqual(chars, 161)
        self.assertEqual(pages, 2)
        self.assertFalse(is_unicode)

    def test_306_chars_english_two_pages(self):
        msg = 'A' * 306
        chars, pages, is_unicode = count_sms_parts(msg)
        self.assertEqual(chars, 306)
        self.assertEqual(pages, 2)
        self.assertFalse(is_unicode)

    def test_307_chars_english_three_pages(self):
        msg = 'A' * 307
        chars, pages, is_unicode = count_sms_parts(msg)
        self.assertEqual(chars, 307)
        self.assertEqual(pages, 3)
        self.assertFalse(is_unicode)

    def test_70_chars_arabic(self):
        msg = '\u0645' * 70
        chars, pages, is_unicode = count_sms_parts(msg)
        self.assertEqual(chars, 70)
        self.assertEqual(pages, 1)
        self.assertTrue(is_unicode)

    def test_71_chars_arabic(self):
        msg = '\u0645' * 71
        chars, pages, is_unicode = count_sms_parts(msg)
        self.assertEqual(chars, 71)
        self.assertEqual(pages, 2)
        self.assertTrue(is_unicode)

    def test_max_7_pages_capped(self):
        """kwtSMS max is 7 pages, should cap even for longer messages."""
        msg = 'A' * 2000  # ~14 pages in GSM-7
        chars, pages, is_unicode = count_sms_parts(msg)
        self.assertEqual(pages, 7)

    def test_empty_message(self):
        chars, pages, is_unicode = count_sms_parts('')
        self.assertEqual(chars, 0)
        self.assertEqual(pages, 0)
        self.assertFalse(is_unicode)
