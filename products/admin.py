from django.contrib import admin
from .models import Category, Product

# Registra los modelos para que aparezcan en el panel de admin
admin.site.register(Category)
admin.site.register(Product)