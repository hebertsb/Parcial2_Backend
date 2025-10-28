# sales/advanced_reports.py
"""
Sistema de Reportes Dinámicos Avanzados
Incluye análisis RFM, ABC, comparativos y dashboards ejecutivos
"""

from django.db.models import Sum, Count, F, Q, Avg, Max, Min, Case, When, Value, DecimalField
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from .models import Order, OrderItem
from products.models import Product, Category


class AdvancedReportGenerator:
    """
    Generador de reportes dinámicos avanzados con capacidades de análisis profundo.
    """
    
    def __init__(self, params):
        self.params = params
        self.report_data = {
            'title': '',
            'subtitle': '',
            'headers': [],
            'rows': [],
            'totals': {},
            'metadata': {},
            'kpis': {},
            'alerts': []
        }
    
    # ========== ANÁLISIS DE CLIENTES (RFM) ==========
    
    def customer_rfm_analysis(self):
        """
        Análisis RFM (Recency, Frequency, Monetary) de clientes.
        Segmenta clientes en: VIP, Regular, Nuevo, En Riesgo, Inactivo.
        """
        self.report_data['title'] = 'Análisis RFM de Clientes'
        self.report_data['subtitle'] = self._get_date_range_text()
        self.report_data['headers'] = [
            'Cliente', 'Email', 'Última Compra (días)', 
            'Frecuencia', 'Monto Total', 'Ticket Prom.', 'Segmento'
        ]
        
        # Obtener órdenes completadas en el rango
        base_orders = self._get_base_orders()
        now = timezone.now()
        
        # Calcular métricas por cliente
        customers_data = []
        for user in User.objects.filter(profile__role='CLIENT'):
            user_orders = base_orders.filter(customer=user)
            
            if not user_orders.exists():
                continue
            
            # Recency: Días desde última compra
            last_order = user_orders.latest('updated_at')
            days_since_last = (now - last_order.updated_at).days
            
            # Frequency: Número de compras
            frequency = user_orders.count()
            
            # Monetary: Monto total gastado
            monetary = user_orders.aggregate(total=Sum('total_price'))['total'] or Decimal('0')
            
            # Ticket promedio
            avg_ticket = monetary / frequency if frequency > 0 else Decimal('0')
            
            # Segmentación
            segment = self._segment_customer(days_since_last, frequency, float(monetary))
            
            customers_data.append({
                'user': user,
                'recency': days_since_last,
                'frequency': frequency,
                'monetary': monetary,
                'avg_ticket': avg_ticket,
                'segment': segment
            })
        
        # Ordenar por valor monetario (descendente)
        customers_data.sort(key=lambda x: x['monetary'], reverse=True)
        
        # Construir filas
        for data in customers_data:
            full_name = f"{data['user'].first_name} {data['user'].last_name}".strip()
            if not full_name:
                full_name = data['user'].username
            
            self.report_data['rows'].append([
                full_name,
                data['user'].email,
                data['recency'],
                data['frequency'],
                f"${data['monetary']:.2f}",
                f"${data['avg_ticket']:.2f}",
                data['segment']
            ])
        
        # Calcular totales y estadísticas
        total_customers = len(customers_data)
        total_revenue = sum(d['monetary'] for d in customers_data)
        avg_frequency = sum(d['frequency'] for d in customers_data) / total_customers if total_customers > 0 else 0
        
        # Contar por segmento
        segment_counts = {}
        for data in customers_data:
            segment = data['segment']
            segment_counts[segment] = segment_counts.get(segment, 0) + 1
        
        self.report_data['totals'] = {
            'total_customers': total_customers,
            'total_revenue': f"${total_revenue:.2f}",
            'avg_frequency': f"{avg_frequency:.1f}",
            'vip_customers': segment_counts.get('🌟 VIP', 0),
            'regular_customers': segment_counts.get('✅ Regular', 0),
            'at_risk_customers': segment_counts.get('⚠️ En Riesgo', 0),
            'new_customers': segment_counts.get('🆕 Nuevo', 0),
            'inactive_customers': segment_counts.get('😴 Inactivo', 0)
        }
        
        # KPIs
        self.report_data['kpis'] = {
            'vip_percentage': f"{(segment_counts.get('🌟 VIP', 0) / total_customers * 100) if total_customers > 0 else 0:.1f}%",
            'retention_rate': f"{((total_customers - segment_counts.get('😴 Inactivo', 0)) / total_customers * 100) if total_customers > 0 else 0:.1f}%",
            'avg_customer_value': f"${(total_revenue / total_customers) if total_customers > 0 else 0:.2f}"
        }
        
        # Alertas
        if segment_counts.get('⚠️ En Riesgo', 0) > 0:
            self.report_data['alerts'].append(
                f"⚠️ {segment_counts['⚠️ En Riesgo']} clientes en riesgo de abandonar"
            )
        if segment_counts.get('😴 Inactivo', 0) > total_customers * 0.3:
            self.report_data['alerts'].append(
                f"🚨 Alta tasa de clientes inactivos ({segment_counts['😴 Inactivo']})"
            )
        
        return self.report_data
    
    def _segment_customer(self, recency, frequency, monetary):
        """Segmenta un cliente según criterios RFM."""
        # VIP: Compra reciente, alta frecuencia, alto monto
        if recency <= 30 and frequency >= 5 and monetary >= 500:
            return '🌟 VIP'
        
        # Regular: Actividad moderada
        elif recency <= 60 and frequency >= 2 and monetary >= 100:
            return '✅ Regular'
        
        # En Riesgo: No compra hace 60-90 días pero era activo
        elif 60 < recency <= 90 and frequency >= 2:
            return '⚠️ En Riesgo'
        
        # Nuevo: Primera compra reciente
        elif recency <= 30 and frequency == 1:
            return '🆕 Nuevo'
        
        # Inactivo: Sin compras hace más de 90 días
        else:
            return '😴 Inactivo'
    
    # ========== ANÁLISIS DE PRODUCTOS (ABC) ==========
    
    def product_abc_analysis(self):
        """
        Análisis ABC de productos (Principio de Pareto 80/20).
        Clasifica productos en A (80% ingresos), B (15%), C (5%).
        """
        self.report_data['title'] = 'Análisis ABC de Productos'
        self.report_data['subtitle'] = self._get_date_range_text()
        self.report_data['headers'] = [
            'Producto', 'Categoría', 'Unidades Vendidas', 
            'Ingresos', '% del Total', '% Acumulado', 'Clasificación'
        ]
        
        # Obtener ventas por producto
        order_items = OrderItem.objects.filter(
            order__in=self._get_base_orders()
        ).select_related('product', 'product__category')
        
        # Agrupar por producto
        product_stats = {}
        for item in order_items:
            product_id = item.product.id
            if product_id not in product_stats:
                product_stats[product_id] = {
                    'product': item.product,
                    'quantity': 0,
                    'revenue': Decimal('0')
                }
            
            product_stats[product_id]['quantity'] += item.quantity
            product_stats[product_id]['revenue'] += item.price * item.quantity
        
        # Ordenar por ingresos (mayor a menor)
        sorted_products = sorted(
            product_stats.values(),
            key=lambda x: x['revenue'],
            reverse=True
        )
        
        # Calcular total de ingresos
        total_revenue = sum(p['revenue'] for p in sorted_products)
        
        # Calcular porcentajes y clasificar
        accumulated = 0
        for product in sorted_products:
            percentage = (product['revenue'] / total_revenue * 100) if total_revenue > 0 else 0
            accumulated += percentage
            
            # Clasificación ABC
            if accumulated <= 80:
                classification = '🅰️ Clase A (80%)'
            elif accumulated <= 95:
                classification = '🅱️ Clase B (15%)'
            else:
                classification = '🅲 Clase C (5%)'
            
            product['percentage'] = percentage
            product['accumulated'] = accumulated
            product['classification'] = classification
        
        # Construir filas
        for product in sorted_products:
            self.report_data['rows'].append([
                product['product'].name,
                product['product'].category.name,
                product['quantity'],
                f"${product['revenue']:.2f}",
                f"{product['percentage']:.1f}%",
                f"{product['accumulated']:.1f}%",
                product['classification']
            ])
        
        # Contar por clasificación
        count_a = sum(1 for p in sorted_products if '🅰️' in p['classification'])
        count_b = sum(1 for p in sorted_products if '🅱️' in p['classification'])
        count_c = sum(1 for p in sorted_products if '🅲' in p['classification'])
        
        self.report_data['totals'] = {
            'total_products': len(sorted_products),
            'total_revenue': f"${total_revenue:.2f}",
            'class_a_products': count_a,
            'class_b_products': count_b,
            'class_c_products': count_c
        }
        
        # KPIs
        self.report_data['kpis'] = {
            'pareto_efficiency': f"{(count_a / len(sorted_products) * 100) if sorted_products else 0:.1f}%",
            'avg_revenue_per_product': f"${(total_revenue / len(sorted_products)) if sorted_products else 0:.2f}"
        }
        
        return self.report_data
    
    # ========== REPORTE COMPARATIVO TEMPORAL ==========
    
    def comparative_report(self, comparison_period='previous_month'):
        """
        Reporte comparativo entre dos períodos.
        Calcula variaciones porcentuales y tendencias.
        """
        self.report_data['title'] = 'Reporte Comparativo de Ventas'
        
        # Obtener períodos
        current_start, current_end = self._get_current_period()
        previous_start, previous_end = self._get_comparison_period(comparison_period)
        
        self.report_data['subtitle'] = (
            f"Actual: {current_start.strftime('%d/%m/%Y')} - {current_end.strftime('%d/%m/%Y')} | "
            f"Anterior: {previous_start.strftime('%d/%m/%Y')} - {previous_end.strftime('%d/%m/%Y')}"
        )
        
        self.report_data['headers'] = [
            'Métrica', 'Período Actual', 'Período Anterior', 'Variación', '% Cambio', 'Tendencia'
        ]
        
        # Órdenes de ambos períodos
        current_orders = Order.objects.filter(
            status='COMPLETED',
            updated_at__gte=current_start,
            updated_at__lte=current_end
        )
        
        previous_orders = Order.objects.filter(
            status='COMPLETED',
            updated_at__gte=previous_start,
            updated_at__lte=previous_end
        )
        
        # Calcular métricas
        metrics = [
            ('Número de Ventas', current_orders.count(), previous_orders.count()),
            ('Ingresos Totales', 
             current_orders.aggregate(total=Sum('total_price'))['total'] or 0,
             previous_orders.aggregate(total=Sum('total_price'))['total'] or 0),
            ('Ticket Promedio',
             (current_orders.aggregate(avg=Avg('total_price'))['avg'] or 0),
             (previous_orders.aggregate(avg=Avg('total_price'))['avg'] or 0)),
            ('Clientes Únicos',
             current_orders.values('customer').distinct().count(),
             previous_orders.values('customer').distinct().count()),
        ]
        
        # Construir filas
        for metric_name, current_value, previous_value in metrics:
            # Calcular variación
            if isinstance(current_value, (int, Decimal, float)) and isinstance(previous_value, (int, Decimal, float)):
                variation = float(current_value) - float(previous_value)
                percentage = (variation / float(previous_value) * 100) if previous_value != 0 else 0
                
                # Determinar tendencia
                if percentage > 5:
                    trend = '📈 Crecimiento'
                elif percentage < -5:
                    trend = '📉 Decrecimiento'
                else:
                    trend = '➡️ Estable'
                
                # Formatear valores
                if 'Ingresos' in metric_name or 'Ticket' in metric_name:
                    current_formatted = f"${current_value:.2f}"
                    previous_formatted = f"${previous_value:.2f}"
                    variation_formatted = f"${variation:.2f}"
                else:
                    current_formatted = str(int(current_value))
                    previous_formatted = str(int(previous_value))
                    variation_formatted = f"{int(variation):+d}"
                
                self.report_data['rows'].append([
                    metric_name,
                    current_formatted,
                    previous_formatted,
                    variation_formatted,
                    f"{percentage:+.1f}%",
                    trend
                ])
        
        # Alertas basadas en tendencias
        for row in self.report_data['rows']:
            if '📉 Decrecimiento' in row[5] and abs(float(row[4].replace('%', '').replace('+', ''))) > 20:
                self.report_data['alerts'].append(
                    f"🚨 Alerta: {row[0]} ha disminuido un {row[4]}"
                )
        
        return self.report_data
    
    # ========== DASHBOARD EJECUTIVO ==========
    
    def executive_dashboard(self):
        """
        Dashboard ejecutivo con KPIs principales y alertas.
        """
        self.report_data['title'] = 'Dashboard Ejecutivo'
        self.report_data['subtitle'] = self._get_date_range_text()
        
        orders = self._get_base_orders()
        
        # KPIs Principales
        total_orders = orders.count()
        total_revenue = orders.aggregate(total=Sum('total_price'))['total'] or Decimal('0')
        avg_ticket = orders.aggregate(avg=Avg('total_price'))['avg'] or Decimal('0')
        unique_customers = orders.values('customer').distinct().count()
        
        # Productos más vendidos (Top 5)
        top_products = OrderItem.objects.filter(order__in=orders) \
            .values('product__name') \
            .annotate(total_qty=Sum('quantity'), total_revenue=Sum(F('price') * F('quantity'))) \
            .order_by('-total_revenue')[:5]
        
        # Clientes top (Top 5)
        top_customers = orders.values(
            'customer__username', 'customer__email'
        ).annotate(
            total_spent=Sum('total_price'),
            num_orders=Count('id')
        ).order_by('-total_spent')[:5]
        
        # Categorías top (Top 3)
        top_categories = OrderItem.objects.filter(order__in=orders) \
            .values('product__category__name') \
            .annotate(total_revenue=Sum(F('price') * F('quantity'))) \
            .order_by('-total_revenue')[:3]
        
        # Productos con bajo stock (alerta)
        low_stock_products = Product.objects.filter(stock__lt=10, stock__gt=0)
        out_of_stock = Product.objects.filter(stock=0)
        
        # Clientes inactivos (sin compras en 90+ días)
        ninety_days_ago = timezone.now() - timedelta(days=90)
        active_customer_ids = Order.objects.filter(
            status='COMPLETED',
            updated_at__gte=ninety_days_ago
        ).values_list('customer_id', flat=True).distinct()
        
        all_customers = User.objects.filter(profile__role='CLIENT').count()
        inactive_customers = all_customers - len(set(active_customer_ids))
        
        # Construir KPIs
        self.report_data['kpis'] = {
            'total_ventas': total_orders,
            'ingresos_totales': f"${total_revenue:.2f}",
            'ticket_promedio': f"${avg_ticket:.2f}",
            'clientes_unicos': unique_customers,
            'productos_bajo_stock': low_stock_products.count(),
            'productos_agotados': out_of_stock.count(),
            'clientes_inactivos': inactive_customers
        }
        
        # Top 5 Productos
        self.report_data['top_products'] = [
            {
                'name': p['product__name'],
                'quantity': p['total_qty'],
                'revenue': f"${p['total_revenue']:.2f}"
            }
            for p in top_products
        ]
        
        # Top 5 Clientes
        self.report_data['top_customers'] = [
            {
                'username': c['customer__username'],
                'email': c['customer__email'],
                'total_spent': f"${c['total_spent']:.2f}",
                'orders': c['num_orders']
            }
            for c in top_customers
        ]
        
        # Top 3 Categorías
        self.report_data['top_categories'] = [
            {
                'name': c['product__category__name'],
                'revenue': f"${c['total_revenue']:.2f}"
            }
            for c in top_categories
        ]
        
        # Alertas
        if low_stock_products.count() > 0:
            self.report_data['alerts'].append(
                f"⚠️ {low_stock_products.count()} productos con stock bajo (< 10 unidades)"
            )
        if out_of_stock.count() > 0:
            self.report_data['alerts'].append(
                f"🚨 {out_of_stock.count()} productos AGOTADOS"
            )
        if inactive_customers > all_customers * 0.3:
            self.report_data['alerts'].append(
                f"📊 Alto porcentaje de clientes inactivos ({inactive_customers}/{all_customers})"
            )
        
        # Headers para tabla resumen
        self.report_data['headers'] = ['Métrica', 'Valor']
        self.report_data['rows'] = [
            ['Total de Ventas', str(total_orders)],
            ['Ingresos Totales', f"${total_revenue:.2f}"],
            ['Ticket Promedio', f"${avg_ticket:.2f}"],
            ['Clientes Únicos', str(unique_customers)],
            ['Productos Bajo Stock', str(low_stock_products.count())],
            ['Productos Agotados', str(out_of_stock.count())],
            ['Clientes Inactivos (90+ días)', str(inactive_customers)]
        ]
        
        return self.report_data
    
    # ========== INVENTARIO INTELIGENTE ==========
    
    def inventory_analysis(self):
        """
        Análisis inteligente de inventario con rotación y alertas.
        """
        self.report_data['title'] = 'Análisis de Inventario'
        self.report_data['subtitle'] = 'Estado Actual del Inventario'
        self.report_data['headers'] = [
            'Producto', 'Categoría', 'Stock Actual', 'Precio', 
            'Valor Inventario', 'Unidades Vendidas', 'Rotación', 'Estado'
        ]
        
        # Rango de fechas para calcular rotación (últimos 30 días)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_orders = Order.objects.filter(
            status='COMPLETED',
            updated_at__gte=thirty_days_ago
        )
        
        products = Product.objects.select_related('category').all()
        
        for product in products:
            # Calcular unidades vendidas en los últimos 30 días
            units_sold = OrderItem.objects.filter(
                order__in=recent_orders,
                product=product
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            # Valor en inventario
            inventory_value = product.price * product.stock
            
            # Rotación (ventas mensuales / stock actual)
            if product.stock > 0:
                rotation_rate = units_sold / product.stock
            else:
                rotation_rate = 0 if units_sold == 0 else 999  # Agotado pero con ventas
            
            # Determinar estado
            if product.stock == 0:
                status = '🚨 AGOTADO'
            elif product.stock < 10:
                status = '⚠️ BAJO'
            elif units_sold == 0:
                status = '😴 SIN VENTAS'
            elif rotation_rate > 2:
                status = '🔥 ALTA ROTACIÓN'
            elif rotation_rate > 0.5:
                status = '✅ NORMAL'
            else:
                status = '🐌 BAJA ROTACIÓN'
            
            self.report_data['rows'].append([
                product.name,
                product.category.name,
                product.stock,
                f"${product.price:.2f}",
                f"${inventory_value:.2f}",
                units_sold,
                f"{rotation_rate:.2f}x",
                status
            ])
        
        # Calcular totales
        total_value = sum(p.price * p.stock for p in products)
        total_products = products.count()
        products_low_stock = sum(1 for p in products if p.stock < 10)
        products_out_of_stock = sum(1 for p in products if p.stock == 0)
        products_no_sales = sum(1 for row in self.report_data['rows'] if row[5] == 0)
        
        self.report_data['totals'] = {
            'total_products': total_products,
            'total_inventory_value': f"${total_value:.2f}",
            'products_low_stock': products_low_stock,
            'products_out_of_stock': products_out_of_stock,
            'products_no_sales_30d': products_no_sales
        }
        
        # Alertas
        if products_out_of_stock > 0:
            self.report_data['alerts'].append(
                f"🚨 {products_out_of_stock} productos completamente agotados"
            )
        if products_low_stock > total_products * 0.2:
            self.report_data['alerts'].append(
                f"⚠️ {products_low_stock} productos con stock bajo (20% del inventario)"
            )
        if products_no_sales > total_products * 0.3:
            self.report_data['alerts'].append(
                f"📊 {products_no_sales} productos sin ventas en 30 días (30% del inventario)"
            )
        
        return self.report_data
    
    # ========== MÉTODOS AUXILIARES ==========
    
    def _get_base_orders(self):
        """Obtiene el queryset base de órdenes filtrado por fechas."""
        queryset = Order.objects.filter(status='COMPLETED')
        
        if self.params.get('start_date'):
            queryset = queryset.filter(updated_at__gte=self.params['start_date'])
        
        if self.params.get('end_date'):
            queryset = queryset.filter(updated_at__lte=self.params['end_date'])
        
        return queryset
    
    def _get_date_range_text(self):
        """Genera texto descriptivo del rango de fechas."""
        if self.params.get('start_date') and self.params.get('end_date'):
            start = self.params['start_date'].strftime('%d/%m/%Y')
            end = self.params['end_date'].strftime('%d/%m/%Y')
            return f"Período: {start} - {end}"
        return "Todas las fechas"
    
    def _get_current_period(self):
        """Retorna el período actual (start, end)."""
        if self.params.get('start_date') and self.params.get('end_date'):
            return self.params['start_date'], self.params['end_date']
        
        # Por defecto: mes actual
        now = timezone.now()
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now
    
    def _get_comparison_period(self, comparison_type):
        """Calcula el período de comparación."""
        current_start, current_end = self._get_current_period()
        duration = current_end - current_start
        
        if comparison_type == 'previous_month':
            # Mes anterior
            if current_start.month == 1:
                prev_start = current_start.replace(year=current_start.year - 1, month=12)
            else:
                prev_start = current_start.replace(month=current_start.month - 1)
            
            prev_end = current_start - timedelta(seconds=1)
            return prev_start, prev_end
        
        elif comparison_type == 'previous_period':
            # Período anterior del mismo tamaño
            prev_end = current_start - timedelta(seconds=1)
            prev_start = prev_end - duration
            return prev_start, prev_end
        
        else:
            # Por defecto: período anterior
            return current_start - duration, current_start - timedelta(seconds=1)
