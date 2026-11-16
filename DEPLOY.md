# راهنمای deploy روی سرور

## ⚠️ نکته‌ی مهم درباره‌ی هاست چابکان و فایل‌های media
چابکان ترافیک عمومی رو **مستقیم به پورت اپ** (متغیر محیطی `PORT`، مثلاً `3000`)
می‌فرسته و از `nginx.conf` داخل این پروژه اصلاً رد نمی‌شه — یعنی nginx.conf موجود
در ریشه‌ی پروژه روی چابکان **عملاً بلااستفاده‌ست** (فقط برای دیپلوی‌های دیگه‌ای که
خودت nginx رو جلوی gunicorn قرار می‌دی کاربرد داره).
به همین خاطر، سرو کردن فایل‌های `media/` (عکس/ویدیوی حرکات) مستقیماً توسط خود
Django تو `fitcoach/urls.py` انجام می‌شه (مستقل از `DEBUG`)، نه با تکیه به nginx.
اگه یه روز دیدی عکس/ویدیوها لود نمی‌شن، اول این‌ها رو چک کن:
```bash
echo $PORT                      # چه پورتی چابکان واقعاً بهش وصل می‌شه
ss -tlnp | grep gunicorn        # gunicorn دقیقاً رو همون پورت بالاست؟
curl -I http://localhost:$PORT/media/<یک-فایل-واقعی>   # مستقیم تست کن
```

## دانلود PDF
PDF با reportlab (یک کتابخونه‌ی خالص پایتونی) روی سرور ساخته می‌شه. هیچ کتابخونه‌ی
سیستمی (pango/cairo) و هیچ دانلود مرورگر (Chromium/Playwright) لازم نیست —
فقط `pip install -r requirements.txt` کافیه.

## متغیرهای محیطی (در /etc/environment یا .env)
```bash
export DJANGO_SECRET_KEY='یک-کلید-تصادفی-قوی-اینجا'
export DJANGO_DEBUG=False
export DJANGO_ALLOWED_HOSTS='your-domain.ir,www.your-domain.ir'
export DJANGO_CSRF_TRUSTED_ORIGINS='https://your-domain.ir,https://www.your-domain.ir'
export MELIPAYAMAK_USERNAME='...'
export MELIPAYAMAK_PASSWORD='...'
export MELIPAYAMAK_SENDER='...'
```

## دستورات اولیه
```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser   # اگر superuser نداری
```

## اجرا با gunicorn
```bash
gunicorn fitcoach.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

## تولید SECRET_KEY جدید
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## نکات مهم
- حتماً `DJANGO_SECRET_KEY` رو عوض کن
- پوشه `logs/` باید writable باشه
- فایل `db.sqlite3` رو backup بگیر
- برای SSL از Let's Encrypt استفاده کن
