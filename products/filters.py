import django_filters
from .models import Product, Category


class ProductFilter(django_filters.FilterSet):
    """
    Filtros avanzados para productos.
    Permite filtrar por categoría, rango de precio, stock mínimo, y búsqueda por nombre.
    """
    # Filtro por nombre (búsqueda parcial, insensible a mayúsculas)
    name = django_filters.CharFilter(lookup_expr='icontains', label='Nombre del producto')
    
    # Filtro por categoría (puede ser por ID o slug)
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.all(),
        field_name='category',
        label='Categoría'
    )
    category_slug = django_filters.CharFilter(
        field_name='category__slug',
        lookup_expr='exact',
        label='Categoría (slug)'
    )
    
    # Filtros de precio (rango)
    price_min = django_filters.NumberFilter(
        field_name='price',
        lookup_expr='gte',
        label='Precio mínimo'
    )
    price_max = django_filters.NumberFilter(
        field_name='price',
        lookup_expr='lte',
        label='Precio máximo'
    )
    
    # Filtro de stock
    stock_min = django_filters.NumberFilter(
        field_name='stock',
        lookup_expr='gte',
        label='Stock mínimo'
    )
    
    # Filtro para productos en stock (disponibles)
    in_stock = django_filters.BooleanFilter(
        method='filter_in_stock',
        label='Solo productos en stock'
    )
    
    # Ordenamiento
    ordering = django_filters.OrderingFilter(
        fields=(
            ('price', 'price'),
            ('created_at', 'created_at'),
            ('name', 'name'),
            ('stock', 'stock'),
        ),
        field_labels={
            'price': 'Precio',
            'created_at': 'Fecha de creación',
            'name': 'Nombre',
            'stock': 'Stock',
        }
    )
    
    class Meta:
        model = Product
        fields = ['name', 'category', 'category_slug', 'price_min', 'price_max', 'stock_min', 'in_stock']
    
    def filter_in_stock(self, queryset, name, value):
        """
        Filtra productos que tienen stock > 0
        """
        if value:
            return queryset.filter(stock__gt=0)
        return queryset
