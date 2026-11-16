# 🏋️ FitCoach — سامانه مدیریت تمرین ورزشی

پلتفرم وب فارسی (RTL) برای مربیان و شاگردان باشگاه: ساخت برنامه تمرینی، پیگیری وزن/BMI، بانک حرکات، دانلود PDF برنامه و پنل مدیریت.
ساخته‌شده با **Django**، سه پنل جدا: **Admin | Coach | Trainee**.

## ✨ ویژگی‌ها

**پنل مربی**
- مدیریت شاگردان، محاسبه‌ی خودکار BMI
- بانک حرکات اختصاصی + عمومی (عکس/ویدیو)
- ساخت برنامه تمرینی (سوپرست، تری‌ست، دراپ‌ست) و آرشیو خودکار برنامه‌های قبلی
- اعلان‌ها و درخواست برنامه

**پنل شاگرد**
- مشاهده‌ی برنامه فعال، درخواست برنامه جدید، نمودار روند وزن/BMI
- دانلود PDF برنامه (با reportlab)

**پنل ادمین**
- مدیریت مربیان و شاگردان، حرکات عمومی، لاگ فعالیت

**فنی**
- تم دارک/لایت، PWA (Add to Home Screen)، Service Worker و صفحه‌ی آفلاین
- فونت وزیرمتن، Font Awesome و Chart.js به‌صورت لوکال (بدون CDN)
- ارسال پیامک با ملی‌پیامک (اختیاری)

## 🚀 اجرای لوکال

نیازمندی: Python 3.10+

```bash
git clone <repo-url>
cd fitcoach

python -m venv venv
source venv/bin/activate        # ویندوز: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # و مقادیر رو پر کن
# برای توسعه‌ی لوکال در .env بذار: DJANGO_DEBUG=True

python manage.py migrate
python manage.py setup_fitcoach   # ساخت کاربران نمونه (رمزها یک‌بار چاپ می‌شن)
python manage.py runserver
```

بعد برو به http://127.0.0.1:8000

> اگه `DJANGO_DEBUG=False` باشه، `DJANGO_SECRET_KEY` حتماً باید تنظیم شده باشه، وگرنه پروژه بالا نمیاد.

## ⚙️ متغیرهای محیطی

همه در `.env.example` توضیح داده شدن: `DJANGO_SECRET_KEY`، `DJANGO_DEBUG`، `DJANGO_ALLOWED_HOSTS`، `DJANGO_CSRF_TRUSTED_ORIGINS`، تنظیمات ملی‌پیامک و `NUTRITION_ENABLED`.

تولید SECRET_KEY:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 🧪 تست

```bash
python manage.py collectstatic --noinput
python manage.py test
```

## 📦 دیپلوی

راهنمای deploy در [DEPLOY.md](DEPLOY.md).

## 📁 ساختار

```
fitcoach/       تنظیمات Django
accounts/       کاربران، پروفایل شاگرد، لاگ فعالیت
coach/          پنل مربی، مدل‌های تمرین و برنامه
trainee/        پنل شاگرد و ساخت PDF
admin_panel/    پنل ادمین
templates/      قالب‌ها
static/         CSS/JS/فونت/آیکون
media/          فایل‌های آپلودی (در گیت نیست)
```

## ⚠️ نکات امنیتی

- فایل `.env` و دیتابیس `db.sqlite3` هرگز commit نشن (در `.gitignore` هستن).
- قبل از انتشار، رمزها و SECRET_KEY واقعی رو فقط از طریق متغیر محیطی بده.
