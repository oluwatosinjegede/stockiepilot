from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Payment)
def handle_successful_payment(sender, instance, created, **kwargs):
    if instance.status == 'success':
        from .services import activate_subscription
        activate_subscription(instance)