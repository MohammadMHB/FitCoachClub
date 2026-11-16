from io import StringIO
from datetime import timedelta

from django.test import TestCase, Client
from django.core.management import call_command
from django.utils import timezone

from accounts.models import User, LoginAttempt
from accounts.test_helpers import make_admin
from coach.models import Notification


class LoginRateLimitTests(TestCase):
    """محدودسازی تلاش‌های ورود ناموفق (جلوگیری از brute-force)."""

    def setUp(self):
        self.admin = make_admin(username='admin_ratelimit')
        self.client = Client()

    def test_failed_login_is_logged(self):
        self.client.post('/accounts/login/', {'username': 'nope', 'password': 'wrong'},
                          REMOTE_ADDR='10.0.0.1')
        self.assertEqual(LoginAttempt.objects.filter(ip_address='10.0.0.1').count(), 1)

    def test_successful_login_not_logged_as_attempt(self):
        self.client.post('/accounts/login/', {'username': 'admin_ratelimit', 'password': 'pass12345'},
                          REMOTE_ADDR='10.0.0.2')
        self.assertEqual(LoginAttempt.objects.filter(ip_address='10.0.0.2').count(), 0)

    def test_sixth_failed_attempt_is_blocked(self):
        for _ in range(5):
            self.client.post('/accounts/login/', {'username': 'nope', 'password': 'wrong'},
                              REMOTE_ADDR='10.0.0.3')
        resp = self.client.post('/accounts/login/', {'username': 'nope', 'password': 'wrong'},
                                 REMOTE_ADDR='10.0.0.3')
        self.assertIn('موقتاً بسته شده', resp.content.decode('utf-8'))

    def test_even_correct_password_is_blocked_after_limit(self):
        for _ in range(5):
            self.client.post('/accounts/login/', {'username': 'admin_ratelimit', 'password': 'wrong'},
                              REMOTE_ADDR='10.0.0.4')
        resp = self.client.post('/accounts/login/', {'username': 'admin_ratelimit', 'password': 'pass12345'},
                                 REMOTE_ADDR='10.0.0.4')
        content = resp.content.decode('utf-8')
        self.assertIn('موقتاً بسته شده', content)
        # واقعاً لاگین نشده باشه
        resp2 = self.client.get('/admin-panel/')
        self.assertNotEqual(resp2.status_code, 200)

    def test_different_ip_is_not_affected(self):
        for _ in range(5):
            self.client.post('/accounts/login/', {'username': 'nope', 'password': 'wrong'},
                              REMOTE_ADDR='10.0.0.5')
        resp = self.client.post('/accounts/login/', {'username': 'nope', 'password': 'wrong'},
                                 REMOTE_ADDR='10.0.0.6')
        self.assertNotIn('موقتاً بسته شده', resp.content.decode('utf-8'))

    def test_old_attempts_outside_window_dont_count(self):
        old_time = timezone.now() - timedelta(minutes=30)
        for _ in range(5):
            a = LoginAttempt.objects.create(ip_address='10.0.0.7', username_tried='nope')
            LoginAttempt.objects.filter(pk=a.pk).update(created_at=old_time)
        resp = self.client.post('/accounts/login/', {'username': 'nope', 'password': 'wrong'},
                                 REMOTE_ADDR='10.0.0.7')
        self.assertNotIn('موقتاً بسته شده', resp.content.decode('utf-8'))


class CleanupOldDataCommandTests(TestCase):
    """دستور مدیریتی cleanup_old_data که برای اجرای روزانه با cron طراحی شده."""

    def setUp(self):
        self.admin = make_admin(username='admin_cleanup')

    def test_old_login_attempts_are_removed(self):
        old_time = timezone.now() - timedelta(hours=48)
        recent = LoginAttempt.objects.create(ip_address='1.1.1.1', username_tried='x')
        old = LoginAttempt.objects.create(ip_address='2.2.2.2', username_tried='y')
        LoginAttempt.objects.filter(pk=old.pk).update(created_at=old_time)

        call_command('cleanup_old_data', stdout=StringIO())

        self.assertTrue(LoginAttempt.objects.filter(pk=recent.pk).exists())
        self.assertFalse(LoginAttempt.objects.filter(pk=old.pk).exists())

    def test_old_read_notifications_are_removed_but_unread_kept(self):
        old_time = timezone.now() - timedelta(days=120)
        old_read = Notification.objects.create(
            recipient=self.admin, notif_type='system', title='قدیمی', message='...', is_read=True)
        Notification.objects.filter(pk=old_read.pk).update(created_at=old_time)

        old_unread = Notification.objects.create(
            recipient=self.admin, notif_type='system', title='قدیمی نخونده', message='...', is_read=False)
        Notification.objects.filter(pk=old_unread.pk).update(created_at=old_time)

        recent_read = Notification.objects.create(
            recipient=self.admin, notif_type='system', title='جدید', message='...', is_read=True)

        call_command('cleanup_old_data', stdout=StringIO())

        self.assertFalse(Notification.objects.filter(pk=old_read.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=old_unread.pk).exists())
        self.assertTrue(Notification.objects.filter(pk=recent_read.pk).exists())

    def test_dry_run_deletes_nothing(self):
        old_time = timezone.now() - timedelta(hours=48)
        old = LoginAttempt.objects.create(ip_address='3.3.3.3', username_tried='z')
        LoginAttempt.objects.filter(pk=old.pk).update(created_at=old_time)

        out = StringIO()
        call_command('cleanup_old_data', '--dry-run', stdout=out)

        self.assertTrue(LoginAttempt.objects.filter(pk=old.pk).exists())
        self.assertIn('dry-run', out.getvalue())
