from django.urls import path

from .views import (
    create_sale,
    invoice_list,
    payment_receipt_detail,
    receipt_list,
    sale_invoice_detail,
    sales_view,
    update_sale_payment,
)

urlpatterns = [
    path("", sales_view, name="sales"),
    path("create/", create_sale, name="create_sale"),
    path("invoices/", invoice_list, name="invoice_list"),
    path("receipts/", receipt_list, name="receipt_list"),
    path("<int:sale_id>/payment/", update_sale_payment, name="update_sale_payment"),
    path("<int:sale_id>/invoice/", sale_invoice_detail, name="sale_invoice_detail"),
    path("receipts/<int:receipt_id>/", payment_receipt_detail, name="payment_receipt_detail"),
]