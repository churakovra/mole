from django.urls import path
from django.db import transaction
from .models import Order

def create_order(request):
    with transaction.atomic():
        order = Order.objects.create()
        order.save()
    return order

urlpatterns = [path('orders/', create_order)]
