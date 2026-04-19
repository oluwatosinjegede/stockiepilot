from django.apps import AppConfig


class AffiliatesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.affiliates"

    def ready(self):
        import apps.affiliates.signals  # noqa: F401
