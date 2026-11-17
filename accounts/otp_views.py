import ipaddress
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from accounts import otp
from accounts.phone import DIGIT_TRANSLATION, normalize_mobile
from coach.sms import otp_sms_configured


def _safe_next(request, value):
    return value if url_has_allowed_host_and_scheme(
        value, {request.get_host()}, require_https=request.is_secure()) else '/'


def _client_ip(request):
    value = request.META.get('REMOTE_ADDR', '')
    if settings.OTP_TRUST_X_FORWARDED_FOR:
        value = request.META.get('HTTP_X_FORWARDED_FOR', value).split(',')[0].strip()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return '0.0.0.0'


def _request_page(request, phone='', status=200):
    return render(request, 'accounts/login.html', {
        'login_mode': 'otp', 'otp_enabled': True, 'otp_available': otp_sms_configured(),
        'phone_value': phone,
        'next_url': _safe_next(request, request.POST.get('next') or request.GET.get('next', '/')),
    }, status=status)


@require_http_methods(['GET', 'POST'])
def request_code(request):
    if request.user.is_authenticated:
        return redirect('home')
    if not settings.OTP_LOGIN_ENABLED:
        return redirect('/accounts/login/?method=password')
    if request.method == 'GET':
        return _request_page(request)
    if not otp_sms_configured():
        messages.error(request, 'ورود پیامکی هنوز تنظیم نشده است؛ فعلاً با رمز عبور وارد شوید.')
        return _request_page(request, status=503)
    try:
        phone = normalize_mobile(request.POST.get('phone'))
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return _request_page(request, request.POST.get('phone', '')[:32], status=400)
    try:
        otp.reserve_send(phone, _client_ip(request))
    except otp.RateLimited:
        messages.error(request, 'برای ارسال دوباره کمی صبر کنید؛ تعداد درخواست‌ها محدود است.')
        if request.session.get('otp_phone') == phone:
            return redirect('accounts:otp_verify')
        return _request_page(request, phone, status=429)
    challenge_id = otp.issue_challenge(phone)
    request.session['otp_challenge_id'] = challenge_id
    request.session['otp_phone'] = phone
    request.session['otp_next'] = _safe_next(request, request.POST.get('next', '/'))
    request.session['otp_requested_at'] = timezone.now().timestamp()
    # Uniform response for unknown, inactive, shared numbers and delivery failure.
    return redirect('accounts:otp_verify')


@require_http_methods(['GET', 'POST'])
def verify_code(request):
    if request.user.is_authenticated:
        return redirect('home')
    if not settings.OTP_LOGIN_ENABLED:
        return redirect('accounts:login')
    phone = request.session.get('otp_phone')
    if not phone:
        return redirect('accounts:login')
    if request.method == 'POST':
        raw_code = request.POST.get('code', '')[:64].translate(DIGIT_TRANSLATION).strip()
        code = raw_code if re.fullmatch(r'[0-9]{6}', raw_code) else 'invalid'
        user = otp.verify_challenge(request.session.get('otp_challenge_id'), code)
        if user is not None:
            destination = _safe_next(request, request.session.get('otp_next', '/'))
            for key in ['otp_challenge_id', 'otp_phone', 'otp_next', 'otp_requested_at']:
                request.session.pop(key, None)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect(destination)
        messages.error(request, 'کد نامعتبر یا منقضی شده است؛ دوباره بررسی کنید یا کد جدید بگیرید.')
    requested_at = request.session.get('otp_requested_at', 0)
    return render(request, 'accounts/otp_verify.html', {
        'otp_enabled': True, 'phone': phone,
        'next_url': request.session.get('otp_next', '/'),
        'resend_at': int(requested_at + settings.OTP_RESEND_SECONDS),
        'expiry_minutes': settings.OTP_CODE_TTL_SECONDS // 60,
    })
