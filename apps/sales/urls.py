from django.urls import path
from .views import create_sale, sales_view   #  import correct view

urlpatterns = [
    path('', sales_view, name='sales'),      #  FIXED
    path('create/', create_sale, name='create_sale'),
]