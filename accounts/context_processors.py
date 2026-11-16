from django.conf import settings


def feature_flags(request):
    """
    فلگ‌های فیچر که تو همه‌ی تمپلیت‌ها بدون پاس‌دادن دستی در دسترس باشن.
    الان فقط رژیم غذایی رو داره که فعلاً مخفی نگه داشته شده.
    """
    return {
        'nutrition_enabled': settings.NUTRITION_ENABLED,
    }
