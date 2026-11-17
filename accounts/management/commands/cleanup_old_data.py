"""
دستور نگهداری روزانه‌ی دیتابیس — برای اجرا با cron روی سرور طراحی شده،
نه به‌صورت دستی. کارهایی که انجام می‌ده:

  1. پاک کردن رکوردهای LoginAttempt قدیمی‌تر از ۲۴ ساعت (فقط برای محدود
     کردن تلاش‌های ورود ناموفق تو یه بازه‌ی کوتاه لازمن، نگه‌داشتن طولانی‌مدتشون
     فایده‌ای نداره و فقط جدول رو بزرگ می‌کنه).
  2. پاک کردن اعلان‌های خوانده‌شده‌ای که بیشتر از ۹۰ روزه ساخته شدن.
  3. پاک کردن چالش‌ها و محدودیت‌های ورود پیامکی قدیمی‌تر از ۲۴ ساعت.

نحوه‌ی وصل کردن به cron روی سرور (crontab -e):

    0 3 * * *  cd /path/to/fitcoach && /path/to/venv/bin/python manage.py cleanup_old_data >> /path/to/fitcoach/logs/cleanup.log 2>&1

یعنی هر روز ساعت ۳ بامداد اجرا می‌شه. مسیرها رو با مسیر واقعی روی سرورت
عوض کن. اگه صرفاً می‌خوای تست کنی چند تا ردیف پاک می‌شه بدون واقعاً پاک
کردن، از --dry-run استفاده کن.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from accounts.models import LoginAttempt, OTPChallenge, OTPRateLimit
from coach.models import Notification

LOGIN_ATTEMPT_MAX_AGE_HOURS = 24
READ_NOTIFICATION_MAX_AGE_DAYS = 90


class Command(BaseCommand):
    help = 'نگهداری دوره‌ای دیتابیس: پاک کردن تلاش‌های ورود قدیمی و اعلان‌های خوانده‌شده‌ی قدیمی (برای cron روزانه)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='فقط نشون بده چند ردیف پاک می‌شه، واقعاً پاکشون نکن.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()

        login_cutoff = now - timedelta(hours=LOGIN_ATTEMPT_MAX_AGE_HOURS)
        old_attempts = LoginAttempt.objects.filter(created_at__lt=login_cutoff)
        attempts_count = old_attempts.count()

        notif_cutoff = now - timedelta(days=READ_NOTIFICATION_MAX_AGE_DAYS)
        old_notifs = Notification.objects.filter(is_read=True, created_at__lt=notif_cutoff)
        notifs_count = old_notifs.count()

        otp_cutoff = now - timedelta(hours=24)
        old_challenges = OTPChallenge.objects.filter(created_at__lt=otp_cutoff)
        old_limits = OTPRateLimit.objects.filter(window_start__lt=otp_cutoff)
        otp_count = old_challenges.count() + old_limits.count()

        if dry_run:
            self.stdout.write(f'[dry-run] {otp_count} رکورد قدیمی ورود پیامکی حذف می‌شد.')
            self.stdout.write(f'[dry-run] {attempts_count} تلاش ورود قدیمی حذف می‌شد.')
            self.stdout.write(f'[dry-run] {notifs_count} اعلان خوانده‌شده‌ی قدیمی حذف می‌شد.')
            return

        old_challenges.delete()
        old_limits.delete()
        old_attempts.delete()
        old_notifs.delete()

        self.stdout.write(self.style.SUCCESS(
            f'{attempts_count} تلاش ورود قدیمی و {notifs_count} اعلان خوانده‌شده‌ی قدیمی پاک شد. '
            f'({now.strftime("%Y-%m-%d %H:%M")})'
        ))
