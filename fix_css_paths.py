#!/usr/bin/env python3
"""اجرا در پوشه پروژه (کنار manage.py): python fix_css_paths.py"""
import os, re

css = os.path.join('static', 'icons', 'fontawesome', 'css', 'all.min.css')
if not os.path.exists(css):
    print("❌ فایل پیدا نشد:", css)
    exit(1)

c = open(css, encoding='utf-8', errors='ignore').read()
print("اولین url() قبل از اصلاح:")
m = re.search(r'url\([^)]*\)', c)
print(" ", m.group() if m else "پیدا نشد")

before = c
c = c.replace('../webfonts/', '/static/icons/fontawesome/webfonts/')
c = c.replace('./webfonts/',  '/static/icons/fontawesome/webfonts/')
c = c.replace('webfonts/',    '/static/icons/fontawesome/webfonts/')  # fallback اگر مسیر دیگه‌ای بود

# جلوگیری از دابل شدن مسیر در صورت اجرای چندباره
c = c.replace('/static/icons/fontawesome/webfonts//static/icons/fontawesome/webfonts/',
               '/static/icons/fontawesome/webfonts/')

open(css, 'w', encoding='utf-8').write(c)

print("\nاولین url() بعد از اصلاح:")
m = re.search(r'url\([^)]*\)', c)
print(" ", m.group() if m else "پیدا نشد")

print("\n" + ("✅ تغییر اعمال شد" if c != before else "ℹ️ تغییری لازم نبود"))

# بررسی وجود فایل‌های webfont
wf_dir = os.path.join('static', 'icons', 'fontawesome', 'webfonts')
print("\nفایل‌های webfont موجود:")
if os.path.isdir(wf_dir):
    for f in os.listdir(wf_dir):
        print("  -", f)
else:
    print("  ❌ پوشه webfonts وجود ندارد!")

print("\nحالا Ctrl+Shift+R (Hard Refresh) در مرورگر بزنید.")