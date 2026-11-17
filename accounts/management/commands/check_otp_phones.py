"""Report accounts that cannot use SMS login without exposing phone numbers."""
from django.core.management.base import BaseCommand
from django.db.models import Count
from accounts.models import User


class Command(BaseCommand):
    help = 'بررسی حساب‌های فاقد شماره معتبر یا دارای شماره تکراری برای ورود پیامکی'

    def handle(self, *args, **options):
        missing = User.objects.filter(is_active=True, phone_normalized='')
        duplicates = User.objects.exclude(phone_normalized='').values('phone_normalized').annotate(
            total=Count('id')).filter(total__gt=1)
        self.stdout.write(f'حساب فعال بدون شماره معتبر: {missing.count()}')
        self.stdout.write(f'شماره‌های متصل به چند حساب: {duplicates.count()}')
        for user in missing.only('id', 'username'):
            self.stdout.write(f'شماره نامعتبر/خالی: id={user.pk}, username={user.username}')
        for duplicate in duplicates:
            for user in User.objects.filter(phone_normalized=duplicate['phone_normalized']).only('id', 'username'):
                self.stdout.write(f'شماره مشترک: id={user.pk}, username={user.username}')
