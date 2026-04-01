from django.urls import path
from .views import products_view
from .views import get_product_price

urlpatterns = [
    path('', products_view, name='products'),
    path('price/<int:product_id>/', get_product_price, name='product_price'),
    
]