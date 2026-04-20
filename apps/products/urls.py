from django.urls import path

from .views import (
    create_supplier_view,
    delete_product,
    edit_product,
    get_product_price,
    products_view,
    supplier_list_view,
)

urlpatterns = [
    path("", products_view, name="products"),
    path("suppliers/", supplier_list_view, name="suppliers"),
    path("suppliers/create/", create_supplier_view, name="create_supplier"),
    path("price/<int:product_id>/", get_product_price, name="product_price"),
    path("edit/<int:product_id>/", edit_product, name="edit_product"),
    path("delete/<int:product_id>/", delete_product, name="delete_product"),
]