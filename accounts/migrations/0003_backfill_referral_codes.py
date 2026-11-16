import secrets

from django.db import migrations


def backfill_referral_codes(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    existing = set(User.objects.exclude(referral_code=None).values_list('referral_code', flat=True))
    for coach in User.objects.filter(role='coach', referral_code=None):
        for _ in range(10):
            code = secrets.token_urlsafe(8)
            if code not in existing:
                existing.add(code)
                coach.referral_code = code
                coach.save(update_fields=['referral_code'])
                break


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_referral_code'),
    ]

    operations = [
        migrations.RunPython(backfill_referral_codes, noop_reverse),
    ]
