#!/usr/bin/env python3
"""
FitCoach - دانلود فایل‌های استاتیک
اجرا در پوشه اصلی پروژه (کنار manage.py):
    python download_assets.py
"""
import os, sys, time, http.client
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

BASE   = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, 'static')

def makedirs(path):
    os.makedirs(path, exist_ok=True)

def download(url, dest, retries=5, chunk=32768):
    makedirs(os.path.dirname(dest))
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Encoding': 'identity',   # غیرفعال کردن chunked encoding
        'Connection': 'close',
    }
    for attempt in range(1, retries + 1):
        try:
            req  = Request(url, headers=headers)
            resp = urlopen(req, timeout=90)
            total = int(resp.headers.get('Content-Length', 0))
            got   = 0
            data  = []
            while True:
                try:
                    buf = resp.read(chunk)
                except http.client.IncompleteRead as e:
                    buf = e.partial   # هر چی دریافت شده رو نگه می‌داره
                if not buf:
                    break
                data.append(buf)
                got += len(buf)
            content = b''.join(data)
            if total and len(content) < total * 0.95:
                raise IOError(f'ناقص: {len(content)}/{total} bytes')
            with open(dest, 'wb') as f:
                f.write(content)
            size = os.path.getsize(dest)
            print(f'  ✓ {os.path.basename(dest)}  ({size//1024} KB)')
            return True
        except (HTTPError, URLError, IOError, OSError,
                http.client.IncompleteRead, http.client.HTTPException) as e:
            print(f'  ! تلاش {attempt}/{retries}: {e}')
            if os.path.exists(dest):
                os.remove(dest)
            if attempt < retries:
                time.sleep(3 * attempt)
    print(f'  ✗ دانلود ناموفق: {url}')
    return False


# ── 1. Chart.js ───────────────────────────────────────────────────────────────
print('\n[1/3] Chart.js 4 ...')
makedirs(os.path.join(STATIC, 'js'))
chart_dest = os.path.join(STATIC, 'js', 'chart.min.js')
if os.path.exists(chart_dest) and os.path.getsize(chart_dest) > 10000:
    print(f'  ✓ chart.min.js  (موجود - {os.path.getsize(chart_dest)//1024} KB)')
else:
    for url in [
        'https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js',
        'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js',
        'https://unpkg.com/chart.js@4.4.4/dist/chart.umd.min.js',
    ]:
        print(f'  → {url}')
        if download(url, chart_dest):
            break


# ── 2. Font Awesome 6 Free ────────────────────────────────────────────────────
print('\n[2/3] Font Awesome 6 Free ...')
fa_dir  = os.path.join(STATIC, 'icons', 'fontawesome')
css_dir = os.path.join(fa_dir, 'css')
wf_dir  = os.path.join(fa_dir, 'webfonts')
makedirs(css_dir); makedirs(wf_dir)

css_dest = os.path.join(css_dir, 'all.min.css')
if os.path.exists(css_dest) and os.path.getsize(css_dest) > 10000:
    print(f'  ✓ all.min.css  (موجود)')
else:
    for url in [
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css',
        'https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/css/all.min.css',
    ]:
        print(f'  → CSS: {url}')
        if download(url, css_dest):
            content = open(css_dest, encoding='utf-8', errors='ignore').read()
            content = content.replace('../webfonts/', '/static/icons/fontawesome/webfonts/')
            content = content.replace('./webfonts/',  '/static/icons/fontawesome/webfonts/')
            open(css_dest, 'w', encoding='utf-8').write(content)
            print('  ✓ مسیر CSS اصلاح شد')
            break

fa_ver = '6.5.2'
wf_files = [
    'fa-brands-400.woff2',
    'fa-regular-400.woff2',
    'fa-solid-900.woff2',
    'fa-v4compatibility.woff2',
]
for fname in wf_files:
    dest = os.path.join(wf_dir, fname)
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        print(f'  ✓ {fname}  (موجود)')
        continue
    for base in [
        f'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/{fa_ver}/webfonts',
        f'https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@{fa_ver}/webfonts',
    ]:
        if download(f'{base}/{fname}', dest):
            break


# ── 3. Vazirmatn Font ─────────────────────────────────────────────────────────
print('\n[3/3] فونت وزیرمتن ...')
makedirs(os.path.join(STATIC, 'fonts'))

ver = 'v33.003'
vazir_files = {
    'Vazirmatn-Regular.woff2': [
        f'https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@{ver}/fonts/webfonts/Vazirmatn-Regular.woff2',
        f'https://github.com/rastikerdar/vazirmatn/raw/{ver}/fonts/webfonts/Vazirmatn-Regular.woff2',
    ],
    'Vazirmatn-Bold.woff2': [
        f'https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@{ver}/fonts/webfonts/Vazirmatn-Bold.woff2',
        f'https://github.com/rastikerdar/vazirmatn/raw/{ver}/fonts/webfonts/Vazirmatn-Bold.woff2',
    ],
    'Vazirmatn-Regular.ttf': [
        f'https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@{ver}/fonts/ttf/Vazirmatn-Regular.ttf',
        f'https://github.com/rastikerdar/vazirmatn/raw/{ver}/fonts/ttf/Vazirmatn-Regular.ttf',
    ],
    'Vazirmatn-Bold.ttf': [
        # منابع مختلف برای Bold TTF
        f'https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@{ver}/fonts/ttf/Vazirmatn-Bold.ttf',
        f'https://github.com/rastikerdar/vazirmatn/raw/{ver}/fonts/ttf/Vazirmatn-Bold.ttf',
        f'https://raw.githubusercontent.com/rastikerdar/vazirmatn/{ver}/fonts/ttf/Vazirmatn-Bold.ttf',
        # نسخه قدیمی‌تر به عنوان fallback
        'https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.002/fonts/ttf/Vazirmatn-Bold.ttf',
    ],
}

for fname, urls in vazir_files.items():
    dest = os.path.join(STATIC, 'fonts', fname)
    if os.path.exists(dest) and os.path.getsize(dest) > 10000:
        print(f'  ✓ {fname}  (موجود - {os.path.getsize(dest)//1024} KB)')
        continue
    for url in urls:
        if download(url, dest):
            break
    # اگر TTF دانلود نشد، از woff2 که داریم کافیه - اخطار بده نه خطا
    if not os.path.exists(dest) or os.path.getsize(dest) < 1000:
        woff2 = dest.replace('.ttf', '.woff2')
        if os.path.exists(woff2):
            print(f'  ℹ  {fname}: نیازی نیست — woff2 موجود است (برای PDF فقط TTF لازم است)')


# ── نتیجه ─────────────────────────────────────────────────────────────────────
print('\n' + '='*55)
print('بررسی نهایی:')
checks = [
    (os.path.join(STATIC, 'js', 'chart.min.js'),                                  'Chart.js',       10000),
    (os.path.join(STATIC, 'icons','fontawesome','css','all.min.css'),              'FA CSS',         10000),
    (os.path.join(STATIC, 'icons','fontawesome','webfonts','fa-solid-900.woff2'),  'FA Solid font',  10000),
    (os.path.join(STATIC, 'fonts','Vazirmatn-Regular.woff2'),                     'Vazir Regular',  10000),
    (os.path.join(STATIC, 'fonts','Vazirmatn-Bold.woff2'),                        'Vazir Bold',     10000),
    (os.path.join(STATIC, 'fonts','Vazirmatn-Regular.ttf'),                       'Vazir TTF (PDF)',  1000),
]
all_ok = True
for path, label, min_size in checks:
    ok     = os.path.exists(path) and os.path.getsize(path) >= min_size
    status = '✅' if ok else '❌'
    size   = f'{os.path.getsize(path)//1024} KB' if os.path.exists(path) else 'موجود نیست'
    print(f'  {status}  {label}: {size}')
    if not ok:
        all_ok = False

print('='*55)
if all_ok:
    print('🎉 همه فایل‌ها آماده‌اند! سرور رو اجرا کنید:')
    print('   python manage.py runserver')
else:
    print('⚠️  بعضی فایل‌ها کامل نشدند — دوباره اجرا کنید:')
    print('   python download_assets.py')