"""
Views para el sistema de recomendaciones de productos.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from sales.ml_recommender import recommender


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_recommendations(request):
    """
    Obtiene recomendaciones personalizadas para el usuario actual.
    
    GET /api/orders/ml/recommendations/
    
    Query params:
    - limit: Número de recomendaciones (default: 10, max: 50)
    - exclude_purchased: Excluir productos ya comprados (default: true)
    
    Returns:
        Recomendaciones personalizadas con scores y razones
    
    Ejemplo:
        GET /api/orders/ml/recommendations/?limit=20
    """
    try:
        # Obtener parámetros
        limit = int(request.query_params.get('limit', 10))
        exclude_purchased = request.query_params.get('exclude_purchased', 'true').lower() == 'true'
        
        # Validar límite
        if limit < 1 or limit > 50:
            return Response({
                'success': False,
                'error': 'El parámetro "limit" debe estar entre 1 y 50'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener recomendaciones
        recommendations = recommender.get_recommendations_for_user(
            user_id=request.user.id,
            n_recommendations=limit,
            exclude_purchased=exclude_purchased
        )
        
        return Response({
            'success': True,
            'data': recommendations
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_recommendations_for_user_id(request, user_id):
    """
    Obtiene recomendaciones para un usuario específico (solo admins).
    
    GET /api/orders/ml/recommendations/user/{user_id}/
    
    Query params:
    - limit: Número de recomendaciones (default: 10)
    
    Returns:
        Recomendaciones para el usuario especificado
    """
    # Verificar que sea admin o el mismo usuario
    if not request.user.is_staff and request.user.id != user_id:
        return Response({
            'success': False,
            'error': 'No tienes permiso para ver recomendaciones de otros usuarios'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        limit = int(request.query_params.get('limit', 10))
        
        recommendations = recommender.get_recommendations_for_user(
            user_id=user_id,
            n_recommendations=limit
        )
        
        return Response({
            'success': True,
            'data': recommendations
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


@api_view(['GET'])
@permission_classes([AllowAny])
def get_similar_products(request, product_id):
    """
    Obtiene productos similares a uno dado.
    Útil para "También te puede interesar" en la página de producto.
    
    GET /api/orders/ml/similar-products/{product_id}/
    
    Query params:
    - limit: Número de productos similares (default: 6, max: 20)
    
    Returns:
        Lista de productos similares
    
    Ejemplo:
        GET /api/orders/ml/similar-products/5/?limit=10
    """
    try:
        limit = int(request.query_params.get('limit', 6))
        
        if limit < 1 or limit > 20:
            return Response({
                'success': False,
                'error': 'El parámetro "limit" debe estar entre 1 y 20'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        similar_products = recommender.get_similar_products(
            product_id=product_id,
            n=limit
        )
        
        return Response({
            'success': True,
            'data': {
                'product_id': product_id,
                'similar_products': similar_products,
                'total': len(similar_products)
            }
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


@api_view(['GET'])
@permission_classes([AllowAny])
def get_trending_products(request):
    """
    Obtiene productos en tendencia (más vendidos recientemente).
    
    GET /api/orders/ml/trending/
    
    Query params:
    - limit: Número de productos (default: 10, max: 50)
    - category: ID de categoría para filtrar (opcional)
    
    Returns:
        Lista de productos en tendencia
    
    Ejemplo:
        GET /api/orders/ml/trending/?limit=20
        GET /api/orders/ml/trending/?category=1&limit=10
    """
    try:
        limit = int(request.query_params.get('limit', 10))
        category_id = request.query_params.get('category')
        
        if limit < 1 or limit > 50:
            return Response({
                'success': False,
                'error': 'El parámetro "limit" debe estar entre 1 y 50'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Si hay categoría específica
        if category_id:
            try:
                category_id = int(category_id)
                trending = recommender.get_trending_in_category(
                    category_id=category_id,
                    n=limit
                )
            except ValueError:
                return Response({
                    'success': False,
                    'error': 'ID de categoría inválido'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Trending general
            trending_data = recommender._get_trending_products(limit)
            
            # Obtener detalles de productos
            from products.models import Product
            product_ids = [pid for pid, _ in trending_data]
            products = Product.objects.filter(id__in=product_ids).select_related('category')
            
            trending = []
            for product in products:
                score = next((s for pid, s in trending_data if pid == product.id), 0)
                trending.append({
                    'id': product.id,
                    'name': product.name,
                    'price': float(product.price),
                    'category': product.category.name if product.category else None,
                    'image': product.image.url if product.image else None,
                    'stock': product.stock,
                    'trend_score': round(score, 3)
                })
        
        return Response({
            'success': True,
            'data': {
                'trending_products': trending,
                'total': len(trending),
                'period': 'Últimos 30 días'
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_frequently_bought_together(request, product_id):
    """
    Obtiene productos frecuentemente comprados junto con uno dado.
    Útil para "Los clientes que compraron esto también compraron..."
    
    GET /api/orders/ml/bought-together/{product_id}/
    
    Query params:
    - limit: Número de productos (default: 5, max: 20)
    
    Returns:
        Lista de productos frecuentemente comprados juntos
    """
    try:
        limit = int(request.query_params.get('limit', 5))
        
        if limit < 1 or limit > 20:
            return Response({
                'success': False,
                'error': 'El parámetro "limit" debe estar entre 1 y 20'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener productos comprados juntos
        from sales.models import Order, OrderItem
        from products.models import Product
        from django.db.models import Count
        
        # Encontrar órdenes que contienen este producto
        orders_with_product = Order.objects.filter(
            status='COMPLETED',
            items__product_id=product_id
        ).distinct()
        
        # Contar qué otros productos aparecen en esas órdenes
        related_products = OrderItem.objects.filter(
            order__in=orders_with_product
        ).exclude(
            product_id=product_id
        ).values('product_id').annotate(
            frequency=Count('id')
        ).order_by('-frequency')[:limit]
        
        # Obtener detalles
        product_ids = [item['product_id'] for item in related_products]
        products = Product.objects.filter(id__in=product_ids).select_related('category')
        
        result = []
        for product in products:
            frequency = next((item['frequency'] for item in related_products if item['product_id'] == product.id), 0)
            result.append({
                'id': product.id,
                'name': product.name,
                'price': float(product.price),
                'category': product.category.name if product.category else None,
                'image': product.image.url if product.image else None,
                'stock': product.stock,
                'frequency': frequency,
                'reason': f'Comprado {frequency} veces junto con este producto'
            })
        
        return Response({
            'success': True,
            'data': {
                'product_id': product_id,
                'frequently_bought_together': result,
                'total': len(result)
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
