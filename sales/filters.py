import django_filters
from .models import Order
from django.contrib.auth.models import User


class OrderFilter(django_filters.FilterSet):
    """
    Filtros avanzados para las Órdenes.
    Permite filtrar por rango de fechas, cliente, estado y monto total.
    
    Ejemplos de uso:
    - /api/sales/sales-history/?start_date=2024-01-01&end_date=2024-12-31
    - /api/sales/sales-history/?customer=5 (filtrar por ID de cliente)
    - /api/sales/sales-history/?customer_username=johndoe (filtrar por nombre de usuario)
    - /api/sales/sales-history/?status=COMPLETED
    - /api/sales/sales-history/?total_min=50&total_max=500
    - /api/sales/sales-history/?ordering=-total_price (ordenar por monto descendente)
    """
    
    # Filtros de fecha (created_at)
    start_date = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='gte',
        label='Fecha de inicio'
    )
    end_date = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='lte',
        label='Fecha de fin'
    )
    
    # Filtros de fecha (updated_at) - útil para ventas completadas
    completed_start = django_filters.DateFilter(
        field_name='updated_at',
        lookup_expr='gte',
        label='Completado desde'
    )
    completed_end = django_filters.DateFilter(
        field_name='updated_at',
        lookup_expr='lte',
        label='Completado hasta'
    )
    
    # Filtro por cliente (ID)
    customer = django_filters.ModelChoiceFilter(
        queryset=User.objects.all(),
        field_name='customer',
        label='Cliente (ID)'
    )
    
    # Filtro por nombre de usuario del cliente
    customer_username = django_filters.CharFilter(
        field_name='customer__username',
        lookup_expr='icontains',
        label='Cliente (username)'
    )
    
    # Filtro por email del cliente
    customer_email = django_filters.CharFilter(
        field_name='customer__email',
        lookup_expr='icontains',
        label='Cliente (email)'
    )
    
    # Filtro por estado
    status = django_filters.ChoiceFilter(
        choices=Order.OrderStatus.choices,
        field_name='status',
        label='Estado de la orden'
    )
    
    # Filtros de monto total (rango)
    total_min = django_filters.NumberFilter(
        field_name='total_price',
        lookup_expr='gte',
        label='Monto mínimo'
    )
    total_max = django_filters.NumberFilter(
        field_name='total_price',
        lookup_expr='lte',
        label='Monto máximo'
    )
    
    # Ordenamiento
    ordering = django_filters.OrderingFilter(
        fields=(
            ('created_at', 'created_at'),
            ('updated_at', 'updated_at'),
            ('total_price', 'total_price'),
            ('customer__username', 'customer_username'),
        ),
        field_labels={
            'created_at': 'Fecha de creación',
            'updated_at': 'Fecha de actualización',
            'total_price': 'Monto total',
            'customer_username': 'Cliente',
        }
    )

    class Meta:
        model = Order
        fields = [
            'start_date', 'end_date', 
            'completed_start', 'completed_end',
            'customer', 'customer_username', 'customer_email',
            'status', 'total_min', 'total_max'
        ]