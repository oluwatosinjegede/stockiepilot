from django.urls import path
from .views import products_view, edit_product, delete_product
from .views import get_product_price


urlpatterns = [
    path('', products_view, name='products'),
    path('price/<int:product_id>/', get_product_price, name='product_price'),
    path('edit/<int:product_id>/', edit_product, name='edit_product'),
    path('delete/<int:product_id>/', delete_product, name='delete_product'),
    
]