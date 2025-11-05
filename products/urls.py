from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, BrandViewSet, WarrantyViewSet, OfferViewSet

# Importar vistas de recomendaciones desde sales app
from sales.views_recommendations import (
    get_user_recommendations, 
    get_similar_products,
    get_trending_products,
    get_frequently_bought_together
)

# Creamos un router que generará las URLs automáticamente
router = DefaultRouter()
router.register(r'warranties', WarrantyViewSet, basename='warranty')
router.register(r'brands', BrandViewSet, basename='brand')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'offers', OfferViewSet, basename='offer')

urlpatterns = [
    path('', include(router.urls)),
    
    # ========================================
    # 🔗 ALIAS PARA COMPATIBILIDAD CON FRONTEND
    # ========================================
    # El frontend está llamando a estas URLs bajo /api/products/ml/
    # pero las vistas están en sales app bajo /api/sales/ml/
    # Estas rutas actúan como aliases para mantener compatibilidad
    
    # Recomendaciones personalizadas para el usuario actual
    # Frontend: GET /api/products/ml/recommendations/personalized/?limit=8
    # Backend real: /api/sales/ml/recommendations/
    path('ml/recommendations/personalized/', get_user_recommendations, name='products-recommendations-personalized'),
    
    # Productos similares a uno específico
    # Frontend: GET /api/products/ml/recommendations/similar/<id>/?limit=6
    # Backend real: /api/sales/ml/similar-products/<id>/
    path('ml/recommendations/similar/<int:product_id>/', get_similar_products, name='products-recommendations-similar'),
    
    # Productos en tendencia
    # Frontend: GET /api/products/ml/recommendations/trending/?limit=10
    # Backend real: /api/sales/ml/trending/
    path('ml/recommendations/trending/', get_trending_products, name='products-recommendations-trending'),
    
    # Productos frecuentemente comprados juntos
    # Frontend: GET /api/products/ml/recommendations/bought-together/<id>/?limit=5
    # Backend real: /api/sales/ml/bought-together/<id>/
    path('ml/recommendations/bought-together/<int:product_id>/', get_frequently_bought_together, name='products-recommendations-bought-together'),
]