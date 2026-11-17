import json
from datetime import timedelta
from unittest.mock import patch, MagicMock
from urllib.parse import parse_qs

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import User, OTPChallenge, OTPRateLimit
from accounts.phone import normalize_mobile
from accounts import otp
from coach.sms import send_otp_sms, send_sms


@override_settings(OTP_LOGIN_ENABLED=True, MELIPAYAMAK_USERNAME='test-account',
                   MELIPAYAMAK_PASSWORD='test-secret', MELIPAYAMAK_SENDER='500000',
                   MELIPAYAMAK_OTP_BODY_ID='')
class OTPLoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='otp-user', password='password123',
                                             role='coach', phone='09123456789')
        self.sent = patch('accounts.otp.send_otp_sms', return_value=True).start()
        self.random = patch('accounts.otp.secrets.randbelow', return_value=123456).start()
        self.addCleanup(patch.stopall)

    def request(self, client=None, phone='09123456789', **data):
        return (client or self.client).post('/accounts/otp/request/', {'phone': phone, **data})

    def verify(self, client=None, code='123456'):
        return (client or self.client).post('/accounts/otp/verify/', {'code': code})

    def challenge(self):
        return OTPChallenge.objects.get(pk=self.client.session['otp_challenge_id'])

    def test_phone_variants_and_persian_digits_are_canonical(self):
        for value in ['۰۹۱۲۳۴۵۶۷۸۹', '+98 912-345-6789', '00989123456789', '989123456789']:
            self.assertEqual(normalize_mobile(value), self.user.phone_normalized)
        for invalid in ['', '123', '091234567890', '+12025550100', '09abcdefgh9']:
            with self.assertRaises(ValidationError):
                normalize_mobile(invalid)

    def test_phone_update_keeps_lookup_index_in_sync(self):
        self.user.phone = '+989351234567'
        self.user.save(update_fields=['phone'])
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_normalized, '09351234567')

    def test_default_login_is_otp_and_password_fallback_is_available(self):
        response = self.client.get('/accounts/login/')
        self.assertContains(response, 'دریافت کد ورود')
        self.assertContains(response, 'method=password')
        self.assertContains(self.client.get('/accounts/login/?method=password'), 'name="username"')

    def test_code_is_sent_but_not_stored_or_rendered_in_plain_text(self):
        self.assertRedirects(self.request(), '/accounts/otp/verify/')
        self.sent.assert_called_once_with('09123456789', '123456')
        self.assertNotEqual(self.challenge().code_hash, '123456')
        self.assertNotContains(self.client.get('/accounts/otp/verify/'), '123456</')
        self.assertNotIn('123456', dict(self.client.session).values())

    def test_all_roles_can_login_and_reach_their_own_dashboard(self):
        for index, role in enumerate(['admin', 'coach', 'trainee']):
            user = User.objects.create_user(username='role'+role, password='x', role=role,
                                             phone=f'0935000000{index}')
            client = Client()
            self.assertEqual(self.request(client, user.phone).status_code, 302)
            self.assertEqual(self.verify(client).status_code, 302)
            self.assertEqual(int(client.session['_auth_user_id']), user.pk)
            expected = {'admin': '/admin-panel/', 'coach': '/coach/', 'trainee': '/trainee/'}[role]
            self.assertRedirects(client.get('/'), expected, fetch_redirect_response=False)

    def test_persian_code_is_accepted(self):
        self.request()
        self.verify(code='۱۲۳۴۵۶')
        self.assertIn('_auth_user_id', self.client.session)

    def test_code_cannot_be_replayed_even_from_an_old_browser_session(self):
        self.request()
        old_state = dict(self.client.session)
        self.verify()
        other = Client()
        session = other.session
        session.update(old_state)
        session.save()
        self.verify(other)
        self.assertNotIn('_auth_user_id', other.session)

    def test_browser_without_request_cannot_verify_another_browsers_code(self):
        self.request()
        other = Client()
        self.assertRedirects(self.verify(other), '/accounts/login/')
        self.assertNotIn('_auth_user_id', other.session)

    def test_expired_code_is_rejected(self):
        self.request()
        OTPChallenge.objects.filter(pk=self.challenge().pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.verify()
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_five_wrong_codes_lock_challenge_even_if_next_code_is_correct(self):
        self.request()
        for _ in range(5):
            self.verify(code='654321')
        self.verify()
        self.assertEqual(self.challenge().attempts, 5)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_malformed_codes_also_count_as_failed_attempts(self):
        self.request()
        self.verify(code='not-a-code')
        self.assertEqual(self.challenge().attempts, 1)

    def test_last_allowed_correct_attempt_can_succeed(self):
        self.request()
        for _ in range(4):
            self.verify(code='000000')
        self.verify()
        self.assertIn('_auth_user_id', self.client.session)

    def test_resend_is_limited_across_browsers_and_ip_changes(self):
        self.request()
        other = Client(REMOTE_ADDR='192.0.2.12')
        self.assertEqual(self.request(other).status_code, 429)
        self.sent.assert_called_once()

    def test_resend_invalidates_previous_code(self):
        self.request()
        old_id = self.challenge().pk
        OTPRateLimit.objects.update(next_allowed_at=timezone.now()-timedelta(seconds=1))
        self.random.return_value = 654321
        self.request()
        self.assertIsNotNone(OTPChallenge.objects.get(pk=old_id).consumed_at)
        self.verify(code='123456')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.verify(code='654321')
        self.assertIn('_auth_user_id', self.client.session)

    def test_window_reset_does_not_erase_the_last_send_cooldown(self):
        self.request()
        OTPRateLimit.objects.filter(key__startswith='phone:').update(
            window_start=timezone.now()-timedelta(seconds=901))
        self.assertEqual(self.request(Client()).status_code, 429)
        self.assertEqual(self.sent.call_count, 1)

    def test_phone_send_quota_survives_cooldowns(self):
        for _ in range(3):
            OTPRateLimit.objects.update(next_allowed_at=timezone.now()-timedelta(seconds=1))
            self.request()
        OTPRateLimit.objects.update(next_allowed_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.request(Client()).status_code, 429)
        self.assertEqual(self.sent.call_count, 3)

    @override_settings(OTP_SEND_LIMIT_IP=2)
    def test_ip_quota_covers_unknown_numbers_and_ignores_spoofed_header(self):
        for phone in ['09350000111', '09350000222']:
            self.request(phone=phone)
        response = self.client.post('/accounts/otp/request/', {'phone': '09350000333'},
                                    HTTP_X_FORWARDED_FOR='192.0.2.99')
        self.assertEqual(response.status_code, 429)
        self.sent.assert_not_called()

    def test_unknown_inactive_and_duplicate_numbers_never_send(self):
        self.request(phone='09350000999')
        self.user.is_active = False
        self.user.save()
        self.request()
        self.sent.assert_not_called()
        self.assertFalse(OTPChallenge.objects.exists())

    def test_duplicate_normalized_phone_never_selects_arbitrary_user(self):
        User.objects.create_user(username='duplicate', password='x', phone='+989123456789', is_active=False)
        self.assertRedirects(self.request(), '/accounts/otp/verify/')
        self.sent.assert_not_called()

    def test_account_disabled_after_delivery_cannot_login(self):
        self.request()
        self.user.is_active = False
        self.user.save()
        self.verify()
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_phone_changed_after_delivery_cannot_login(self):
        self.request()
        self.user.phone = '09351234567'
        self.user.save(update_fields=['phone'])
        self.verify()
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_new_duplicate_after_delivery_cannot_login(self):
        self.request()
        User.objects.create_user(username='later-duplicate', phone=self.user.phone)
        self.verify()
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_delivery_failure_cannot_be_used_to_login(self):
        self.sent.return_value = False
        self.request()
        self.assertIsNone(self.client.session['otp_challenge_id'])
        self.assertIsNotNone(OTPChallenge.objects.get().consumed_at)
        self.verify()
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_internal_next_is_preserved_but_external_next_is_rejected(self):
        self.request(next='/coach/exercises/')
        self.assertRedirects(self.verify(), '/coach/exercises/')
        client = Client(REMOTE_ADDR='192.0.2.3')
        OTPRateLimit.objects.all().delete()
        self.request(client, next='https://example.org/')
        self.assertRedirects(self.verify(client), '/', fetch_redirect_response=False)

    def test_password_login_also_rejects_external_redirect(self):
        response = self.client.post('/accounts/login/?next=https://example.org/',
                                    {'username': self.user.username, 'password': 'password123'})
        self.assertRedirects(response, '/', fetch_redirect_response=False)

    def test_csrf_is_required_for_request_and_verification(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.request(client).status_code, 403)
        self.assertEqual(self.verify(client).status_code, 403)

    @override_settings(MELIPAYAMAK_USERNAME='')
    def test_missing_configuration_fails_closed_and_exposes_password_fallback(self):
        self.assertContains(self.client.get('/accounts/login/'), 'ارسال پیامک هنوز تنظیم نشده')
        self.assertEqual(self.request().status_code, 503)
        self.sent.assert_not_called()

    @override_settings(OTP_LOGIN_ENABLED=False)
    def test_feature_can_be_disabled_without_locking_existing_users_out(self):
        self.assertContains(self.client.get('/accounts/login/'), 'name="username"')
        self.assertRedirects(self.request(), '/accounts/login/?method=password')

    def test_invalid_number_is_rejected_before_send(self):
        self.assertEqual(self.request(phone='not-a-number').status_code, 400)
        self.sent.assert_not_called()

    def test_cleanup_removes_old_otp_records_but_keeps_current_challenges(self):
        from django.core.management import call_command
        from io import StringIO
        self.request()
        old_id = self.challenge().pk
        OTPChallenge.objects.filter(pk=old_id).update(created_at=timezone.now()-timedelta(days=2))
        fresh = OTPChallenge.objects.create(user=self.user, phone=self.user.phone,
            code_hash='x'*64, expires_at=timezone.now()+timedelta(minutes=3))
        call_command('cleanup_old_data', '--dry-run', stdout=StringIO())
        self.assertTrue(OTPChallenge.objects.filter(pk=old_id).exists())
        call_command('cleanup_old_data', stdout=StringIO())
        self.assertFalse(OTPChallenge.objects.filter(pk=old_id).exists())
        self.assertTrue(OTPChallenge.objects.filter(pk=fresh.pk).exists())
        self.assertTrue(OTPRateLimit.objects.exists())

    def test_bad_session_challenge_id_does_not_crash(self):
        session = self.client.session
        session.update({'otp_phone': self.user.phone, 'otp_challenge_id': 'not-a-uuid'})
        session.save()
        self.assertEqual(self.verify().status_code, 200)


@override_settings(MELIPAYAMAK_USERNAME='test', MELIPAYAMAK_PASSWORD='test',
                   MELIPAYAMAK_SENDER='500000', MELIPAYAMAK_OTP_BODY_ID='')
class MelipayamakOTPTests(TestCase):
    def response(self, data):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(data).encode()
        return response

    @patch('coach.sms.urlopen')
    def test_direct_sms_payload_and_positive_receipt(self, transport):
        transport.return_value = self.response({'RetStatus': 1, 'Value': '123456789'})
        self.assertTrue(send_otp_sms('09123456789', '045678'))
        req = transport.call_args.args[0]
        payload = {key: value[0] for key, value in parse_qs(req.data.decode()).items()}
        self.assertEqual(payload['to'], '09123456789')
        self.assertIn('045678', payload['text'])
        self.assertEqual(payload['from'], '500000')

    @override_settings(MELIPAYAMAK_OTP_BODY_ID='1234', MELIPAYAMAK_SENDER='')
    @patch('coach.sms.urlopen')
    def test_service_pattern_payload(self, transport):
        transport.return_value = self.response({'RetStatus': 1, 'Value': '123456789'})
        self.assertTrue(send_otp_sms('09123456789', '045678'))
        req = transport.call_args.args[0]
        self.assertTrue(req.full_url.endswith('/BaseServiceNumber'))
        self.assertEqual(parse_qs(req.data.decode())['bodyId'], ['1234'])
        self.assertEqual(parse_qs(req.data.decode())['text'], ['045678'])

    @patch('coach.sms.urlopen')
    def test_http_success_with_provider_error_is_failure(self, transport):
        for result in [{'RetStatus': 1, 'Value': '-1'}, {'RetStatus': 0, 'Value': '123'},
                       {'RetStatus': 1, 'Value': 'invalid'}, []]:
            transport.return_value = self.response(result)
            self.assertFalse(send_otp_sms('09123456789', '123456'))

    @patch('coach.sms.urlopen', side_effect=TimeoutError)
    def test_timeout_fails_without_exposing_otp_or_credentials_in_logs(self, transport):
        with self.assertLogs('coach.sms', level='WARNING') as logs:
            self.assertFalse(send_otp_sms('09123456789', '654321'))
        self.assertNotIn('654321', ''.join(logs.output))
        self.assertNotIn('09123456789', ''.join(logs.output))

    @override_settings(MELIPAYAMAK_OTP_BODY_ID='bad-id')
    @patch('coach.sms.urlopen')
    def test_invalid_pattern_configuration_does_not_send(self, transport):
        self.assertFalse(send_otp_sms('09123456789', '123456'))
        transport.assert_not_called()
