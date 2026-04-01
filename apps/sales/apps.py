# apps/sales/apps.py

from django.apps import AppConfig


class SalesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sales'

    def ready(self):
        try:
            import apps.sales.signals  # noqa
        except ImportError:
            pass

