from django.db import models
from django.contrib.auth.models import User
from products.models import Product

# Importar modelos de auditoría
from .models_audit import AuditLog, UserSession


class PaymentMethod(models.Model):
    """
    Modelo para gestionar los métodos de pago disponibles (Ej: Tarjeta, Efectivo).
    """
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Método de Pago"
        verbose_name_plural = "Métodos de Pago"

    def __str__(self):
        return self.name


class Order(models.Model):
    class OrderStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'       # Actúa como el carrito de compras
        PROCESSING = 'PROCESSING', 'Processing' # En proceso de pago
        COMPLETED = 'COMPLETED', 'Completed' # Es una venta finalizada
        CANCELLED = 'CANCELLED', 'Cancelled'

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.id} by {self.customer.username} - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='order_items')
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2) # Precio al momento de la compra

    def __str__(self):
        return f"{self.quantity} of {self.product.name}"