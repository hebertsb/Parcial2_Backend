"""
Sistema de recomendaciones de productos usando Machine Learning.
Implementa múltiples estrategias de recomendación.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from collections import defaultdict, Counter
from datetime import datetime, timedelta

from django.db.models import Count, Sum, Q, F, Avg
from django.utils import timezone
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from sales.models import Order, OrderItem
from products.models import Product
from django.contrib.auth import get_user_model

User = get_user_model()


class ProductRecommender:
    """
    Sistema de recomendaciones de productos que combina múltiples estrategias.
    """
    
    def __init__(self):
        self.user_item_matrix = None
        self.product_similarity_matrix = None
        self.scaler = StandardScaler()
        
    def get_recommendations_for_user(
        self, 
        user_id: int, 
        n_recommendations: int = 10,
        exclude_purchased: bool = True
    ) -> Dict[str, Any]:
        """
        Obtiene recomendaciones personalizadas para un usuario.
        
        Args:
            user_id: ID del usuario
            n_recommendations: Número de recomendaciones a retornar
            exclude_purchased: Si True, excluye productos ya comprados
            
        Returns:
            Dict con recomendaciones y metadatos
        """
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValueError(f"Usuario {user_id} no encontrado")
        
        # Obtener diferentes tipos de recomendaciones
        collaborative = self._collaborative_filtering(user_id, n_recommendations)
        content_based = self._content_based_filtering(user_id, n_recommendations)
        trending = self._get_trending_products(n_recommendations)
        frequently_bought_together = self._frequently_bought_together(user_id, n_recommendations)
        
        # Productos ya comprados por el usuario
        purchased_products = set()
        if exclude_purchased:
            purchased_products = set(
                OrderItem.objects.filter(
                    order__customer_id=user_id,
                    order__status='COMPLETED'
                ).values_list('product_id', flat=True)
            )
        
        # Combinar recomendaciones con scores ponderados
        combined_scores = defaultdict(float)
        
        # Pesos para cada estrategia
        weights = {
            'collaborative': 0.35,
            'content_based': 0.25,
            'trending': 0.20,
            'frequently_bought': 0.20
        }
        
        for product_id, score in collaborative:
            if product_id not in purchased_products:
                combined_scores[product_id] += score * weights['collaborative']
        
        for product_id, score in content_based:
            if product_id not in purchased_products:
                combined_scores[product_id] += score * weights['content_based']
        
        for product_id, score in trending:
            if product_id not in purchased_products:
                combined_scores[product_id] += score * weights['trending']
        
        for product_id, score in frequently_bought_together:
            if product_id not in purchased_products:
                combined_scores[product_id] += score * weights['frequently_bought']
        
        # Ordenar por score
        sorted_recommendations = sorted(
            combined_scores.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:n_recommendations]
        
        # Obtener detalles de productos
        recommended_products = []
        for product_id, score in sorted_recommendations:
            try:
                product = Product.objects.select_related('category').get(id=product_id)
                recommended_products.append({
                    'id': product.id,
                    'name': product.name,
                    'price': float(product.price),
                    'category': product.category.name if product.category else None,
                    'image': product.image.url if product.image else None,
                    'stock': product.stock,
                    'recommendation_score': round(score, 3),
                    'reason': self._get_recommendation_reason(user_id, product_id)
                })
            except Product.DoesNotExist:
                continue
        
        return {
            'user_id': user_id,
            'recommendations': recommended_products,
            'total_recommendations': len(recommended_products),
            'strategies_used': list(weights.keys()),
            'generated_at': timezone.now().isoformat()
        }
    
    def _collaborative_filtering(self, user_id: int, n: int) -> List[tuple]:
        """
        Filtrado colaborativo: recomendaciones basadas en usuarios similares.
        "Usuarios que compraron como tú también compraron..."
        """
        # Obtener productos que ha comprado este usuario
        user_products = set(
            OrderItem.objects.filter(
                order__customer_id=user_id,
                order__status='COMPLETED'
            ).values_list('product_id', flat=True)
        )
        
        if not user_products:
            return []
        
        # Encontrar usuarios que compraron productos similares
        similar_users = OrderItem.objects.filter(
            order__status='COMPLETED',
            product_id__in=user_products
        ).exclude(
            order__customer_id=user_id
        ).values('order__customer_id').annotate(
            common_products=Count('product_id', distinct=True)
        ).order_by('-common_products')[:20]
        
        similar_user_ids = [u['order__customer_id'] for u in similar_users]
        
        # Obtener productos que compraron esos usuarios similares
        recommended_products = OrderItem.objects.filter(
            order__customer_id__in=similar_user_ids,
            order__status='COMPLETED'
        ).exclude(
            product_id__in=user_products
        ).values('product_id').annotate(
            purchase_count=Count('id'),
            total_revenue=Sum(F('price') * F('quantity'))
        ).order_by('-purchase_count')[:n]
        
        # Normalizar scores entre 0 y 1
        max_count = recommended_products[0]['purchase_count'] if recommended_products else 1
        
        return [
            (item['product_id'], item['purchase_count'] / max_count)
            for item in recommended_products
        ]
    
    def _content_based_filtering(self, user_id: int, n: int) -> List[tuple]:
        """
        Filtrado basado en contenido: productos similares a los que ha comprado.
        "Basado en tus compras anteriores..."
        """
        # Obtener categorías que ha comprado el usuario
        user_categories = OrderItem.objects.filter(
            order__customer_id=user_id,
            order__status='COMPLETED'
        ).values_list('product__category_id', flat=True).distinct()
        
        if not user_categories:
            return []
        
        # Obtener productos comprados
        purchased_products = set(
            OrderItem.objects.filter(
                order__customer_id=user_id,
                order__status='COMPLETED'
            ).values_list('product_id', flat=True)
        )
        
        # Encontrar productos de las mismas categorías
        similar_products = Product.objects.filter(
            category_id__in=user_categories,
            stock__gt=0
        ).exclude(
            id__in=purchased_products
        ).annotate(
            popularity=Count('order_items', filter=Q(order_items__order__status='COMPLETED'))
        ).order_by('-popularity')[:n]
        
        # Normalizar scores
        max_popularity = similar_products[0].popularity if similar_products else 1
        
        return [
            (product.id, product.popularity / max_popularity if max_popularity > 0 else 0.5)
            for product in similar_products
        ]
    
    def _get_trending_products(self, n: int) -> List[tuple]:
        """
        Productos en tendencia (más vendidos recientemente).
        """
        # Últimos 30 días
        since_date = timezone.now() - timedelta(days=30)
        
        trending = Product.objects.filter(
            stock__gt=0,
            order_items__order__status='COMPLETED',
            order_items__order__created_at__gte=since_date
        ).annotate(
            recent_sales=Count('order_items'),
            recent_revenue=Sum(F('order_items__price') * F('order_items__quantity'))
        ).order_by('-recent_sales')[:n]
        
        # Normalizar
        max_sales = trending[0].recent_sales if trending else 1
        
        return [
            (product.id, product.recent_sales / max_sales)
            for product in trending
        ]
    
    def _frequently_bought_together(self, user_id: int, n: int) -> List[tuple]:
        """
        Productos frecuentemente comprados juntos.
        "Los clientes que compraron X también compraron Y"
        """
        # Obtener productos que ha comprado este usuario
        user_products = list(
            OrderItem.objects.filter(
                order__customer_id=user_id,
                order__status='COMPLETED'
            ).values_list('product_id', flat=True).distinct()
        )
        
        if not user_products:
            return []
        
        # Encontrar órdenes que contienen esos productos
        orders_with_user_products = Order.objects.filter(
            status='COMPLETED',
            items__product_id__in=user_products
        ).distinct()
        
        # Contar qué otros productos aparecen en esas órdenes
        related_products = OrderItem.objects.filter(
            order__in=orders_with_user_products
        ).exclude(
            product_id__in=user_products
        ).values('product_id').annotate(
            co_occurrence=Count('id')
        ).order_by('-co_occurrence')[:n]
        
        # Normalizar
        max_occurrence = related_products[0]['co_occurrence'] if related_products else 1
        
        return [
            (item['product_id'], item['co_occurrence'] / max_occurrence)
            for item in related_products
        ]
    
    def _get_recommendation_reason(self, user_id: int, product_id: int) -> str:
        """
        Genera una explicación de por qué se recomienda este producto.
        """
        try:
            product = Product.objects.select_related('category').get(id=product_id)
            
            # Verificar si el usuario compró de la misma categoría
            user_has_category = OrderItem.objects.filter(
                order__customer_id=user_id,
                order__status='COMPLETED',
                product__category=product.category
            ).exists()
            
            if user_has_category:
                return f"Basado en tus compras de {product.category.name}"
            
            # Verificar si es trending
            since_date = timezone.now() - timedelta(days=30)
            recent_sales = OrderItem.objects.filter(
                product_id=product_id,
                order__status='COMPLETED',
                order__created_at__gte=since_date
            ).count()
            
            if recent_sales > 10:
                return "Producto popular este mes"
            
            return "Recomendado para ti"
            
        except Product.DoesNotExist:
            return "Recomendación personalizada"
    
    def get_similar_products(self, product_id: int, n: int = 6) -> List[Dict[str, Any]]:
        """
        Obtiene productos similares a uno dado.
        Útil para "También te puede interesar" en páginas de producto.
        
        Args:
            product_id: ID del producto de referencia
            n: Número de productos similares a retornar
            
        Returns:
            Lista de productos similares
        """
        try:
            product = Product.objects.select_related('category').get(id=product_id)
        except Product.DoesNotExist:
            raise ValueError(f"Producto {product_id} no encontrado")
        
        # Estrategia 1: Misma categoría
        similar_by_category = Product.objects.filter(
            category=product.category,
            stock__gt=0
        ).exclude(
            id=product_id
        ).annotate(
            popularity=Count('order_items', filter=Q(order_items__order__status='COMPLETED'))
        ).order_by('-popularity')[:n]
        
        # Estrategia 2: Productos comprados juntos
        bought_together = OrderItem.objects.filter(
            order__items__product_id=product_id,
            order__status='COMPLETED'
        ).exclude(
            product_id=product_id
        ).values('product_id').annotate(
            frequency=Count('id')
        ).order_by('-frequency')[:n]
        
        bought_together_ids = [item['product_id'] for item in bought_together]
        
        # Combinar resultados
        similar_products_ids = list(similar_by_category.values_list('id', flat=True))
        similar_products_ids.extend([pid for pid in bought_together_ids if pid not in similar_products_ids])
        
        # Limitar a n productos
        similar_products_ids = similar_products_ids[:n]
        
        # Obtener detalles
        products = Product.objects.filter(
            id__in=similar_products_ids
        ).select_related('category')
        
        result = []
        for p in products:
            result.append({
                'id': p.id,
                'name': p.name,
                'price': float(p.price),
                'category': p.category.name if p.category else None,
                'image': p.image.url if p.image else None,
                'stock': p.stock,
                'reason': 'Frecuentemente comprados juntos' if p.id in bought_together_ids else 'De la misma categoría'
            })
        
        return result
    
    def get_trending_in_category(self, category_id: int, n: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene productos en tendencia de una categoría específica.
        
        Args:
            category_id: ID de la categoría
            n: Número de productos a retornar
            
        Returns:
            Lista de productos en tendencia
        """
        since_date = timezone.now() - timedelta(days=30)
        
        trending = Product.objects.filter(
            category_id=category_id,
            stock__gt=0,
            order_items__order__status='COMPLETED',
            order_items__order__created_at__gte=since_date
        ).annotate(
            recent_sales=Count('order_items'),
            recent_revenue=Sum(F('order_items__price') * F('order_items__quantity'))
        ).order_by('-recent_sales')[:n]
        
        result = []
        for product in trending:
            result.append({
                'id': product.id,
                'name': product.name,
                'price': float(product.price),
                'image': product.image.url if product.image else None,
                'stock': product.stock,
                'recent_sales': product.recent_sales,
                'recent_revenue': float(product.recent_revenue or 0),
                'trend_score': product.recent_sales  # Simplificado
            })
        
        return result


# Instancia singleton del recomendador
recommender = ProductRecommender()
