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
from urllib.parse import urlencode
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

    return _send_payload(MELIPAYAMAK_URL, payload)


def _send_payload(url, payload):
    try:
        req = Request(url, data=urlencode(payload).encode('utf-8'),
                      headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
        with urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        # HTTP 200 alone does not indicate acceptance by Melipayamak.
        from decimal import Decimal
        accepted = (isinstance(result, dict) and str(result.get('RetStatus')) == '1'
                    and Decimal(str(result.get('Value', '0'))) > 0)
        if not accepted:
            logger.warning('Melipayamak rejected an SMS request.')
        return accepted
    except Exception:
        # Do not log provider bodies, OTPs, passwords, or recipient numbers.
        logger.warning('Melipayamak SMS delivery request failed.')
        return False


def otp_sms_configured():
    return bool(settings.MELIPAYAMAK_USERNAME and settings.MELIPAYAMAK_PASSWORD
                and (getattr(settings, 'MELIPAYAMAK_OTP_BODY_ID', '')
                     or settings.MELIPAYAMAK_SENDER))


def send_otp_sms(phone, code):
    if not otp_sms_configured():
        return False
    body_id = getattr(settings, 'MELIPAYAMAK_OTP_BODY_ID', '')
    if body_id:
        try:
            body_id = int(body_id)
            if body_id <= 0:
                return False
        except (ValueError, TypeError):
            return False
        return _send_payload('https://rest.payamak-panel.com/api/SendSMS/BaseServiceNumber', {
            'username': settings.MELIPAYAMAK_USERNAME,
            'password': settings.MELIPAYAMAK_PASSWORD,
            'to': phone, 'text': code, 'bodyId': body_id,
        })
    minutes = max(1, settings.OTP_CODE_TTL_SECONDS // 60)
    return send_sms(phone, f'فیت‌کوچ\nکد ورود: {code}\nاعتبار: {minutes} دقیقه\nاین کد را در اختیار دیگران نگذارید.')


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
