"""
اسکریپت چک و دانلود خودکار فایل‌های استاتیک FitCoach
اجرا: python check_assets.py
"""
import os
import urllib.request

BASE   = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, 'static')

GREEN  = '\033[92m✔'
RED    = '\033[91m✘'
YELLOW = '\033[93m!'
RESET  = '\033[0m'

FA_BASE = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/webfonts/'

def check(root, path, min_size=1000):
    full = os.path.join(root, path)
    if not os.path.exists(full):
        return RED, f'وجود ندارد{RESET}', False
    size = os.path.getsize(full)
    if size < min_size:
        return YELLOW, f'فایل ناقص است ({size} bytes){RESET}', False
    return GREEN, f'OK  ({size:,} bytes){RESET}', True

checks = [
    (STATIC, 'fonts/Vazirmatn-Regular.ttf',   50_000, None),
    (STATIC, 'fonts/Vazirmatn-Regular.woff2', 50_000, None),
    (STATIC, 'fonts/Vazirmatn-Bold.ttf',      50_000, None),
    (STATIC, 'fonts/Vazirmatn-Bold.woff2',    50_000, None),
    (STATIC, 'icons/fontawesome/css/all.min.css', 50_000, None),
    (STATIC, 'icons/fontawesome/webfonts/fa-solid-900.woff2',      100_000, FA_BASE + 'fa-solid-900.woff2'),
    (STATIC, 'icons/fontawesome/webfonts/fa-regular-400.woff2',     10_000, FA_BASE + 'fa-regular-400.woff2'),
    (STATIC, 'icons/fontawesome/webfonts/fa-brands-400.woff2',      50_000, FA_BASE + 'fa-brands-400.woff2'),
    (STATIC, 'icons/fontawesome/webfonts/fa-v4compatibility.woff2',  1_000, FA_BASE + 'fa-v4compatibility.woff2'),
    (STATIC, 'icons/fontawesome/webfonts/fa-solid-900.ttf',        100_000, FA_BASE + 'fa-solid-900.ttf'),
    (STATIC, 'icons/fontawesome/webfonts/fa-regular-400.ttf',       10_000, FA_BASE + 'fa-regular-400.ttf'),
    (STATIC, 'icons/fontawesome/webfonts/fa-brands-400.ttf',        50_000, FA_BASE + 'fa-brands-400.ttf'),
    (STATIC, 'icons/fontawesome/webfonts/fa-v4compatibility.ttf',    1_000, FA_BASE + 'fa-v4compatibility.ttf'),
    (STATIC, 'js/chart.min.js',  100_000, None),
    (STATIC, 'js/main.js',         1_000, None),
    (STATIC, 'css/main.css',       5_000, None),
    (STATIC, 'img/icon-192.png',   1_000, None),
    (STATIC, 'img/icon-512.png',   1_000, None),
    (STATIC, 'manifest.json',        100, None),
    (STATIC, 'sw.js',               100, None),
]

print('\n' + '═'*58)
print('   چک فایل‌های استاتیک FitCoach')
print('═'*58)

missing = []
ok = warn = fail = 0
for root, path, min_sz, url in checks:
    icon, msg, passed = check(root, path, min_sz)
    label = path.split('/')[-1]
    print(f'  {icon}  {label:<42} {msg}')
    if passed:       ok   += 1
    elif icon == YELLOW: warn += 1
    else:
        fail += 1
        if url:
            missing.append((root, path, url))

print('═'*58)
print(f'  نتیجه:  {ok} OK  |  {warn} ناقص  |  {fail} مفقود')

if missing:
    print(f'\n  دانلود خودکار {len(missing)} فایل مفقود...\n')
    downloaded = 0
    for root, path, url in missing:
        full = os.path.join(root, path)
        label = path.split('/')[-1]
        try:
            print(f'  ⬇  {label} ...', end=' ', flush=True)
            urllib.request.urlretrieve(url, full)
            size = os.path.getsize(full)
            print(f'\033[92mدانلود شد ({size:,} bytes)\033[0m')
            downloaded += 1
        except Exception as e:
            print(f'\033[91mخطا: {e}\033[0m')
    print(f'\n  {downloaded}/{len(missing)} فایل دانلود شد')

if fail == 0 and warn == 0:
    print('  ✔ همه فایل‌ها موجود و سالم هستند')
print('═'*58 + '\n')
