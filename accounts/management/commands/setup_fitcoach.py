"""
دستور راه‌اندازی اولیه FitCoach (فقط برای توسعه‌ی لوکال)
اجرا: python manage.py setup_fitcoach

برای هر کاربر نمونه یک رمز تصادفی ساخته و فقط یک‌بار در خروجی چاپ می‌شه.
(رمزهای ثابت مثل admin123 عمداً حذف شدن چون پروژه عمومیه.)
"""
import secrets

from django.core.management.base import BaseCommand
from django.db import transaction


def _pw():
    return secrets.token_urlsafe(9)


class Command(BaseCommand):
    help = 'راه‌اندازی اولیه - ساخت ادمین و کاربران نمونه با رمز تصادفی'

    def handle(self, *args, **options):
        from accounts.models import User, TraineeProfile

        created = []

        with transaction.atomic():
            if not User.objects.filter(username='admin').exists():
                pw = _pw()
                User.objects.create_superuser(
                    username='admin',
                    password=pw,
                    first_name='مدیر',
                    last_name='سیستم',
                    role='admin',
                )
                created.append(('ادمین', 'admin', pw))

            coach = User.objects.filter(username='coach1').first()
            if coach is None:
                pw = _pw()
                coach = User.objects.create_user(
                    username='coach1',
                    password=pw,
                    first_name='علی',
                    last_name='احمدی',
                    role='coach',
                    phone='09120000001',
                )
                created.append(('مربی', 'coach1', pw))

            if not User.objects.filter(username='trainee1').exists():
                pw = _pw()
                trainee_user = User.objects.create_user(
                    username='trainee1',
                    password=pw,
                    first_name='محمد',
                    last_name='رضایی',
                    role='trainee',
                    phone='09120000002',
                )
                TraineeProfile.objects.create(
                    user=trainee_user,
                    coach=coach,
                    weight=85.0,
                    height=178.0,
                    age=28,
                )
                created.append(('شاگرد', 'trainee1', pw))

        if not created:
            self.stdout.write('کاربران نمونه از قبل وجود دارن؛ چیزی ساخته نشد.')
            return

        self.stdout.write(self.style.SUCCESS('\n🎉 FitCoach آماده است! (این رمزها فقط همین یک‌بار نمایش داده می‌شن)\n'))
        self.stdout.write('=' * 40)
        for role, username, pw in created:
            self.stdout.write(f'{role}: {username} / {pw}')
        self.stdout.write('=' * 40)
