"""
ارسال پیامک از طریق ملی‌پیامک (Melipayamak)
مستندات: https://www.melipayamak.com/api/

تنظیمات لازم در settings.py:
    MELIPAYAMAK_USERNAME = '...'
    MELIPAYAMAK_PASSWORD = '...'
    MELIPAYAMAK_SENDER   = '...'   # شماره فرستنده

اگر این مقادیر خالی باشند، تابع send_sms به‌سادگی هیچ کاری نمی‌کند
(تا توسعه/تست بدون پیامک هم بدون خطا کار کند).
"""
import json
import logging
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from django.conf import settings

logger = logging.getLogger(__name__)

MELIPAYAMAK_URL = 'https://rest.payamak-panel.com/api/SendSMS/SendSMS'


def send_sms(to: str, text: str) -> bool:
    """
    ارسال پیامک به شماره `to` با متن `text`.
    در صورت موفقیت True و در غیر این صورت False برمی‌گرداند.
    خطاها فقط لاگ می‌شوند و باعث کرش برنامه نمی‌شوند.
    """
    username = getattr(settings, 'MELIPAYAMAK_USERNAME', '')
    password = getattr(settings, 'MELIPAYAMAK_PASSWORD', '')
    sender   = getattr(settings, 'MELIPAYAMAK_SENDER', '')

    if not (username and password and sender):
        logger.info('SMS skipped (Melipayamak credentials not configured).')
        return False

    if not to:
        logger.info('SMS skipped (no phone number).')
        return False

    # نرمال‌سازی شماره: ملی‌پیامک معمولاً 09xxxxxxxxx را می‌پذیرد
    to = to.strip().replace(' ', '')
    if to.startswith('+98'):
        to = '0' + to[3:]
    elif to.startswith('98'):
        to = '0' + to[2:]

    payload = {
        'username': username,
        'password': password,
        'to': to,
        'from': sender,
        'text': text,
        'isFlash': False,
    }

    try:
        req = Request(
            MELIPAYAMAK_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urlopen(req, timeout=15) as resp:
            body = resp.read().decode('utf-8', errors='ignore')
            logger.info(f'SMS sent to {to}: {body}')
            return True
    except (HTTPError, URLError) as e:
        logger.error(f'SMS error to {to}: {e}')
        return False
    except Exception as e:
        logger.error(f'SMS unexpected error to {to}: {e}')
        return False


def send_new_program_sms(trainee_profile, coach_user):
    """
    پیامک اطلاع‌رسانی برنامه تمرینی جدید برای شاگرد.
    """
    user = trainee_profile.user
    coach_name = coach_user.get_full_name() or coach_user.username

    lines = [
        f'مربی {coach_name} برنامه تمرینی جدیدی برای شما تنظیم کرد.',
        'برای مشاهده به پنل خود وارد شوید:',
        'fitcoachclub.ir',
        f'یوزرنیم: {user.username}',
    ]
    if trainee_profile.last_password_plain:
        lines.append(f'رمز عبور: {trainee_profile.last_password_plain}')

    text = '\n'.join(lines)
    return send_sms(user.phone, text)
