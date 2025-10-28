from django.contrib import admin
from .models import Order, OrderItem

# Registra los modelos para que aparezcan en el panel de admin
admin.site.register(Order)
admin.site.register(OrderItem)