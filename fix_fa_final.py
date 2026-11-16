#!/usr/bin/env python3
"""اجرا در پوشه پروژه: python fix_fa_final.py"""
import os, time, http.client
from urllib.request import urlopen, Request

STATIC = 'static'
WF_DIR = os.path.join(STATIC, 'icons', 'fontawesome', 'webfonts')
CSS    = os.path.join(STATIC, 'icons', 'fontawesome', 'css', 'all.min.css')

WOFF2_MAGIC = b'wOF2'

def download(url, retries=8):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Encoding': 'identity',
        'Connection': 'close',
    }
    for attempt in range(1, retries+1):
        try:
            req = Request(url, headers=headers)
            resp = urlopen(req, timeout=90)
            total = int(resp.headers.get('Content-Length', 0))
            data, got = [], 0
            while True:
                try:
                    buf = resp.read(32768)
                except http.client.IncompleteRead as e:
                    buf = e.partial
                if not buf:
                    break
                data.append(buf)
                got += len(buf)
            content = b''.join(data)
            if total and len(content) != total:
                raise IOError(f'size mismatch {len(content)}/{total}')
            return content
        except Exception as e:
            print(f'    تلاش {attempt}/{retries} ناموفق: {e}')
            time.sleep(2*attempt)
    return None


def fetch_woff2(name, urls):
    print(f'  {name}:')
    for url in urls:
        print(f'    منبع: {url}')
        content = download(url)
        if content is None:
            continue
        if content[:4] != WOFF2_MAGIC:
            print(f'    ✗ هدر اشتباه ({content[:4]!r}) — رد شد')
            continue
        dest = os.path.join(WF_DIR, name)
        with open(dest, 'wb') as f:
            f.write(content)
        print(f'    ✓ معتبر و ذخیره شد ({len(content)} bytes)')
        return True
    print(f'    ✗ {name} از همه منابع ناموفق')
    return False


os.makedirs(WF_DIR, exist_ok=True)

# حذف فایل‌های فعلی webfont
for fname in list(os.listdir(WF_DIR)):
    os.remove(os.path.join(WF_DIR, fname))

ver = '6.5.2'
targets = {
    'fa-solid-900.woff2': [
        f'https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@{ver}/webfonts/fa-solid-900.woff2',
        f'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/{ver}/webfonts/fa-solid-900.woff2',
        f'https://use.fontawesome.com/releases/v{ver}/webfonts/fa-solid-900.woff2',
    ],
    'fa-regular-400.woff2': [
        f'https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@{ver}/webfonts/fa-regular-400.woff2',
        f'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/{ver}/webfonts/fa-regular-400.woff2',
        f'https://use.fontawesome.com/releases/v{ver}/webfonts/fa-regular-400.woff2',
    ],
    'fa-brands-400.woff2': [
        f'https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@{ver}/webfonts/fa-brands-400.woff2',
        f'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/{ver}/webfonts/fa-brands-400.woff2',
        f'https://use.fontawesome.com/releases/v{ver}/webfonts/fa-brands-400.woff2',
    ],
    'fa-v4compatibility.woff2': [
        f'https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@{ver}/webfonts/fa-v4compatibility.woff2',
        f'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/{ver}/webfonts/fa-v4compatibility.woff2',
    ],
}

print('دانلود و اعتبارسنجی webfont ها (بررسی magic header wOF2)...\n')
results = {}
for name, urls in targets.items():
    results[name] = fetch_woff2(name, urls)

print('\n' + '='*50)
all_ok = all(results.values())
if all_ok:
    print('🎉 همه فایل‌ها معتبر دانلود شدند!')
    print('Ctrl+Shift+R بزنید.')
else:
    failed = [k for k,v in results.items() if not v]
    print(f'⚠️ این فایل‌ها ناموفق بودند: {failed}')
    print('اینترنت را چک کنید و دوباره اجرا کنید: python fix_fa_final.py')