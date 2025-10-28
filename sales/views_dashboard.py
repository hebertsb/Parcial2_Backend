# sales/views_dashboard.py
"""
Vistas para el dashboard en tiempo real
"""

from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from api.permissions import IsAdminUser
from .analytics import DashboardAnalytics
from django.core.cache import cache


class RealTimeDashboardView(views.APIView):
    """
    GET /api/orders/dashboard/realtime/
    
    Dashboard en tiempo real con estadísticas actualizadas.
    Los datos se cachean por 5 minutos para mejorar el rendimiento.
    """
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """Obtiene estadísticas en tiempo real"""
        
        # Intentar obtener del cache primero
        cache_key = 'dashboard_realtime_stats'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            cached_data['from_cache'] = True
            return Response(cached_data)
        
        try:
            # Generar estadísticas frescas
            stats = DashboardAnalytics.get_real_time_stats()
            stats['from_cache'] = False
            
            # Cachear por 5 minutos
            cache.set(cache_key, stats, 300)
            
            return Response(stats, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'error': f'Error al generar estadísticas: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductPerformanceView(views.APIView):
    """
    GET /api/orders/dashboard/products/
    GET /api/orders/dashboard/products/{product_id}/
    
    Análisis de rendimiento de productos
    """
    permission_classes = [IsAdminUser]
    
    def get(self, request, product_id=None):
        """Obtiene análisis de rendimiento de productos"""
        
        try:
            performance = DashboardAnalytics.get_product_performance(product_id)
            
            return Response({
                'count': len(performance),
                'products': performance
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CustomerInsightsView(views.APIView):
    """
    GET /api/orders/dashboard/customers/
    GET /api/orders/dashboard/customers/{customer_id}/
    
    Análisis de comportamiento de clientes
    """
    permission_classes = [IsAdminUser]
    
    def get(self, request, customer_id=None):
        """Obtiene insights de clientes"""
        
        try:
            insights = DashboardAnalytics.get_customer_insights(customer_id)
            
            return Response({
                'count': len(insights),
                'customers': insights
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InvalidateCacheView(views.APIView):
    """
    POST /api/orders/dashboard/invalidate-cache/
    
    Invalida el cache del dashboard para forzar actualización
    """
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        """Invalida el cache"""
        
        cache.delete('dashboard_realtime_stats')
        
        return Response({
            'message': 'Cache invalidado exitosamente'
        }, status=status.HTTP_200_OK)
