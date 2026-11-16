from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.views.static import serve as static_serve
from django.shortcuts import redirect, render
from django.http import JsonResponse, HttpResponse
from pathlib import Path
from accounts import views as accounts_views

def home_redirect(request):
    if not request.user.is_authenticated:
        return render(request, 'landing.html')
    role = getattr(request.user, 'role', None)
    if role == 'admin':
        return redirect('admin_panel:dashboard')
    elif role == 'coach':
        return redirect('coach:dashboard')
    elif role == 'trainee':
        return redirect('trainee:dashboard')
    return redirect('accounts:login')


def service_worker(request):
    """
    فایل sw.js رو از مسیر ریشه‌ی سایت (/sw.js) سرو می‌کنه، نه از زیر
    /static/. علتش مهمه: محدوده‌ی کنترل (scope) پیش‌فرض یک Service Worker
    فقط پوشه‌ای‌ست که خودِ فایلش توش سرو می‌شه. اگه sw.js زیر /static/
    باشه، فقط می‌تونه فایل‌های استاتیک (css/js/فونت) رو موقع آفلاین بودن
    کنترل کنه و هیچ‌وقت صفحات واقعی برنامه (داشبورد، ورود، لیست شاگردان
    و...) رو نمی‌بینه — دقیقاً همون دلیلی که برنامه کاملاً آفلاین باز
    نمی‌شد. با سرو کردن از ریشه، محدوده‌ی پیش‌فرض کل سایت (/) می‌شه.
    """
    sw_path = Path(settings.BASE_DIR) / 'static' / 'sw.js'
    content = sw_path.read_text(encoding='utf-8')
    return HttpResponse(content, content_type='application/javascript')


def asset_links(request):
    """
    فایل تایید مالکیت سایت برای اپ اندرویدی TWA (کافه‌بازار/اندروید موقع نصب
    این آدرس رو چک می‌کنن تا مطمئن بشن اپ و سایت مال یک نفره و نوار آدرس
    مرورگر تو اپ نصب‌شده نشون داده نشه).

    بعد از ساختن پکیج اندروید در PWABuilder (یا هر ابزار TWA دیگه)،
    مقدار PACKAGE_NAME و SHA256_FINGERPRINT رو با مقادیر واقعی که خود
    ابزار بهت می‌ده جایگزین کن. تا قبل از اون، این فایل بی‌ضرره و هیچ
    تاثیری روی خود سایت نداره.
    """
    PACKAGE_NAME = "ir.fitcoach.app"
    SHA256_FINGERPRINT = "REPLACE_WITH_REAL_FINGERPRINT_FROM_PWABUILDER"

    data = [{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": PACKAGE_NAME,
            "sha256_cert_fingerprints": [SHA256_FINGERPRINT],
        },
    }]
    return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 2})


urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', home_redirect, name='home'),
    path('sw.js', service_worker, name='service_worker'),
    path('.well-known/assetlinks.json', asset_links, name='asset_links'),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('coach/', include('coach.urls', namespace='coach')),
    path('trainee/', include('trainee.urls', namespace='trainee')),
    path('admin-panel/', include('admin_panel.urls', namespace='admin_panel')),
    # لینک عمومیِ کوتاه ثبت‌نام شاگرد (مخصوص هر مربی) — مثلاً برای بیوی اینستاگرام
    path('r/<str:code>/', accounts_views.coach_signup, name='coach_signup'),
    # سرو مستقیم media توسط خود Django، مستقل از DEBUG.
    # علتش: روی هاست چابکان، ترافیک عمومی مستقیم به gunicorn می‌رسه و از
    # nginx داخل کانتینر (که قرار بود مسئول /media/ باشه) رد نمی‌شه. کمک‌تابع
    # پیش‌فرض django.conf.urls.static.static() فقط وقتی DEBUG=True هست کار
    # می‌کنه، برای همین اینجا صریح و همیشگی serve می‌کنیم.
    re_path(r'^media/(?P<path>.*)$', static_serve, {'document_root': settings.MEDIA_ROOT}),
]
