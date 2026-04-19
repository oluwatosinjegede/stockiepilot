from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .services import register_affiliate_for_user


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_affiliate_wallet_for_affiliate(sender, instance, created, **kwargs):
    if not created:
        return

    if getattr(instance, "is_affiliate", False):
        register_affiliate_for_user(instance)
