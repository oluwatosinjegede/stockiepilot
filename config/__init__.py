import os

if os.getenv("RUN_CELERY", "False") == "True":
    from .celery import app as celery_app
    __all__ = ('celery_app',)