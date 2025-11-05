from rest_framework import serializers
from .models import Order, OrderItem, PaymentMethod # Importar PaymentMethod
from products.serializers import ProductSerializer
from api.serializers import UserSerializer


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ['id', 'name', 'is_active']


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Serializador para los artículos dentro de una orden (carrito).
    """
    product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price']


class OrderSerializer(serializers.ModelSerializer):
    """
    Serializador para la Orden/Venta (el carrito de compras).
    """
    items = OrderItemSerializer(many=True, read_only=True)
    customer = UserSerializer(read_only=True)
    payment_method_detail = PaymentMethodSerializer(source='payment_method', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'status', 'total_price', 
            'payment_method', 'payment_method_detail', 
            'created_at', 'items'
        ]
        read_only_fields = ['customer', 'status', 'total_price', 'created_at']