"""Isolated, disposable demo; the normal Chabokan settings are unchanged."""
import os
from pathlib import Path

from fitcoach.settings import *

DEBUG = False
DEMO_DATA_DIR = Path(os.environ.get('DEMO_DATA_DIR', '/tmp/fitcoachclub-demo'))
DEMO_DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': DEMO_DATA_DIR / 'db.sqlite3',
}}
MEDIA_ROOT = DEMO_DATA_DIR / 'media'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
CSRF_TRUSTED_ORIGINS = []
if os.environ.get('RENDER_EXTERNAL_HOSTNAME'):
    ALLOWED_HOSTS.append(os.environ['RENDER_EXTERNAL_HOSTNAME'])
    CSRF_TRUSTED_ORIGINS.append('https://' + os.environ['RENDER_EXTERNAL_HOSTNAME'])
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
MELIPAYAMAK_USERNAME = ''
MELIPAYAMAK_PASSWORD = ''
MELIPAYAMAK_SENDER = ''
MIDDLEWARE = ['deployment.demo_middleware.DemoNoticeMiddleware'] + MIDDLEWARE
