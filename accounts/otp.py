"""Database-backed, browser-bound SMS login challenges and atomic quotas."""
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from accounts.models import OTPChallenge, OTPRateLimit, User
from coach.sms import send_otp_sms


class RateLimited(Exception):
    pass


def reserve_send(phone, ip):
    now = timezone.now()
    cutoff = now - timedelta(seconds=settings.OTP_SEND_WINDOW_SECONDS)
    with transaction.atomic():
        for kind, value, limit, cooldown in [
            ('ip', ip, settings.OTP_SEND_LIMIT_IP, 0),
            ('phone', phone, settings.OTP_SEND_LIMIT_PHONE, settings.OTP_RESEND_SECONDS),
        ]:
            key = kind + ':' + salted_hmac('otp.rate', value, algorithm='sha256').hexdigest()
            row, _ = OTPRateLimit.objects.get_or_create(
                key=key, defaults={'window_start': now, 'next_allowed_at': now})
            OTPRateLimit.objects.filter(pk=key, window_start__lte=cutoff).update(
                count=0, window_start=now)
            changed = OTPRateLimit.objects.filter(
                pk=key, count__lt=limit, next_allowed_at__lte=now).update(
                count=F('count') + 1, next_allowed_at=now + timedelta(seconds=cooldown))
            if not changed:
                raise RateLimited


def code_digest(challenge_id, code):
    return salted_hmac('fitcoach.otp.code', f'{challenge_id}:{code}', algorithm='sha256').hexdigest()


def issue_challenge(phone):
    # A shared number must never select an arbitrary account, even if one is inactive.
    users = list(User.objects.filter(phone_normalized=phone)[:2])
    if len(users) != 1 or not users[0].is_active:
        return None
    now = timezone.now()
    challenge = OTPChallenge(user=users[0], phone=phone,
                             expires_at=now + timedelta(seconds=settings.OTP_CODE_TTL_SECONDS))
    code = f'{secrets.randbelow(1_000_000):06d}'
    challenge.code_hash = code_digest(challenge.pk, code)
    with transaction.atomic():
        OTPChallenge.objects.filter(phone=phone, consumed_at__isnull=True).update(consumed_at=now)
        challenge.save()
    delivered = send_otp_sms(phone, code)
    OTPChallenge.objects.filter(pk=challenge.pk).update(delivered=delivered)
    # A failed/uncertain provider response must never create a usable challenge.
    if not delivered:
        OTPChallenge.objects.filter(pk=challenge.pk).update(consumed_at=timezone.now())
        return None
    return str(challenge.pk)


def verify_challenge(challenge_id, code):
    if not challenge_id:
        return None
    try:
        challenge_id = uuid.UUID(str(challenge_id))
    except (ValueError, TypeError, AttributeError):
        return None
    now = timezone.now()
    eligible = OTPChallenge.objects.filter(
        pk=challenge_id, delivered=True, consumed_at__isnull=True,
        expires_at__gt=now, attempts__lt=settings.OTP_MAX_ATTEMPTS)
    if not eligible.update(attempts=F('attempts') + 1):
        return None
    challenge = OTPChallenge.objects.select_related('user').get(pk=challenge_id)
    if not constant_time_compare(challenge.code_hash, code_digest(challenge.pk, code)):
        return None
    # Check the current account binding again after the SMS was sent.
    if (not challenge.user.is_active or challenge.user.phone_normalized != challenge.phone
            or User.objects.filter(phone_normalized=challenge.phone).count() != 1):
        return None
    # Conditional consumption also prevents two concurrent correct submissions succeeding.
    consumed = OTPChallenge.objects.filter(
        pk=challenge.pk, consumed_at__isnull=True, delivered=True,
        expires_at__gt=timezone.now()).update(consumed_at=timezone.now())
    return challenge.user if consumed else None
