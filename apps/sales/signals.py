from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import SaleItem


# =========================
# STOCK MANAGEMENT
# =========================

@receiver(post_save, sender=SaleItem)
def handle_stock_on_save(sender, instance, created, **kwargs):
    product = instance.product

    if created:
        #  Reduce stock on create
        if product.quantity < instance.quantity:
            raise ValueError("Not enough stock available")

        product.quantity -= instance.quantity
        product.save(update_fields=["quantity"])

    else:
        #  Handle update (adjust difference)
        try:
            old_item = SaleItem.objects.get(pk=instance.pk)
        except SaleItem.DoesNotExist:
            return

        difference = instance.quantity - old_item.quantity

        if difference > 0:
            if product.quantity < difference:
                raise ValueError("Not enough stock available")

            product.quantity -= difference
        else:
            product.quantity += abs(difference)

        product.save(update_fields=["quantity"])


@receiver(post_delete, sender=SaleItem)
def restore_stock_on_delete(sender, instance, **kwargs):
    product = instance.product

    #  Restore stock when item is deleted
    product.quantity += instance.quantity
    product.save(update_fields=["quantity"])


# =========================
# SALE TOTAL CALCULATION
# =========================

@receiver(post_save, sender=SaleItem)
@receiver(post_delete, sender=SaleItem)
def update_sale_total(sender, instance, **kwargs):
    sale = instance.sale

    sale.recalculate_totals()
    sale.save(update_fields=["total_amount", "amount_paid", "balance", "status"])