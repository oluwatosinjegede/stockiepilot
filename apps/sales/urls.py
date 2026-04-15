from django.urls import path
from .views import create_sale, sales_view, update_sale_payment   #  import correct view

urlpatterns = [
    path('', sales_view, name='sales'),      #  FIXED
    path('create/', create_sale, name='create_sale'),
     path('<int:sale_id>/payment/', update_sale_payment, name='update_sale_payment'),
]