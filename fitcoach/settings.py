from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# بارگذاری .env (اختیاری) - اگه python-dotenv نصب باشه
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except ImportError:
    pass


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def _env_list(name, default=''):
    return [x.strip() for x in os.environ.get(name, default).split(',') if x.strip()]

# ─── DEBUG ────────────────────────────────────────────────────
# در سرور: DJANGO_DEBUG=False (پیش‌فرض)
DEBUG = _env_bool('DJANGO_DEBUG', False)

# ─── SECRET KEY ───────────────────────────────────────────────
# در production حتماً از متغیر محیطی بخوان. فقط در حالت DEBUG یه کلید موقت
# برای توسعه‌ی لوکال استفاده می‌شه.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-dev-only-key'
    else:
        raise ImproperlyConfigured(
            'DJANGO_SECRET_KEY تنظیم نشده. فایل .env.example رو ببین.'
        )

# ─── HOSTS ───────────────────────────────────────────────────
ALLOWED_HOSTS = _env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')

CSRF_TRUSTED_ORIGINS = _env_list('DJANGO_CSRF_TRUSTED_ORIGINS', '')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'coach',
    'trainee',
    'admin_panel',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'fitcoach.middleware.OnlineOnlyPagesMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',        # سرو static بدون nginx
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'fitcoach.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.feature_flags',
            ],
        },
    },
]

WSGI_APPLICATION = 'fitcoach.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True

# ─── STATIC ──────────────────────────────────────────────────
STATIC_URL  = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# whitenoise: فشرده‌سازی و cache خودکار
# (STATICFILES_STORAGE از Django 5.1 حذف شده؛ از STORAGES استفاده می‌کنیم)
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# ─── MEDIA ───────────────────────────────────────────────────
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── SESSION ─────────────────────────────────────────────────
SESSION_COOKIE_AGE          = 60 * 60 * 24 * 30   # 30 روز
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_SECURE       = not DEBUG   # فقط HTTPS (در production)
CSRF_COOKIE_SECURE          = not DEBUG

LOGIN_URL          = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'

# ─── SECURITY HEADERS (production) ───────────────────────────
SECURE_BROWSER_XSS_FILTER        = True
SECURE_CONTENT_TYPE_NOSNIFF      = True
X_FRAME_OPTIONS                  = 'DENY'
SECURE_HSTS_SECONDS              = 31536000 if not DEBUG else 0   # 1 سال (فقط production)
SECURE_HSTS_INCLUDE_SUBDOMAINS   = not DEBUG
SECURE_HSTS_PRELOAD              = not DEBUG
SECURE_SSL_REDIRECT              = False      # پشت nginx ست می‌شه (پایین‌تر توضیح داده شده)

# ─── UPLOAD ──────────────────────────────────────────────────
FILE_UPLOAD_MAX_MEMORY_SIZE = 200 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 200 * 1024 * 1024

# ─── LOGGING (خطاها رو ذخیره کن) ─────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django_errors.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}

# ─── ملی‌پیامک ────────────────────────────────────────────────
MELIPAYAMAK_USERNAME = os.environ.get('MELIPAYAMAK_USERNAME', '')
MELIPAYAMAK_PASSWORD = os.environ.get('MELIPAYAMAK_PASSWORD', '')
MELIPAYAMAK_SENDER   = os.environ.get('MELIPAYAMAK_SENDER',   '')

# ─── FEATURE FLAGS ────────────────────────────────────────────
# فعلاً موقتاً مخفی است — کل قابلیت رژیم غذایی (منو، دکمه‌ها، صفحات) از دید
# مربی/شاگرد/ادمین پنهان می‌شود بدون این‌که چیزی حذف شود. برای فعال‌سازی
# دوباره، فقط این مقدار را True کنید.
NUTRITION_ENABLED = _env_bool('NUTRITION_ENABLED', False)

# پشت nginx بدون SSL — redirect غیرفعال
SECURE_PROXY_SSL_HEADER = None

# ── PERFORMANCE ──────────────────────────────────────────────
# Cache برای static files
WHITENOISE_MAX_AGE = 31536000  # 1 سال
WHITENOISE_ALLOW_ALL_ORIGINS = True

# Database connection pooling
CONN_MAX_AGE = 60  # ثانیه
