"""
Core de reportes para la tienda (moneda única: Bs).

Provee utilidades para:
- Métricas y series para gráficas de dashboard
- Construcción de datos tabulares para exportar ventas, clientes y productos

Nota: se filtra por órdenes con estado COMPLETED.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

from django.db.models import Sum, Count, Avg, Max, F
from django.utils import timezone

from .models import Order, OrderItem
from products.models import Product
from django.contrib.auth.models import User


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d')
    except Exception:
        return None


def _get_period(fecha_inicio: str | None, fecha_fin: str | None) -> Tuple[datetime, datetime]:
    start_dt = _parse_date(fecha_inicio)
    end_dt = _parse_date(fecha_fin)
    if not end_dt:
        end_dt = timezone.now()
    if not start_dt:
        start_dt = end_dt - timedelta(days=365)
    # normalizar a fechas sin tiempo para consistencia
    start_dt = datetime(year=start_dt.year, month=start_dt.month, day=start_dt.day)
    end_dt = datetime(year=end_dt.year, month=end_dt.month, day=end_dt.day, hour=23, minute=59, second=59)
    return start_dt, end_dt


def obtener_metricas_y_series(filtros: Dict[str, Any]) -> Dict[str, Any]:
    """Genera métricas y series para dashboards (Bs, sin departamentos)."""
    fecha_inicio = filtros.get('fecha_inicio')
    fecha_fin = filtros.get('fecha_fin')
    start_dt, end_dt = _get_period(fecha_inicio, fecha_fin)

    # Filtrar órdenes completadas en el periodo
    orders = Order.objects.filter(
        status=Order.OrderStatus.COMPLETED,
        created_at__gte=start_dt,
        created_at__lte=end_dt,
    )

    items = OrderItem.objects.filter(order__in=orders).select_related('product', 'order')

    # Métricas principales
    agg_orders = orders.aggregate(
        total_ventas=Sum('total_price'),
        total_ordenes=Count('id'),
        promedio_orden=Avg('total_price'),
        total_clientes=Count('customer', distinct=True),
    )

    total_ventas = float(agg_orders.get('total_ventas') or 0)
    total_ordenes = int(agg_orders.get('total_ordenes') or 0)
    promedio_orden = float(agg_orders.get('promedio_orden') or 0)
    total_clientes = int(agg_orders.get('total_clientes') or 0)

    # Ventas por mes
    ventas_mes = (
        orders
        .values('created_at__year', 'created_at__month')
        .annotate(total=Sum('total_price'), cantidad=Count('id'))
        .order_by('created_at__year', 'created_at__month')
    )
    meses_nombres = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
        7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }
    ventas_por_mes: List[Dict[str, Any]] = []
    ventas_mes_list = list(ventas_mes)
    for i, item in enumerate(ventas_mes_list):
        year = item['created_at__year']
        month = item['created_at__month']
        total = float(item['total'] or 0)
        cantidad = int(item['cantidad'] or 0)
        crecimiento = 0.0
        if i > 0:
            total_anterior = float(ventas_mes_list[i - 1]['total'] or 0)
            if total_anterior > 0:
                crecimiento = ((total - total_anterior) / total_anterior) * 100.0
        ventas_por_mes.append({
            'mes': f"{year}-{month:02d}",
            'mes_nombre': f"{meses_nombres.get(month, str(month))} {year}",
            'total': round(total, 2),
            'cantidad': cantidad,
            'crecimiento': round(crecimiento, 2),
        })

    # Productos más vendidos (top 10 por ingresos)
    prod_agg = (
        items
        .values('product_id', 'product__name')
        .annotate(
            cantidad_vendida=Sum('quantity'),
            total_ventas=Sum(F('quantity') * F('price')),
            precio_promedio=Avg('price'),
        )
        .order_by('-total_ventas')[:10]
    )
    productos_mas_vendidos = [
        {
            'id': p['product_id'],
            'nombre': p['product__name'],
            'total_ventas': float(p['total_ventas'] or 0),
            'cantidad_vendida': int(p['cantidad_vendida'] or 0),
            'promedio': float(p['precio_promedio'] or 0),
        }
        for p in prod_agg
    ]

    # Tipos de cliente por número de órdenes en el periodo
    customers = (
        User.objects
        .filter(orders__in=orders)
        .annotate(num_orders=Count('orders'))
        .values('id', 'username', 'num_orders')
    )
    nuevos = sum(1 for c in customers if c['num_orders'] == 1)
    recurrentes = sum(1 for c in customers if 2 <= (c['num_orders'] or 0) <= 5)
    vip = sum(1 for c in customers if (c['num_orders'] or 0) >= 6)
    total_clasificados = max(nuevos + recurrentes + vip, 1)
    tipos_cliente = [
        {'tipo': 'nuevo', 'cantidad': nuevos, 'porcentaje': round(nuevos / total_clasificados * 100, 2)},
        {'tipo': 'recurrente', 'cantidad': recurrentes, 'porcentaje': round(recurrentes / total_clasificados * 100, 2)},
        {'tipo': 'vip', 'cantidad': vip, 'porcentaje': round(vip / total_clasificados * 100, 2)},
    ]

    return {
        'success': True,
        'moneda': 'Bs',
        'periodo': {
            'fecha_inicio': start_dt.strftime('%Y-%m-%d'),
            'fecha_fin': end_dt.strftime('%Y-%m-%d'),
        },
        'metricas': {
            'total_ventas': round(total_ventas, 2),
            'total_ordenes': total_ordenes,
            'promedio_orden': round(promedio_orden, 2),
            'total_clientes': total_clientes,
        },
        'ventas_por_mes': ventas_por_mes,
        'productos_mas_vendidos': productos_mas_vendidos,
        'tipos_cliente': tipos_cliente,
        'tendencia_mensual': ventas_por_mes,
    }


def construir_datos_ventas(filtros: Dict[str, Any]) -> Tuple[List[str], List[List[Any]], Dict[str, Any]]:
    """Construye datos tabulares de ventas desde OrderItem."""
    start_dt, end_dt = _get_period(filtros.get('fecha_inicio'), filtros.get('fecha_fin'))
    items = (
        OrderItem.objects
        .select_related('order', 'product', 'order__customer')
        .filter(order__status=Order.OrderStatus.COMPLETED,
                order__created_at__gte=start_dt,
                order__created_at__lte=end_dt)
        .order_by('-order__created_at')
    )
    headers = ['Fecha', 'Cliente', 'Producto', 'Cantidad', 'Precio (Bs)', 'Total (Bs)']
    rows: List[List[Any]] = []
    total_general = 0.0
    for it in items:
        total = float(it.quantity * it.price)
        total_general += total
        rows.append([
            it.order.created_at.strftime('%d/%m/%Y'),
            getattr(it.order.customer, 'username', 'N/A'),
            it.product.name,
            int(it.quantity),
            f"Bs {float(it.price):.2f}",
            f"Bs {total:.2f}",
        ])
    totals = {'total_general': f"Bs {total_general:.2f}", 'registros': len(rows)}
    return headers, rows, totals


def construir_datos_clientes(filtros: Dict[str, Any]) -> Tuple[List[str], List[List[Any]], Dict[str, Any]]:
    """Resumen por cliente (número de órdenes completadas y total gastado)."""
    start_dt, end_dt = _get_period(filtros.get('fecha_inicio'), filtros.get('fecha_fin'))
    orders = Order.objects.filter(status=Order.OrderStatus.COMPLETED,
                                  created_at__gte=start_dt, created_at__lte=end_dt).select_related('customer')
    by_user: Dict[int, Dict[str, Any]] = {}
    for o in orders:
        if not o.customer:
            continue
        uid = o.customer.pk
        if uid not in by_user:
            by_user[uid] = {
                'username': o.customer.username,
                'num_ordenes': 0,
                'total_gastado': 0.0,
                'ultima_compra': o.created_at,
            }
        udata = by_user[uid]
        udata['num_ordenes'] += 1
        udata['total_gastado'] += float(o.total_price or 0)
        if o.created_at and o.created_at > udata['ultima_compra']:
            udata['ultima_compra'] = o.created_at

    headers = ['Cliente', 'Órdenes', 'Total Gastado (Bs)', 'Última Compra']
    rows: List[List[Any]] = []
    total_gastado = 0.0
    for data in by_user.values():
        total_gastado += data['total_gastado']
        rows.append([
            data['username'],
            data['num_ordenes'],
            f"Bs {data['total_gastado']:.2f}",
            data['ultima_compra'].strftime('%d/%m/%Y') if data['ultima_compra'] else 'N/A',
        ])
    totals = {'total_gastado': f"Bs {total_gastado:.2f}", 'clientes': len(rows)}
    return headers, rows, totals


def construir_datos_productos(filtros: Dict[str, Any]) -> Tuple[List[str], List[List[Any]], Dict[str, Any]]:
    start_dt, end_dt = _get_period(filtros.get('fecha_inicio'), filtros.get('fecha_fin'))
    items = (
        OrderItem.objects
        .select_related('product')
        .filter(order__status=Order.OrderStatus.COMPLETED,
                order__created_at__gte=start_dt,
                order__created_at__lte=end_dt)
    )
    agg = (
        items.values('product_id', 'product__name')
        .annotate(
            cantidad=Sum('quantity'),
            ingresos=Sum(F('quantity') * F('price')),
            precio_promedio=Avg('price'),
            ultima_venta=Max('order__created_at'),
        )
        .order_by('-ingresos')
    )
    headers = ['Producto', 'Cantidad', 'Ingresos (Bs)', 'Precio Promedio (Bs)', 'Última Venta']
    rows: List[List[Any]] = []
    total_ingresos = 0.0
    for a in agg:
        ingresos = float(a['ingresos'] or 0)
        total_ingresos += ingresos
        rows.append([
            a['product__name'],
            int(a['cantidad'] or 0),
            f"Bs {ingresos:.2f}",
            f"Bs {float(a['precio_promedio'] or 0):.2f}",
            a['ultima_venta'].strftime('%d/%m/%Y') if a['ultima_venta'] else 'N/A',
        ])
    totals = {'total_ingresos': f"Bs {total_ingresos:.2f}", 'productos': len(rows)}
    return headers, rows, totals
