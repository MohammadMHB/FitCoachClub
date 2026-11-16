#!/usr/bin/env python3
"""اجرا در پوشه پروژه: python restore_css.py"""
import os, re

css = os.path.join('static', 'icons', 'fontawesome', 'css', 'all.min.css')
c = open(css, encoding='utf-8', errors='ignore').read()

# اصلاح مسیر دابل‌شده
c = c.replace('/static/icons/fontawesome//static/icons/fontawesome/webfonts/',
               '/static/icons/fontawesome/webfonts/')

open(css, 'w', encoding='utf-8').write(c)

m = re.search(r'url\([^)]*\)', c)
print("مسیر الان:", m.group() if m else "پیدا نشد")
print("✅ اصلاح شد. حالا Ctrl+Shift+R بزنید.")