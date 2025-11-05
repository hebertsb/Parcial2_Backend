# sales/analytics.py
"""
Módulo para análisis avanzado y estadísticas del sistema
"""

from django.db.models import Sum, Count, Avg, F, Q, Max
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import Order, OrderItem
from products.models import Product, Category
from django.contrib.auth.models import User


class DashboardAnalytics:
    """Clase para generar estadísticas del dashboard en tiempo real"""
    
    @staticmethod
    def get_real_time_stats():
        """Obtiene estadísticas en tiempo real del sistema"""
        
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)
        
        # Ventas de hoy
        today_sales = Order.objects.filter(
            status='COMPLETED',
            updated_at__gte=today_start
        ).aggregate(
            total=Sum('total_price'),
            count=Count('id')
        )
        
        # Ventas de la semana
        week_sales = Order.objects.filter(
            status='COMPLETED',
            updated_at__gte=week_start
        ).aggregate(
            total=Sum('total_price'),
            count=Count('id')
        )
        
        # Ventas del mes
        month_sales = Order.objects.filter(
            status='COMPLETED',
            updated_at__gte=month_start
        ).aggregate(
            total=Sum('total_price'),
            count=Count('id'),
            avg_ticket=Avg('total_price')
        )
        
        # Productos con stock bajo (menos de 10)
        low_stock_products = Product.objects.filter(stock__lt=10).count()
        
        # Productos sin stock
        out_of_stock = Product.objects.filter(stock=0).count()
        
        # Clientes activos (con al menos una compra)
        active_customers = User.objects.filter(
            orders__status='COMPLETED'
        ).distinct().count()
        
        # Nuevos clientes del mes
        new_customers = User.objects.filter(
            date_joined__gte=month_start
        ).count()
        
        # Top 5 productos más vendidos del mes
        top_products = OrderItem.objects.filter(
            order__status='COMPLETED',
            order__updated_at__gte=month_start
        ).select_related(
            'product'  # ✅ OPTIMIZADO: traer el producto en la misma consulta
        ).values(
            'product__name',
            'product__id'
        ).annotate(
            total_sold=Sum('quantity'),
            revenue=Sum(F('price') * F('quantity'))
        ).order_by('-total_sold')[:5]
        
        # Top 5 clientes del mes
        top_customers = Order.objects.filter(
            status='COMPLETED',
            updated_at__gte=month_start
        ).select_related(
            'customer'  # ✅ OPTIMIZADO: traer datos del cliente
        ).values(
            'customer__username',
            'customer__email',
            'customer__id'
        ).annotate(
            total_spent=Sum('total_price'),
            order_count=Count('id')
        ).order_by('-total_spent')[:5]
        
        # Categorías más vendidas
        top_categories = OrderItem.objects.filter(
            order__status='COMPLETED',
            order__updated_at__gte=month_start
        ).select_related(
            'product__category'  # ✅ OPTIMIZADO: traer categoría del producto
        ).values(
            'product__category__name',
            'product__category__id'
        ).annotate(
            total_sold=Sum('quantity'),
            revenue=Sum(F('price') * F('quantity'))
        ).order_by('-revenue')[:5]
        
        # Tendencia de ventas (últimos 7 días)
        sales_trend = []
        for i in range(7):
            day = now - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            day_stats = Order.objects.filter(
                status='COMPLETED',
                updated_at__gte=day_start,
                updated_at__lt=day_end
            ).aggregate(
                total=Sum('total_price'),
                count=Count('id')
            )
            
            sales_trend.append({
                'date': day_start.strftime('%Y-%m-%d'),
                'day_name': day_start.strftime('%A'),
                'total_sales': float(day_stats['total'] or 0),
                'order_count': day_stats['count'] or 0
            })
        
        sales_trend.reverse()  # Ordenar cronológicamente
        
        return {
            'today': {
                'total_sales': float(today_sales['total'] or 0),
                'order_count': today_sales['count'] or 0
            },
            'week': {
                'total_sales': float(week_sales['total'] or 0),
                'order_count': week_sales['count'] or 0
            },
            'month': {
                'total_sales': float(month_sales['total'] or 0),
                'order_count': month_sales['count'] or 0,
                'avg_ticket': float(month_sales['avg_ticket'] or 0)
            },
            'inventory': {
                'low_stock_count': low_stock_products,
                'out_of_stock_count': out_of_stock,
                'total_products': Product.objects.count()
            },
            'customers': {
                'active_count': active_customers,
                'new_this_month': new_customers,
                'total_count': User.objects.count()
            },
            'top_products': [
                {
                    'product_id': item['product__id'],
                    'product_name': item['product__name'],
                    'quantity_sold': item['total_sold'],
                    'revenue': float(item['revenue'])
                }
                for item in top_products
            ],
            'top_customers': [
                {
                    'customer_id': item['customer__id'],
                    'username': item['customer__username'],
                    'email': item['customer__email'],
                    'total_spent': float(item['total_spent']),
                    'order_count': item['order_count']
                }
                for item in top_customers
            ],
            'top_categories': [
                {
                    'category_id': item['product__category__id'],
                    'category_name': item['product__category__name'],
                    'quantity_sold': item['total_sold'],
                    'revenue': float(item['revenue'])
                }
                for item in top_categories
            ],
            'sales_trend': sales_trend,
            'timestamp': now.isoformat()
        }
    
    @staticmethod
    def get_product_performance(product_id=None):
        """Analiza el rendimiento de productos"""
        
        queryset = OrderItem.objects.filter(order__status='COMPLETED')
        
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        performance = queryset.values(
            'product__id',
            'product__name',
            'product__price',
            'product__stock',
            'product__category__name'
        ).annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum(F('price') * F('quantity')),
            times_purchased=Count('order', distinct=True)
        ).order_by('-total_revenue')
        
        return list(performance)
    
    @staticmethod
    def get_customer_insights(customer_id=None):
        """Analiza el comportamiento de clientes"""
        
        queryset = Order.objects.filter(status='COMPLETED')
        
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        insights = queryset.values(
            'customer__id',
            'customer__username',
            'customer__email',
            'customer__date_joined'
        ).annotate(
            total_orders=Count('id'),
            total_spent=Sum('total_price'),
            avg_order_value=Avg('total_price'),
            last_purchase=Max('updated_at')
        ).order_by('-total_spent')
        
        return list(insights)
