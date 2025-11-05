"""
Views optimizadas para Dashboard de Predicciones de Ventas.
Diseñadas específicamente para consumo del frontend con gráficas estadísticas.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from api.permissions import IsAdminUser
from django.core.cache import cache
from django.utils import timezone
from django_ratelimit.decorators import ratelimit

from sales.ml_predictor_simple import SimpleSalesPredictor
from sales.ml_model_manager import get_predictor
from sales.ml_product_predictor import product_predictor


@ratelimit(key='user', rate='20/m', method='GET')
@api_view(['GET'])
@permission_classes([IsAdminUser])
def sales_predictions_dashboard(request):
    """
    Dashboard principal de predicciones de ventas para el frontend.

    GET /api/orders/dashboard/sales-predictions/

    Retorna predicciones de ventas totales para 7, 14, 30 y 90 días
    con datos estructurados para gráficas de líneas y estadísticas.

    Query params:
    - include_historical: Incluir datos históricos para comparación (default: true)
    - chart_format: Formato optimizado para gráficas (default: true)

    Returns:
        {
            "success": true,
            "data": {
                "predictions_7d": {...},
                "predictions_14d": {...},
                "predictions_30d": {...},
                "predictions_90d": {...},
                "historical_data": {...},
                "summary": {...}
            }
        }

    Ejemplo de uso para gráficas:
        - Gráfico de líneas: data.predictions_7d.daily_predictions[]
        - Estadísticas: data.predictions_7d.summary
        - Comparación histórica: data.historical_data
    """
    try:
        include_historical = request.query_params.get('include_historical', 'true').lower() == 'true'
        chart_format = request.query_params.get('chart_format', 'true').lower() == 'true'

        # Verificar caché
        cache_key = f'sales_dashboard:historical_{include_historical}:chart_{chart_format}'
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response({
                'success': True,
                'data': cached_data,
                'cached': True,
                'cache_expires_in_seconds': cache.ttl(cache_key)
            })

        # Obtener predictor entrenado
        try:
            predictor = get_predictor()
        except ValueError as e:
            return Response({
                'success': False,
                'error': 'No hay modelo entrenado',
                'message': str(e),
                'action_required': 'Entrena un modelo usando POST /api/orders/ml/train/'
            }, status=status.HTTP_424_FAILED_DEPENDENCY)

        # Generar predicciones para cada período
        periods = [7, 14, 30, 90]
        predictions_by_period = {}

        for days in periods:
            pred = predictor.predict(days=days)

            # Formatear para gráficas si se solicita
            if chart_format:
                predictions_by_period[f'predictions_{days}d'] = {
                    'period_days': days,
                    'period_label': _get_period_label(days),

                    # Datos para gráfico de líneas
                    'daily_predictions': [
                        {
                            'date': p['date'],
                            'value': p['predicted_sales'],
                            'lower_bound': p.get('lower_bound'),
                            'upper_bound': p.get('upper_bound')
                        }
                        for p in pred['predictions']
                    ],

                    # Resumen estadístico
                    'summary': {
                        'total_sales': pred['summary']['total_predicted_sales'],
                        'average_daily': pred['summary']['average_daily_sales'],
                        'growth_rate': pred['summary']['growth_rate_percent'],
                        'confidence_level': 0.95,

                        # Fechas del período
                        'start_date': pred['summary']['prediction_start'],
                        'end_date': pred['summary']['prediction_end'],

                        # Comparación histórica
                        'historical_average': pred['summary']['historical_average'],
                        'difference_vs_historical': round(
                            pred['summary']['average_daily_sales'] - pred['summary']['historical_average'], 2
                        )
                    },

                    # Información del modelo
                    'model_info': {
                        'r2_score': pred['model_info']['r2_score'],
                        'training_days': pred['model_info']['training_samples'],
                        'last_trained': pred['model_info']['last_trained']
                    }
                }
            else:
                # Formato original completo
                predictions_by_period[f'predictions_{days}d'] = pred

        # Datos históricos para comparación
        historical_data = None
        if include_historical:
            historical_data = _get_historical_sales_data(predictor, days=90)

        # Resumen general del dashboard
        dashboard_summary = {
            'next_week_forecast': predictions_by_period['predictions_7d']['summary']['total_sales'],
            'next_month_forecast': predictions_by_period['predictions_30d']['summary']['total_sales'],
            'next_quarter_forecast': predictions_by_period['predictions_90d']['summary']['total_sales'],

            'overall_trend': _calculate_overall_trend(predictions_by_period),

            'best_period': max(
                [(k, v['summary']['growth_rate']) for k, v in predictions_by_period.items()],
                key=lambda x: x[1]
            )[0].replace('predictions_', '').replace('d', ' días'),

            'model_accuracy': predictions_by_period['predictions_30d']['model_info']['r2_score'],

            'generated_at': timezone.now().isoformat()
        }

        # Estructura de respuesta optimizada
        response_data = {
            **predictions_by_period,
            'historical_data': historical_data,
            'summary': dashboard_summary
        }

        # Guardar en caché (30 minutos)
        cache.set(cache_key, response_data, 1800)

        return Response({
            'success': True,
            'data': response_data,
            'cached': False,

            # Guía para el frontend
            'chart_guide': {
                'line_chart': {
                    'title': 'Predicción de Ventas por Período',
                    'description': 'Gráfico de líneas mostrando ventas predichas día a día',
                    'data_source': 'data.predictions_XXd.daily_predictions[]',
                    'x_axis': 'date',
                    'y_axis': 'value (en dólares)',
                    'additional_series': [
                        'lower_bound y upper_bound para área de confianza',
                        'historical_data para comparar con histórico'
                    ]
                },
                'bar_chart': {
                    'title': 'Comparación de Períodos',
                    'description': 'Gráfico de barras comparando totales por período',
                    'data': [
                        {'period': '7 días', 'value': 'data.predictions_7d.summary.total_sales'},
                        {'period': '14 días', 'value': 'data.predictions_14d.summary.total_sales'},
                        {'period': '30 días', 'value': 'data.predictions_30d.summary.total_sales'},
                        {'period': '90 días', 'value': 'data.predictions_90d.summary.total_sales'}
                    ]
                },
                'stats_cards': {
                    'next_week': 'data.summary.next_week_forecast',
                    'next_month': 'data.summary.next_month_forecast',
                    'next_quarter': 'data.summary.next_quarter_forecast',
                    'trend': 'data.summary.overall_trend (growing/stable/declining)'
                },
                'colors': {
                    '7d': '#3B82F6',   # Blue
                    '14d': '#8B5CF6',  # Purple
                    '30d': '#10B981',  # Green
                    '90d': '#F59E0B',  # Orange
                    'historical': '#6B7280'  # Gray
                }
            }
        })

    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@ratelimit(key='user', rate='20/m', method='GET')
@api_view(['GET'])
@permission_classes([IsAdminUser])
def top_products_predictions_dashboard(request):
    """
    Dashboard de productos más vendidos predichos para el frontend.

    GET /api/orders/dashboard/top-products-predictions/

    Retorna ranking de productos que se predice venderán más en
    7, 14, 30 y 90 días, optimizado para gráficas de barras y tablas.

    Query params:
    - limit: Número de productos por período (default: 10, max: 20)
    - category: Filtrar por categoría ID (opcional)
    - chart_format: Formato optimizado para gráficas (default: true)

    Returns:
        {
            "success": true,
            "data": {
                "top_products_7d": [...],
                "top_products_14d": [...],
                "top_products_30d": [...],
                "top_products_90d": [...],
                "summary": {...}
            }
        }

    Ejemplo de uso:
        - Tabla de ranking: data.top_products_30d.products[]
        - Gráfico de barras: data.top_products_30d.chart_data[]
        - Comparación temporal: data.consistency_analysis
    """
    try:
        limit = int(request.query_params.get('limit', 10))
        category_id = request.query_params.get('category')
        chart_format = request.query_params.get('chart_format', 'true').lower() == 'true'

        # Validar límite
        if limit < 1 or limit > 20:
            return Response({
                'success': False,
                'error': 'El parámetro "limit" debe estar entre 1 y 20'
            }, status=status.HTTP_400_BAD_REQUEST)

        category_id = int(category_id) if category_id else None

        # Verificar caché
        cache_key = f'top_products_dashboard:limit_{limit}:cat_{category_id}:chart_{chart_format}'
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response({
                'success': True,
                'data': cached_data,
                'cached': True
            })

        # Generar predicciones para cada período
        periods = [7, 14, 30, 90]
        top_products_by_period = {}
        all_products_across_periods = {}  # Para análisis de consistencia

        for days in periods:
            forecast = product_predictor.get_top_products_forecast(
                days=days,
                limit=limit,
                category_id=category_id
            )

            if chart_format:
                # Formato optimizado para gráficas
                products_data = []
                chart_data = []

                for product in forecast['top_products']:
                    product_id = product['product_id']

                    # Rastrear productos entre períodos
                    if product_id not in all_products_across_periods:
                        all_products_across_periods[product_id] = {
                            'name': product['product_name'],
                            'appearances': [],
                            'avg_rank': 0
                        }

                    all_products_across_periods[product_id]['appearances'].append({
                        'period': days,
                        'rank': product['rank'],
                        'predicted_sales': product['predicted_sales']
                    })

                    # Datos para tabla
                    products_data.append({
                        'rank': product['rank'],
                        'product_id': product_id,
                        'product_name': product['product_name'],
                        'category': product['category'],
                        'predicted_sales': product['predicted_sales'],
                        'predicted_revenue': product['predicted_revenue'],
                        'daily_average': product['predicted_daily_sales'],
                        'growth_rate': product['growth_rate'],
                        'current_stock': product['current_stock'],
                        'stock_status': product['stock_status'],

                        # Indicadores visuales
                        'trend_icon': '📈' if product['growth_rate'] > 0 else '📉',
                        'stock_icon': _get_stock_icon(product['stock_status']),
                        'growth_color': '#10B981' if product['growth_rate'] > 0 else '#EF4444'
                    })

                    # Datos para gráfico de barras
                    chart_data.append({
                        'product_name': product['product_name'],
                        'value': product['predicted_sales'],
                        'color': _get_rank_color(product['rank'])
                    })

                top_products_by_period[f'top_products_{days}d'] = {
                    'period_days': days,
                    'period_label': _get_period_label(days),
                    'total_products': len(products_data),

                    # Datos para tabla de ranking
                    'products': products_data,

                    # Datos para gráfico de barras horizontal
                    'chart_data': chart_data,

                    # Resumen del período
                    'period_summary': {
                        'total_predicted_sales': sum(p['predicted_sales'] for p in products_data),
                        'total_predicted_revenue': sum(p['predicted_revenue'] for p in products_data),
                        'average_growth_rate': sum(p['growth_rate'] for p in products_data) / len(products_data) if products_data else 0,
                        'products_with_low_stock': sum(1 for p in products_data if p['stock_status'] in ['CRITICAL', 'WARNING'])
                    }
                }
            else:
                # Formato original
                top_products_by_period[f'top_products_{days}d'] = forecast

        # Análisis de consistencia entre períodos
        consistency_analysis = _analyze_product_consistency(all_products_across_periods, limit)

        # Resumen general
        dashboard_summary = {
            'most_consistent_products': consistency_analysis['most_consistent'][:5],
            'rising_stars': consistency_analysis['rising_stars'][:5],
            'total_unique_products': len(all_products_across_periods),
            'category_filter': category_id,
            'generated_at': timezone.now().isoformat()
        }

        # Respuesta completa
        response_data = {
            **top_products_by_period,
            'consistency_analysis': consistency_analysis,
            'summary': dashboard_summary
        }

        # Guardar en caché (30 minutos)
        cache.set(cache_key, response_data, 1800)

        return Response({
            'success': True,
            'data': response_data,
            'cached': False,

            # Guía para el frontend
            'chart_guide': {
                'horizontal_bar_chart': {
                    'title': 'Top Productos por Período',
                    'description': 'Gráfico de barras horizontal mostrando ranking',
                    'data_source': 'data.top_products_XXd.chart_data[]',
                    'x_axis': 'value (unidades predichas)',
                    'y_axis': 'product_name',
                    'colors': 'Usar campo "color" de cada producto'
                },
                'comparison_table': {
                    'title': 'Comparación de Períodos',
                    'description': 'Tabla mostrando productos consistentes',
                    'data_source': 'data.consistency_analysis.most_consistent[]',
                    'columns': ['product_name', 'appearances_count', 'average_rank']
                },
                'period_selector': {
                    'options': [
                        {'value': '7d', 'label': 'Próxima Semana'},
                        {'value': '14d', 'label': 'Próximas 2 Semanas'},
                        {'value': '30d', 'label': 'Próximo Mes'},
                        {'value': '90d', 'label': 'Próximos 3 Meses'}
                    ],
                    'default': '30d'
                },
                'badges': {
                    'stock_status': {
                        'CRITICAL': {'color': '#DC2626', 'label': 'Stock Crítico'},
                        'WARNING': {'color': '#F59E0B', 'label': 'Stock Bajo'},
                        'CAUTION': {'color': '#FBBF24', 'label': 'Monitorear'},
                        'OK': {'color': '#10B981', 'label': 'Stock OK'}
                    },
                    'growth': {
                        'positive': {'color': '#10B981', 'icon': '↗'},
                        'negative': {'color': '#EF4444', 'icon': '↘'}
                    }
                }
            }
        })

    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@ratelimit(key='user', rate='30/m', method='GET')
@api_view(['GET'])
@permission_classes([IsAdminUser])
def combined_predictions_dashboard(request):
    """
    Dashboard combinado: Ventas totales + Productos más vendidos.

    GET /api/orders/dashboard/predictions-combined/

    Endpoint TODO-EN-UNO que retorna tanto predicciones de ventas
    totales como productos más vendidos para 7, 14, 30 y 90 días.

    Query params:
    - products_limit: Número de productos por período (default: 5)
    - include_historical: Incluir datos históricos (default: false para velocidad)

    Returns:
        {
            "success": true,
            "data": {
                "sales_predictions": {...},  // Del endpoint sales_predictions_dashboard
                "top_products": {...},       // Del endpoint top_products_predictions_dashboard
                "overview": {...}             // Resumen ejecutivo
            }
        }

    Úsalo cuando:
        - Necesitas cargar todo el dashboard de predicciones de una vez
        - Quieres minimizar número de peticiones HTTP
        - Renderizas vista completa de predicciones
    """
    try:
        products_limit = int(request.query_params.get('products_limit', 5))
        include_historical = request.query_params.get('include_historical', 'false').lower() == 'true'

        # Verificar caché
        cache_key = f'combined_dashboard:limit_{products_limit}:hist_{include_historical}'
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response({
                'success': True,
                'data': cached_data,
                'cached': True
            })

        # Obtener predictor
        try:
            predictor = get_predictor()
        except ValueError as e:
            return Response({
                'success': False,
                'error': 'No hay modelo entrenado',
                'message': str(e),
                'action_required': 'POST /api/orders/ml/train/'
            }, status=status.HTTP_424_FAILED_DEPENDENCY)

        # 1. Predicciones de ventas totales
        periods = [7, 14, 30, 90]
        sales_predictions = {}

        for days in periods:
            pred = predictor.predict(days=days)
            sales_predictions[f'{days}d'] = {
                'period_days': days,
                'period_label': _get_period_label(days),
                'total_sales': pred['summary']['total_predicted_sales'],
                'average_daily': pred['summary']['average_daily_sales'],
                'growth_rate': pred['summary']['growth_rate_percent'],
                'start_date': pred['summary']['prediction_start'],
                'end_date': pred['summary']['prediction_end'],

                # Datos para gráfico de líneas (simplificado)
                'daily_chart': [
                    {'date': p['date'], 'value': p['predicted_sales']}
                    for p in pred['predictions']
                ]
            }

        # 2. Top productos por período
        top_products = {}

        for days in periods:
            forecast = product_predictor.get_top_products_forecast(
                days=days,
                limit=products_limit
            )

            top_products[f'{days}d'] = {
                'period_days': days,
                'period_label': _get_period_label(days),
                'products': [
                    {
                        'rank': p['rank'],
                        'name': p['product_name'],
                        'predicted_sales': p['predicted_sales'],
                        'growth_rate': p['growth_rate']
                    }
                    for p in forecast['top_products']
                ]
            }

        # 3. Resumen ejecutivo
        overview = {
            'next_week': {
                'total_sales': sales_predictions['7d']['total_sales'],
                'top_product': top_products['7d']['products'][0] if top_products['7d']['products'] else None
            },
            'next_month': {
                'total_sales': sales_predictions['30d']['total_sales'],
                'top_product': top_products['30d']['products'][0] if top_products['30d']['products'] else None
            },
            'next_quarter': {
                'total_sales': sales_predictions['90d']['total_sales'],
                'top_product': top_products['90d']['products'][0] if top_products['90d']['products'] else None
            },
            'overall_growth_trend': sales_predictions['30d']['growth_rate'],
            'model_last_trained': predictor.last_trained.isoformat() if predictor.last_trained else None,
            'generated_at': timezone.now().isoformat()
        }

        # Datos históricos (opcional)
        historical_data = None
        if include_historical:
            historical_data = _get_historical_sales_data(predictor, days=30)

        response_data = {
            'sales_predictions': sales_predictions,
            'top_products': top_products,
            'overview': overview,
            'historical_data': historical_data
        }

        # Guardar en caché (30 minutos)
        cache.set(cache_key, response_data, 1800)

        return Response({
            'success': True,
            'data': response_data,
            'cached': False,
            'performance_tip': 'Este endpoint combina múltiples predicciones. Para mejor rendimiento, usa endpoints específicos si solo necesitas una parte.'
        })

    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== FUNCIONES AUXILIARES =====

def _get_period_label(days: int) -> str:
    """Retorna etiqueta legible para el período."""
    labels = {
        7: 'Próxima Semana',
        14: 'Próximas 2 Semanas',
        30: 'Próximo Mes',
        60: 'Próximos 2 Meses',
        90: 'Próximos 3 Meses'
    }
    return labels.get(days, f'Próximos {days} días')


def _get_stock_icon(stock_status: str) -> str:
    """Retorna icono para estado de stock."""
    icons = {
        'CRITICAL': '🔴',
        'WARNING': '⚠️',
        'CAUTION': '⚡',
        'OK': '✅'
    }
    return icons.get(stock_status, '❓')


def _get_rank_color(rank: int) -> str:
    """Retorna color basado en ranking."""
    if rank == 1:
        return '#FFD700'  # Gold
    elif rank == 2:
        return '#C0C0C0'  # Silver
    elif rank == 3:
        return '#CD7F32'  # Bronze
    else:
        return '#3B82F6'  # Blue


def _calculate_overall_trend(predictions_by_period: dict) -> str:
    """Calcula tendencia general de ventas."""
    growth_rates = [
        p['summary']['growth_rate']
        for p in predictions_by_period.values()
    ]
    avg_growth = sum(growth_rates) / len(growth_rates)

    if avg_growth > 5:
        return 'growing'
    elif avg_growth < -5:
        return 'declining'
    else:
        return 'stable'


def _get_historical_sales_data(predictor, days: int = 90) -> dict:
    """Obtiene datos históricos para comparación."""
    if predictor.training_data is None:
        return None

    # Tomar últimos N días
    historical_df = predictor.training_data.tail(days)

    return {
        'period_days': days,
        'daily_data': [
            {
                'date': row['date'].strftime('%Y-%m-%d'),
                'value': float(row['sales'])
            }
            for _, row in historical_df.iterrows()
        ],
        'summary': {
            'total_sales': float(historical_df['sales'].sum()),
            'average_daily': float(historical_df['sales'].mean()),
            'min_daily': float(historical_df['sales'].min()),
            'max_daily': float(historical_df['sales'].max())
        }
    }


def _analyze_product_consistency(all_products: dict, limit: int) -> dict:
    """Analiza consistencia de productos entre períodos."""
    consistency_scores = []
    rising_stars = []

    for product_id, data in all_products.items():
        appearances = data['appearances']
        num_appearances = len(appearances)

        if num_appearances == 0:
            continue

        avg_rank = sum(a['rank'] for a in appearances) / num_appearances

        consistency_scores.append({
            'product_id': product_id,
            'product_name': data['name'],
            'appearances_count': num_appearances,
            'average_rank': round(avg_rank, 1),
            'periods': [a['period'] for a in appearances]
        })

        # Detectar "rising stars" (mejora en ranking)
        if num_appearances >= 2:
            ranks = [a['rank'] for a in sorted(appearances, key=lambda x: x['period'])]
            if ranks[-1] < ranks[0]:  # Ranking mejoró (número menor)
                rank_improvement = ranks[0] - ranks[-1]
                rising_stars.append({
                    'product_id': product_id,
                    'product_name': data['name'],
                    'rank_improvement': rank_improvement,
                    'latest_rank': ranks[-1]
                })

    # Ordenar por consistencia
    consistency_scores.sort(key=lambda x: (-x['appearances_count'], x['average_rank']))
    rising_stars.sort(key=lambda x: -x['rank_improvement'])

    return {
        'most_consistent': consistency_scores[:limit],
        'rising_stars': rising_stars[:limit],
        'total_products_analyzed': len(all_products)
    }
