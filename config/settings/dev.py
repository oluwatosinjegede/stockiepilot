from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

# ================= STATIC FILES =================

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'