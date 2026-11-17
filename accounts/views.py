from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from datetime import timedelta
import re

from .models import User, TraineeProfile, BodyMetricHistory, LoginAttempt

# نام کاربری: فقط حروف انگلیسی/عدد و چند کاراکتر متداول (بدون فارسی، بدون فاصله)
USERNAME_RE = re.compile(r'^[A-Za-z0-9_.@+-]+$')
# رمز عبور: هر چیزی مجازه (انگلیسی/عدد/نماد) به‌جز حروف فارسی/عربی
PERSIAN_CHAR_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]')

LOGIN_MAX_ATTEMPTS   = 5
LOGIN_WINDOW_MINUTES = 15


def _client_ip(request):
    # پشت nginx: هدر X-Forwarded-For اولویت داره، وگرنه REMOTE_ADDR
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


@require_http_methods(["GET", "POST"])
def login_view(request):
    if (settings.OTP_LOGIN_ENABLED and request.method == 'GET'
            and request.GET.get('method') != 'password'):
        from .otp_views import request_code
        return request_code(request)
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        ip = _client_ip(request)
        window_start = timezone.now() - timedelta(minutes=LOGIN_WINDOW_MINUTES)
        recent_fails = LoginAttempt.objects.filter(ip_address=ip, created_at__gte=window_start).count()
        if recent_fails >= LOGIN_MAX_ATTEMPTS:
            messages.error(
                request,
                f'به‌خاطر تلاش‌های ناموفق زیاد، ورود از این آدرس موقتاً بسته شده. '
                f'{LOGIN_WINDOW_MINUTES} دقیقه‌ی دیگر دوباره امتحان کن.'
            )
            return render(request, 'accounts/login.html', {'login_mode': 'password', 'otp_enabled': settings.OTP_LOGIN_ENABLED, 'next_url': request.POST.get('next') or request.GET.get('next', '/')})

        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                destination = request.POST.get('next') or request.GET.get('next', '/')
                if not url_has_allowed_host_and_scheme(destination, {request.get_host()}, require_https=request.is_secure()):
                    destination = '/'
                return redirect(destination)
            else:
                messages.error(request, 'حساب کاربری شما غیرفعال است.')
        else:
            LoginAttempt.objects.create(ip_address=ip, username_tried=username[:150])
            messages.error(request, 'نام کاربری یا رمز عبور اشتباه است.')
    return render(request, 'accounts/login.html', {'login_mode': 'password', 'otp_enabled': settings.OTP_LOGIN_ENABLED, 'next_url': request.POST.get('next') or request.GET.get('next', '/')})


@login_required
def logout_view(request):
    logout(request)
    return redirect('accounts:login')


@login_required
def change_password_view(request):
    if request.method == 'POST':
        current = request.POST.get('current_password', '')
        new_p   = request.POST.get('new_password', '')
        confirm = request.POST.get('confirm_password', '')
        if not request.user.check_password(current):
            messages.error(request, 'رمز عبور فعلی اشتباه است.')
        elif new_p != confirm:
            messages.error(request, 'رمز عبور جدید و تکرار آن مطابقت ندارند.')
        elif len(new_p) < 6:
            messages.error(request, 'رمز عبور باید حداقل ۶ کاراکتر باشد.')
        else:
            request.user.set_password(new_p)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, 'رمز عبور با موفقیت تغییر یافت.')
            return redirect('home')
    return render(request, 'accounts/change_password.html')


@require_http_methods(["GET", "POST"])
def coach_signup(request, code):
    """
    صفحه‌ی عمومی ثبت‌نام شاگرد از طریق لینک اختصاصی یک مربی (مثلاً از بیوی
    اینستاگرام). نیازی به لاگین ندارد. با ثبت فرم: حساب شاگرد ساخته می‌شود،
    به همان مربی وصل می‌شود، یک درخواست برنامه‌ی خودکار برایش ثبت می‌شود، و
    خود شاگرد بلافاصله لاگین می‌شود.
    """
    coach = get_object_or_404(User, referral_code=code, role='coach', is_active=True)

    if request.user.is_authenticated:
        # اگر یه کاربر لاگین‌شده (مثلاً خود مربی یا یه شاگرد دیگه) وارد این
        # لینک بشه، اذیتش نمی‌کنیم؛ می‌فرستیمش به داشبورد خودش.
        return redirect('home')

    form_data = {}
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        phone      = request.POST.get('phone', '').strip()
        username   = request.POST.get('username', '').strip()
        password   = request.POST.get('password', '')
        weight     = request.POST.get('weight', '').strip()
        height     = request.POST.get('height', '').strip()
        age        = request.POST.get('age', '').strip()
        form_data  = request.POST

        errors = []
        if not first_name:
            errors.append('وارد کردن نام الزامی است.')
        if not last_name:
            errors.append('وارد کردن نام‌خانوادگی الزامی است.')
        if not phone:
            errors.append('وارد کردن شماره تلفن الزامی است.')
        if not username:
            errors.append('وارد کردن نام کاربری الزامی است.')
        elif not USERNAME_RE.match(username):
            errors.append('نام کاربری فقط باید شامل حروف انگلیسی، عدد، و کاراکترهای . _ @ + - باشد (بدون فارسی و بدون فاصله).')
        elif User.objects.filter(username=username).exists():
            errors.append('این نام کاربری قبلاً استفاده شده؛ یک نام کاربری دیگر انتخاب کنید.')
        if not password or len(password) < 6:
            errors.append('رمز عبور باید حداقل ۶ کاراکتر باشد.')
        elif PERSIAN_CHAR_RE.search(password):
            errors.append('رمز عبور نباید شامل حروف فارسی باشد؛ فقط انگلیسی/عدد/نماد استفاده کنید.')
        for label, val in [('وزن', weight), ('قد', height), ('سن', age)]:
            if val:
                try:
                    float(val)
                except ValueError:
                    errors.append(f'مقدار «{label}» باید عدد باشد.')

        if not errors:
            try:
                from coach.models import Notification
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=username, password=password,
                        first_name=first_name, last_name=last_name,
                        role='trainee', phone=phone,
                    )
                    profile = TraineeProfile.objects.create(
                        user=user, coach=coach,
                        weight=float(weight) if weight else None,
                        height=float(height) if height else None,
                        age=int(float(age)) if age else None,
                        last_password_plain=password,
                    )
                    if weight or height:
                        BodyMetricHistory.objects.create(
                            trainee=profile,
                            weight=profile.weight, height=profile.height,
                            age=profile.age, bmi=profile.bmi,
                        )
                    Notification.objects.create(
                        recipient=coach,
                        sender=user,
                        notif_type='new_trainee',
                        title='شاگرد جدید ثبت‌نام کرد',
                        message=f'{user.get_full_name() or user.username} از طریق لینک اختصاصی شما '
                                f'ثبت‌نام کرد.',
                    )
                # کاربر تازه‌ثبت‌نام‌شده رو خودکار لاگین می‌کنیم تا حس کنه
                # ثبت‌نامش کامل شده و مستقیم بره تو داشبورد خودش.
                login(request, user)
                messages.success(
                    request,
                    'ثبت‌نام شما با موفقیت انجام شد و درخواست برنامه برای مربی‌تان ارسال شد. '
                    'به‌محض آماده شدن برنامه، از همینجا می‌بینیدش.'
                )
                return redirect('trainee:dashboard')
            except Exception as e:
                errors.append(f'خطای غیرمنتظره در ثبت‌نام: {e}')

        for err in errors:
            messages.error(request, err)

    return render(request, 'accounts/coach_signup.html', {
        'coach': coach,
        'form_data': form_data,
    })
