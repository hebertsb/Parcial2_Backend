# sales/report_generator.py
"""
Generador dinámico de reportes basado en parámetros extraídos de prompts.
"""

from django.db.models import Sum, Count, F, Q, Avg, Max, Min
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Order, OrderItem
from products.models import Product, Category
from decimal import Decimal
from datetime import datetime


class ReportGenerator:
    """
    Clase para generar reportes dinámicos basados en parámetros.
    """
    
    def __init__(self, params):
        self.params = params
        self.report_data = {
            'title': '',
            'subtitle': '',
            'headers': [],
            'rows': [],
            'totals': {},
            'metadata': {}
        }
    
    def generate(self):
        """
        Genera el reporte según el tipo especificado en los parámetros.
        """
        report_type = self.params.get('report_type', 'sales')
        
        if report_type == 'sales':
            return self._generate_sales_report()
        elif report_type == 'products':
            return self._generate_products_report()
        elif report_type == 'clients':
            return self._generate_clients_report()
        elif report_type == 'revenue':
            return self._generate_revenue_report()
        else:
            return self._generate_sales_report()  # Por defecto
    
    def _generate_sales_report(self):
        """
        Genera reporte de ventas según agrupación solicitada.
        """
        group_by = self.params.get('group_by')
        
        if group_by == 'product':
            return self._sales_by_product()
        elif group_by == 'client':
            return self._sales_by_client()
        elif group_by == 'category':
            return self._sales_by_category()
        elif group_by == 'date':
            return self._sales_by_date()
        else:
            return self._sales_general()
    
    def _get_base_orders_queryset(self):
        """
        Obtiene el queryset base de órdenes filtrado por fechas.
        """
        queryset = Order.objects.filter(status='COMPLETED')
        
        if self.params.get('start_date'):
            queryset = queryset.filter(updated_at__gte=self.params['start_date'])
        
        if self.params.get('end_date'):
            queryset = queryset.filter(updated_at__lte=self.params['end_date'])
        
        return queryset
    
    def _sales_by_product(self):
        """
        Reporte de ventas agrupado por producto.
        """
        self.report_data['title'] = 'Reporte de Ventas por Producto'
        self.report_data['subtitle'] = self._get_date_range_text()
        self.report_data['headers'] = ['Producto', 'Categoría', 'Cantidad Vendida', 'Ingresos Totales', 'Precio Promedio']
        
        # Obtener items de órdenes completadas en el rango de fechas
        order_items = OrderItem.objects.filter(
            order__in=self._get_base_orders_queryset()
        ).select_related('product', 'product__category')
        
        # Agrupar por producto
        product_stats = {}
        for item in order_items:
            product_id = item.product.id
            if product_id not in product_stats:
                product_stats[product_id] = {
                    'name': item.product.name,
                    'category': item.product.category.name,
                    'quantity': 0,
                    'revenue': Decimal('0.00'),
                    'prices': []
                }
            
            product_stats[product_id]['quantity'] += item.quantity
            product_stats[product_id]['revenue'] += item.price * item.quantity
            product_stats[product_id]['prices'].append(float(item.price))
        
        # Construir filas
        for product_id, stats in product_stats.items():
            avg_price = sum(stats['prices']) / len(stats['prices']) if stats['prices'] else 0
            self.report_data['rows'].append([
                stats['name'],
                stats['category'],
                stats['quantity'],
                f"${stats['revenue']:.2f}",
                f"${avg_price:.2f}"
            ])
        
        # Ordenar por ingresos (mayor a menor)
        self.report_data['rows'].sort(key=lambda x: float(x[3].replace('$', '')), reverse=True)
        
        # Calcular totales
        total_quantity = sum(stats['quantity'] for stats in product_stats.values())
        total_revenue = sum(stats['revenue'] for stats in product_stats.values())
        
        self.report_data['totals'] = {
            'total_products': len(product_stats),
            'total_quantity': total_quantity,
            'total_revenue': f"${total_revenue:.2f}"
        }
        
        return self.report_data
    
    def _sales_by_client(self):
        """
        Reporte de ventas agrupado por cliente.
        """
        self.report_data['title'] = 'Reporte de Ventas por Cliente'
        self.report_data['subtitle'] = self._get_date_range_text()
        self.report_data['headers'] = ['Cliente', 'Email', 'Cantidad de Compras', 'Monto Total', 'Ticket Promedio']
        
        # ✅ OPTIMIZADO: select_related para traer datos del cliente
        orders = self._get_base_orders_queryset().select_related('customer')
        
        # Agrupar por cliente
        client_stats = orders.values(
            'customer__id',
            'customer__username',
            'customer__email',
            'customer__first_name',
            'customer__last_name'
        ).annotate(
            num_orders=Count('id'),
            total_spent=Sum('total_price')
        )
        
        # Construir filas
        for stats in client_stats:
            full_name = f"{stats['customer__first_name']} {stats['customer__last_name']}".strip()
            if not full_name:
                full_name = stats['customer__username']
            
            avg_ticket = float(stats['total_spent']) / stats['num_orders'] if stats['num_orders'] > 0 else 0
            
            self.report_data['rows'].append([
                full_name,
                stats['customer__email'],
                stats['num_orders'],
                f"${stats['total_spent']:.2f}",
                f"${avg_ticket:.2f}"
            ])
        
        # Ordenar por monto total (mayor a menor)
        self.report_data['rows'].sort(key=lambda x: float(x[3].replace('$', '')), reverse=True)
        
        # Calcular totales
        total_orders = sum(row[2] for row in self.report_data['rows'])
        total_revenue = sum(float(row[3].replace('$', '')) for row in self.report_data['rows'])
        
        self.report_data['totals'] = {
            'total_clients': len(self.report_data['rows']),
            'total_orders': total_orders,
            'total_revenue': f"${total_revenue:.2f}"
        }
        
        return self.report_data
    
    def _sales_by_category(self):
        """
        Reporte de ventas agrupado por categoría.
        """
        self.report_data['title'] = 'Reporte de Ventas por Categoría'
        self.report_data['subtitle'] = self._get_date_range_text()
        self.report_data['headers'] = ['Categoría', 'Productos Vendidos', 'Cantidad Total', 'Ingresos Totales']
        
        order_items = OrderItem.objects.filter(
            order__in=self._get_base_orders_queryset()
        ).select_related('product__category')
        
        # Agrupar por categoría
        category_stats = {}
        for item in order_items:
            category_name = item.product.category.name
            if category_name not in category_stats:
                category_stats[category_name] = {
                    'products': set(),
                    'quantity': 0,
                    'revenue': Decimal('0.00')
                }
            
            category_stats[category_name]['products'].add(item.product.id)
            category_stats[category_name]['quantity'] += item.quantity
            category_stats[category_name]['revenue'] += item.price * item.quantity
        
        # Construir filas
        for category, stats in category_stats.items():
            self.report_data['rows'].append([
                category,
                len(stats['products']),
                stats['quantity'],
                f"${stats['revenue']:.2f}"
            ])
        
        # Ordenar por ingresos (mayor a menor)
        self.report_data['rows'].sort(key=lambda x: float(x[3].replace('$', '')), reverse=True)
        
        # Calcular totales
        total_quantity = sum(stats['quantity'] for stats in category_stats.values())
        total_revenue = sum(stats['revenue'] for stats in category_stats.values())
        
        self.report_data['totals'] = {
            'total_categories': len(category_stats),
            'total_quantity': total_quantity,
            'total_revenue': f"${total_revenue:.2f}"
        }
        
        return self.report_data
    
    def _sales_by_date(self):
        """
        Reporte de ventas agrupado por fecha (día a día).
        """
        self.report_data['title'] = 'Reporte de Ventas por Fecha'
        self.report_data['subtitle'] = self._get_date_range_text()
        self.report_data['headers'] = ['Fecha', 'Número de Ventas', 'Productos Vendidos', 'Ingresos del Día']
        
        orders = self._get_base_orders_queryset().order_by('updated_at')
        
        # Agrupar por fecha
        date_stats = {}
        for order in orders:
            date_key = order.updated_at.strftime('%Y-%m-%d')
            if date_key not in date_stats:
                date_stats[date_key] = {
                    'num_orders': 0,
                    'total_items': 0,
                    'revenue': Decimal('0.00')
                }
            
            date_stats[date_key]['num_orders'] += 1
            date_stats[date_key]['total_items'] += order.items.count()
            date_stats[date_key]['revenue'] += order.total_price
        
        # Construir filas
        for date_str, stats in sorted(date_stats.items()):
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d/%m/%Y')
            
            self.report_data['rows'].append([
                formatted_date,
                stats['num_orders'],
                stats['total_items'],
                f"${stats['revenue']:.2f}"
            ])
        
        # Calcular totales
        total_orders = sum(stats['num_orders'] for stats in date_stats.values())
        total_items = sum(stats['total_items'] for stats in date_stats.values())
        total_revenue = sum(stats['revenue'] for stats in date_stats.values())
        
        self.report_data['totals'] = {
            'total_days': len(date_stats),
            'total_orders': total_orders,
            'total_items': total_items,
            'total_revenue': f"${total_revenue:.2f}"
        }
        
        return self.report_data
    
    def _sales_general(self):
        """
        Reporte general de ventas (sin agrupación específica).
        """
        self.report_data['title'] = 'Reporte General de Ventas'
        self.report_data['subtitle'] = self._get_date_range_text()
        self.report_data['headers'] = ['ID Orden', 'Cliente', 'Fecha', 'Productos', 'Total']
        
        orders = self._get_base_orders_queryset().order_by('-updated_at')
        
        for order in orders:
            self.report_data['rows'].append([
                f"#{order.id}",
                order.customer.username,
                order.updated_at.strftime('%d/%m/%Y %H:%M'),
                order.items.count(),
                f"${order.total_price:.2f}"
            ])
        
        # Calcular totales
        total_revenue = sum(order.total_price for order in orders)
        
        self.report_data['totals'] = {
            'total_orders': orders.count(),
            'total_revenue': f"${total_revenue:.2f}"
        }
        
        return self.report_data
    
    def _generate_products_report(self):
        """
        Reporte de productos (inventario, stock, etc.).
        """
        self.report_data['title'] = 'Reporte de Productos'
        self.report_data['subtitle'] = 'Inventario Actual'
        self.report_data['headers'] = ['Producto', 'Categoría', 'Precio', 'Stock Actual', 'Valor en Inventario']
        
        products = Product.objects.select_related('category').order_by('name')
        
        total_value = Decimal('0.00')
        for product in products:
            inventory_value = product.price * product.stock
            total_value += inventory_value
            
            self.report_data['rows'].append([
                product.name,
                product.category.name,
                f"${product.price:.2f}",
                product.stock,
                f"${inventory_value:.2f}"
            ])
        
        self.report_data['totals'] = {
            'total_products': products.count(),
            'total_inventory_value': f"${total_value:.2f}"
        }
        
        return self.report_data
    
    def _generate_clients_report(self):
        """
        Reporte de clientes (básicamente lo mismo que sales_by_client).
        """
        return self._sales_by_client()
    
    def _generate_revenue_report(self):
        """
        Reporte de ingresos (similar a sales general pero enfocado en dinero).
        """
        return self._sales_general()
    
    def _get_date_range_text(self):
        """
        Genera texto descriptivo del rango de fechas.
        """
        if self.params.get('start_date') and self.params.get('end_date'):
            start = self.params['start_date'].strftime('%d/%m/%Y')
            end = self.params['end_date'].strftime('%d/%m/%Y')
            return f"Período: {start} - {end}"
        elif self.params.get('start_date'):
            start = self.params['start_date'].strftime('%d/%m/%Y')
            return f"Desde: {start}"
        elif self.params.get('end_date'):
            end = self.params['end_date'].strftime('%d/%m/%Y')
            return f"Hasta: {end}"
        else:
            return "Todas las fechas"


def generate_report(params):
    """
    Función helper para generar un reporte.
    
    Args:
        params (dict): Parámetros del reporte
    
    Returns:
        dict: Datos del reporte generado
    """
    generator = ReportGenerator(params)
    return generator.generate()
