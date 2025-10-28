"""
Views para predicciones avanzadas de ventas con filtros.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from api.permissions import IsAdminUser
from django.core.cache import cache
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
import hashlib
import json

from sales.ml_product_predictor import product_predictor


def _get_cache_key(prefix: str, **kwargs) -> str:
    """Genera una clave de caché única basada en parámetros."""
    params_str = json.dumps(kwargs, sort_keys=True)
    params_hash = hashlib.md5(params_str.encode()).hexdigest()
    return f"{prefix}:{params_hash}"


def _generate_stock_alert_message(alert_level: str, days_until_stockout: int, product_name: str) -> str:
    """
    Genera un mensaje descriptivo para la alerta de stock.
    
    Args:
        alert_level: Nivel de alerta (CRITICAL, WARNING, CAUTION, OK)
        days_until_stockout: Días hasta quedarse sin stock
        product_name: Nombre del producto
        
    Returns:
        Mensaje descriptivo de la alerta
    """
    if days_until_stockout is None:
        return f"Estado de stock desconocido para {product_name}"
    
    messages = {
        'CRITICAL': f"🔴 Stock crítico - El producto '{product_name}' se agotará en {days_until_stockout} días. Reposición URGENTE requerida.",
        'WARNING': f"⚠️ Stock bajo - El producto '{product_name}' se agotará en {days_until_stockout} días. Planificar reposición pronto.",
        'CAUTION': f"⚡ Stock moderado - El producto '{product_name}' se agotará en {days_until_stockout} días. Monitorear inventario.",
        'OK': f"✅ Stock suficiente para {product_name}."
    }
    
    return messages.get(alert_level, f"Estado de stock para {product_name}: {alert_level}")


@api_view(['GET'])
@permission_classes([IsAdminUser])
def predict_product_sales(request, product_id):
    """
    Predice ventas futuras de un producto específico.
    
    GET /api/orders/predictions/product/{product_id}/
    
    Query params:
    - days: Días a predecir (default: 30)
      Ejemplos: 7 (una semana), 14 (dos semanas), 30 (un mes), 90 (tres meses)
    - confidence: Incluir intervalos de confianza (default: true)
    
    Returns:
        Predicciones detalladas del producto con alertas de stock
    
    Ejemplos:
        GET /api/orders/predictions/product/5/?days=7    # Predicción de 1 semana
        GET /api/orders/predictions/product/5/?days=14   # Predicción de 2 semanas
        GET /api/orders/predictions/product/5/?days=30   # Predicción de 1 mes
        GET /api/orders/predictions/product/5/?days=90   # Predicción de 3 meses
    """
    try:
        days = int(request.query_params.get('days', 30))
        include_confidence = request.query_params.get('confidence', 'true').lower() == 'true'
        
        if days < 1 or days > 365:
            return Response({
                'success': False,
                'error': 'El parámetro "days" debe estar entre 1 y 365'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        prediction = product_predictor.predict_product_sales(
            product_id=product_id,
            days=days,
            include_confidence=include_confidence
        )
        
        if 'error' in prediction:
            return Response({
                'success': False,
                'data': prediction
            }, status=status.HTTP_200_OK)
        
        # Agregar metadata explicativa para frontend
        response_data = {
            'success': True,
            'data': prediction,
            'metadata': {
                'how_it_works': {
                    'title': 'Cómo funciona la predicción con IA',
                    'description': 'El sistema analiza los últimos 90 días de ventas del producto y usa Machine Learning (Regresión Lineal) para predecir ventas futuras.',
                    'factors_analyzed': [
                        'Tendencia histórica de ventas (si el producto está creciendo o decreciendo)',
                        'Día de la semana (algunos productos venden más en ciertos días)',
                        'Fin de semana vs días laborales',
                        'Estacionalidad y patrones de compra'
                    ],
                    'prediction_method': f'Se generan predicciones día por día para los próximos {days} días basándose en patrones históricos'
                },
                'how_to_interpret': {
                    'total_predicted_units': f'Número total de unidades que se espera vender en {days} días',
                    'average_daily_units': 'Promedio de unidades vendidas por día en el período',
                    'growth_vs_historical': 'Comparación del ritmo de ventas predicho vs. el histórico (positivo = crecimiento)',
                    'days_until_stockout': 'Días estimados hasta quedarse sin inventario al ritmo actual',
                    'alert_level': {
                        'CRITICAL': 'Rojo - Stock se agotará en menos del 30% del período',
                        'WARNING': 'Amarillo - Stock se agotará antes del 70% del período',
                        'CAUTION': 'Naranja - Stock justo para el período',
                        'OK': 'Verde - Stock suficiente'
                    }
                },
                'visualization_guide': {
                    'chart_type': 'Gráfico de líneas recomendado',
                    'x_axis': 'Fechas (predictions[].date)',
                    'y_axis': 'Unidades predichas (predictions[].predicted_units)',
                    'additional_series': [
                        'Línea de promedio histórico para comparar',
                        'Área de intervalo de confianza (si está disponible)',
                        'Marcador de fecha cuando se acabaría el stock'
                    ],
                    'color_coding': {
                        'prediction_line': 'Azul #2563EB',
                        'historical_avg': 'Gris #6B7280',
                        'stock_alert_zone': 'Rojo degradado cuando se acerca el stockout'
                    }
                },
                'usage_examples': {
                    'short_term': 'days=7 - Planificación semanal, ideal para reposición rápida',
                    'medium_term': 'days=30 - Planificación mensual, compras y presupuestos',
                    'long_term': 'days=90 - Estrategia trimestral, análisis de tendencias'
                },
                'important_notes': [
                    f'Los números cambian según el período: más días = más unidades totales',
                    'El promedio diario muestra el ritmo de ventas esperado',
                    'Productos nuevos (<7 días de historial) no tienen suficientes datos',
                    'La precisión mejora con más historial de ventas'
                ]
            }
        }
        
        return Response(response_data)
        
    except ValueError as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def predict_category_sales(request, category_id):
    """
    Predice ventas futuras de todos los productos de una categoría.
    
    GET /api/orders/predictions/category/{category_id}/
    
    Query params:
    - days: Días a predecir (default: 30)
    
    Returns:
        Predicciones agregadas de la categoría con ranking de productos
    
    Ejemplos:
        GET /api/orders/predictions/category/1/?days=7    # Categoría en 1 semana
        GET /api/orders/predictions/category/1/?days=30   # Categoría en 1 mes
    """
    try:
        days = int(request.query_params.get('days', 30))
        
        if days < 1 or days > 365:
            return Response({
                'success': False,
                'error': 'El parámetro "days" debe estar entre 1 y 365'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        prediction = product_predictor.predict_category_sales(
            category_id=category_id,
            days=days
        )
        
        if 'error' in prediction:
            return Response({
                'success': False,
                'data': prediction
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': True,
            'data': prediction
        })
        
    except ValueError as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def compare_products_predictions(request):
    """
    Compara predicciones de múltiples productos.
    
    POST /api/orders/predictions/compare/
    
    Body:
    {
        "product_ids": [1, 2, 3, 4, 5],
        "days": 30
    }
    
    Returns:
        Comparación lado a lado de productos con ranking
    
    Ejemplo:
        POST /api/orders/predictions/compare/
        {
            "product_ids": [1, 2, 3],
            "days": 14
        }
    """
    try:
        product_ids = request.data.get('product_ids', [])
        days = int(request.data.get('days', 30))
        
        if not product_ids:
            return Response({
                'success': False,
                'error': 'Se requiere el parámetro "product_ids" con al menos un ID'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(product_ids) > 20:
            return Response({
                'success': False,
                'error': 'Máximo 20 productos para comparar'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if days < 1 or days > 365:
            return Response({
                'success': False,
                'error': 'El parámetro "days" debe estar entre 1 y 365'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        comparison = product_predictor.compare_products(
            product_ids=product_ids,
            days=days
        )
        
        return Response({
            'success': True,
            'data': comparison
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@ratelimit(key='user', rate='10/m', method='GET')
@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_top_products_forecast(request):
    """
    Obtiene ranking de productos que se predice venderán más.
    
    GET /api/orders/predictions/top-products/
    
    Query params:
    - days: Días a predecir (default: 30)
    - limit: Número de productos (default: 10, max: 50)
    - category: ID de categoría para filtrar (opcional)
    
    Returns:
        Ranking de productos con mejores predicciones
    
    Ejemplos:
        GET /api/orders/predictions/top-products/?days=7&limit=20
        GET /api/orders/predictions/top-products/?days=30&category=1
    """
    try:
        days = int(request.query_params.get('days', 30))
        limit = int(request.query_params.get('limit', 10))
        category_id = request.query_params.get('category')
        
        if days < 1 or days > 365:
            return Response({
                'success': False,
                'error': 'El parámetro "days" debe estar entre 1 y 365'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if limit < 1 or limit > 50:
            return Response({
                'success': False,
                'error': 'El parámetro "limit" debe estar entre 1 y 50'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        category_id = int(category_id) if category_id else None
        
        # Intentar obtener del caché
        cache_key = _get_cache_key(
            'top_products',
            days=days,
            limit=limit,
            category_id=category_id
        )
        
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response({
                'success': True,
                'data': cached_data,
                'cached': True
            })
        
        # Si no está en caché, calcular
        forecast = product_predictor.get_top_products_forecast(
            days=days,
            limit=limit,
            category_id=category_id
        )
        
        # Guardar en caché (15 minutos)
        cache.set(cache_key, forecast, 900)
        
        return Response({
            'success': True,
            'data': forecast,
            'cached': False,
            'metadata': {
                'explanation': {
                    'title': 'Ranking de Productos Más Vendidos (Predicción IA)',
                    'description': f'Este ranking muestra los {limit} productos que la IA predice venderán más unidades en los próximos {days} días.',
                    'how_ranking_works': 'Los productos se ordenan por cantidad total de unidades predichas (predicted_units), no por ingresos.'
                },
                'what_changes_with_days': {
                    'days_7': 'Muestra productos para reposición inmediata (próxima semana)',
                    'days_14': 'Productos para planificación bisemanal',
                    'days_30': 'Productos estrella del próximo mes (ideal para compras)',
                    'days_90': 'Tendencias trimestrales y estrategia a largo plazo',
                    'important': f'A más días, mayores números totales. Compare "predicted_units" entre períodos para ver proporción.'
                },
                'visualization_guide': {
                    'recommended_charts': [
                        'Gráfico de barras horizontal (top productos)',
                        'Tabla con ranking y métricas clave',
                        'Badges de crecimiento (growth_percent)'
                    ],
                    'key_metrics_to_show': {
                        'rank': 'Posición en el ranking (#1, #2, etc)',
                        'predicted_units': f'Unidades totales en {days} días',
                        'predicted_revenue': f'Ingresos estimados en {days} días',
                        'growth_percent': 'Crecimiento vs histórico (verde si >0, rojo si <0)',
                        'current_stock': 'Inventario actual disponible'
                    },
                    'color_coding': {
                        'rank_1_to_3': 'Oro/Plata/Bronce (#FFD700, #C0C0C0, #CD7F32)',
                        'growth_positive': 'Verde #10B981',
                        'growth_negative': 'Rojo #EF4444',
                        'low_stock': 'Naranja #F59E0B si stock < predicted_units'
                    }
                },
                'frontend_tips': {
                    'display_format': 'Mostrar siempre el período (days) en el título',
                    'comparison': 'Permitir cambiar días para ver cómo cambia el ranking',
                    'highlight': 'Resaltar productos con stock bajo vs predicción',
                    'filters': 'Permitir filtrar por categoría para análisis específico'
                },
                'data_interpretation': [
                    f'Si predicted_units > current_stock: ALERTA - Necesita reposición',
                    'growth_percent positivo: Producto en tendencia alcista',
                    'growth_percent negativo: Producto perdiendo popularidad',
                    'El ranking puede cambiar entre períodos según estacionalidad'
                ]
            }
        })
        
    except ValueError as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@ratelimit(key='user', rate='10/m', method='GET')
@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_stock_alerts(request):
    """
    Obtiene alertas de productos con riesgo de quedarse sin stock.
    
    GET /api/orders/predictions/stock-alerts/
    
    Query params:
    - days: Período a analizar (default: 30)
    - alert_level: Filtrar por nivel (CRITICAL, WARNING, CAUTION, opcional)
    
    Returns:
        Lista de productos con alertas de stock ordenados por criticidad
    """
    try:
        days = int(request.query_params.get('days', 30))
        alert_level_filter = request.query_params.get('alert_level')
        
        # Intentar obtener del caché
        cache_key = _get_cache_key(
            'stock_alerts',
            days=days,
            alert_level=alert_level_filter
        )
        
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response({
                'success': True,
                'data': cached_data,
                'cached': True
            })
        
        # Obtener top products
        forecast = product_predictor.get_top_products_forecast(
            days=days,
            limit=50
        )
        
        # Generar alertas detalladas
        alerts = []
        for product_data in forecast['top_products']:
            try:
                prediction = product_predictor.predict_product_sales(
                    product_id=product_data['product_id'],
                    days=days,
                    include_confidence=False
                )
                
                if 'error' not in prediction:
                    stock_alert = prediction['stock_alert']
                    
                    # Filtrar por nivel si se especifica
                    if alert_level_filter and stock_alert['alert_level'] != alert_level_filter:
                        continue
                    
                    if stock_alert['days_until_stockout'] is not None and stock_alert['days_until_stockout'] < days:
                        # Generar mensaje descriptivo
                        message = _generate_stock_alert_message(
                            stock_alert['alert_level'],
                            stock_alert['days_until_stockout'],
                            product_data['product_name']
                        )
                        
                        alerts.append({
                            'product_id': product_data['product_id'],
                            'product_name': product_data['product_name'],
                            'category': product_data['category'],
                            'current_stock': prediction['product']['current_stock'],
                            'predicted_daily_sales': prediction['summary']['average_daily_units'],
                            'days_until_stockout': stock_alert['days_until_stockout'],
                            # Renombrar campos para consistencia
                            'restock_recommendation': stock_alert['restock_recommended'],
                            'alert_level': stock_alert['alert_level'],
                            'predicted_sales': prediction['summary']['total_predicted_units'],
                            # Agregar mensaje
                            'message': message
                        })
            except Exception:
                continue
        
        # Ordenar por criticidad
        priority_order = {'CRITICAL': 1, 'WARNING': 2, 'CAUTION': 3, 'OK': 4}
        alerts.sort(key=lambda x: (priority_order.get(x['alert_level'], 99), x['days_until_stockout']))
        
        # Preparar datos de respuesta
        response_data = {
            'alerts': alerts,
            'total_alerts': len(alerts),
            'critical_count': sum(1 for a in alerts if a['alert_level'] == 'CRITICAL'),
            'warning_count': sum(1 for a in alerts if a['alert_level'] == 'WARNING'),
            'caution_count': sum(1 for a in alerts if a['alert_level'] == 'CAUTION'),
            'analysis_period_days': days,
            'generated_at': forecast['generated_at']
        }
        
        # Guardar en caché (15 minutos)
        cache.set(cache_key, response_data, 900)
        
        return Response({
            'success': True,
            'data': response_data,
            'cached': False,
            'metadata': {
                'explanation': {
                    'title': 'Sistema de Alertas de Stock Inteligente',
                    'description': f'Identifica productos que se quedarán sin inventario en los próximos {days} días según predicciones de IA.',
                    'purpose': 'Prevenir quiebres de stock y optimizar reposiciones basándose en ventas predichas, no solo históricas.'
                },
                'alert_levels_explained': {
                    'CRITICAL': {
                        'color': '#DC2626',
                        'icon': '🔴',
                        'meaning': 'Stock se agotará en menos del 30% del período',
                        'action': 'URGENTE: Reponer inmediatamente',
                        'example': f'Si days={days}, se acabará en menos de {int(days*0.3)} días'
                    },
                    'WARNING': {
                        'color': '#F59E0B',
                        'icon': '⚠️',
                        'meaning': 'Stock se agotará entre 30% y 70% del período',
                        'action': 'Planificar reposición pronto',
                        'example': f'Se acabará entre {int(days*0.3)} y {int(days*0.7)} días'
                    },
                    'CAUTION': {
                        'color': '#FBBF24',
                        'icon': '⚡',
                        'meaning': 'Stock justo alcanza para el período',
                        'action': 'Monitorear y considerar reposición',
                        'example': f'Se acabará cerca del día {days}'
                    },
                    'OK': {
                        'color': '#10B981',
                        'icon': '✅',
                        'meaning': 'Stock suficiente para todo el período',
                        'action': 'Sin acción requerida',
                        'example': f'Stock dura más de {days} días'
                    }
                },
                'how_calculation_works': {
                    'step_1': 'IA predice ventas diarias futuras basándose en 90 días históricos',
                    'step_2': f'Suma total de unidades a vender en {days} días',
                    'step_3': 'Compara stock actual vs ventas predichas',
                    'step_4': 'Calcula: días_hasta_agotarse = stock_actual / promedio_ventas_diarias',
                    'step_5': 'Asigna nivel de alerta según criticidad'
                },
                'key_metrics_explained': {
                    'current_stock': 'Inventario disponible ahora mismo',
                    'predicted_daily_sales': 'Unidades que se venderán por día (promedio)',
                    'days_until_stockout': 'Días hasta quedarse sin stock al ritmo predicho',
                    'predicted_total_sales': f'Total de unidades a vender en {days} días',
                    'restock_recommended': 'Cantidad sugerida a reponer (+20% margen de seguridad)'
                },
                'visualization_guide': {
                    'recommended_layout': 'Lista ordenada por criticidad (CRITICAL primero)',
                    'card_design': [
                        'Badge de nivel de alerta con color correspondiente',
                        'Nombre del producto grande',
                        'Barra de progreso: stock actual vs predicted_total_sales',
                        'Días hasta stockout prominente',
                        'Cantidad recomendada a reponer'
                    ],
                    'color_scheme': {
                        'critical_bg': 'Fondo rojo suave #FEE2E2',
                        'warning_bg': 'Fondo naranja suave #FEF3C7',
                        'caution_bg': 'Fondo amarillo suave #FEF9C3',
                        'ok_bg': 'Fondo verde suave #D1FAE5'
                    },
                    'sorting': 'Ya viene ordenado: CRITICAL → WARNING → CAUTION, y por días (menos días primero)'
                },
                'how_days_parameter_affects': {
                    'days_7': 'Alertas para la próxima semana - Reposición urgente',
                    'days_14': 'Alertas quincenales - Planificación a corto plazo',
                    'days_30': 'Alertas mensuales - Compras regulares (recomendado)',
                    'days_90': 'Alertas trimestrales - Estrategia de largo plazo',
                    'important': f'Con days={days}, solo muestra productos que NO alcanzarán para los {days} días completos'
                },
                'frontend_implementation': {
                    'filters': 'Permitir filtrar por alert_level (query param)',
                    'notifications': 'Mostrar badge con critical_count en el menú',
                    'actions': [
                        'Botón "Crear Orden de Compra" con restock_recommended pre-llenado',
                        'Link directo al producto para ver más detalles',
                        'Opción de marcar alerta como "En proceso"'
                    ],
                    'refresh': 'Actualizar automáticamente cada hora o cuando cambie días'
                },
                'example_interpretation': {
                    'scenario': 'Producto X con current_stock=50, predicted_daily_sales=5, days=30',
                    'calculation': '50 unidades / 5 por día = 10 días hasta stockout',
                    'result': 'CRITICAL porque 10 < 30 (se acaba antes del período)',
                    'action': f'Reponer restock_recommended unidades URGENTE'
                }
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@ratelimit(key='user', rate='5/m', method='GET')
@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_multi_period_forecast(request):
    """
    Obtiene predicciones para múltiples períodos en una sola llamada.
    
    GET /api/sales/predictions/multi-period/
    
    Query params:
    - periods: Períodos separados por comas (default: "7,14,30,60,90")
    - limit: Número de productos por período (default: 5, max: 20)
    - category: ID de categoría para filtrar (opcional)
    
    Returns:
        Predicciones para cada período solicitado
    
    Ejemplos:
        GET /api/sales/predictions/multi-period/
        GET /api/sales/predictions/multi-period/?periods=7,14,30&limit=10
        GET /api/sales/predictions/multi-period/?periods=30,60,90&category=1
    """
    try:
        # Parsear parámetros
        periods_str = request.query_params.get('periods', '7,14,30,60,90')
        periods = [int(p.strip()) for p in periods_str.split(',')]
        limit = int(request.query_params.get('limit', 5))
        category_id = request.query_params.get('category')
        
        # Validar límite
        if limit < 1 or limit > 20:
            return Response({
                'success': False,
                'error': 'El parámetro "limit" debe estar entre 1 y 20'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validar número de períodos
        if len(periods) > 10:
            return Response({
                'success': False,
                'error': 'Máximo 10 períodos permitidos'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        category_id = int(category_id) if category_id else None
        
        # Obtener forecasts
        result = product_predictor.get_multi_period_forecast(
            periods=periods,
            limit=limit,
            category_id=category_id
        )
        
        return Response({
            'success': True,
            'data': result,
            'metadata': {
                'how_to_use': {
                    'description': 'Datos optimizados para gráficos de comparación temporal',
                    'keys': 'Cada key (ej: "7d", "30d") contiene el forecast completo para ese período',
                    'comparison': 'Compara "predicted_sales" entre períodos para ver tendencias'
                },
                'example_usage': {
                    'chart_data': 'Usar forecasts["7d"].top_products para período de 7 días',
                    'trend_analysis': 'Comparar predicted_sales entre diferentes períodos',
                    'growth_analysis': 'Usar growth_rate para ver aceleración/desaceleración'
                },
                'performance': {
                    'benefit': 'Una llamada en lugar de N llamadas separadas',
                    'speed': '5-10x más rápido que llamadas individuales',
                    'cache_friendly': 'Fácil de cachear en frontend por conjunto completo'
                }
            }
        })
        
    except ValueError as e:
        return Response({
            'success': False,
            'error': f'Error en parámetros: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def clear_ml_cache(request):
    """
    Limpia el caché de predicciones ML.
    
    POST /api/sales/predictions/clear-cache/
    
    Útil después de:
    - Agregar nuevas ventas
    - Modificar stock
    - Reentrenar modelos
    - Actualizar productos
    
    Returns:
        Confirmación de limpieza del caché
    """
    try:
        # Limpiar caché completo
        cache.clear()
        
        return Response({
            'success': True,
            'message': 'Caché de predicciones ML limpiado exitosamente',
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

