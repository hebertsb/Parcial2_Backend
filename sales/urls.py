from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CartView, CartItemView, StripeCheckoutView, StripeWebhookView, CompleteOrderView, 
    ManualOrderCompletionView, SalesHistoryView, SalesHistoryDetailView, GenerateOrderReceiptPDF, MyOrderListView,
    PaymentMethodViewSet # Importar el nuevo ViewSet
)
# ... (resto de importaciones)

# Router para endpoints de configuración
config_router = DefaultRouter()
config_router.register(r'payment-methods', PaymentMethodViewSet, basename='payment-method')

urlpatterns = [
    # ... (urlpatterns existentes) ...

    # === ⚙️ ENDPOINTS DE CONFIGURACIÓN (NUEVO) ===
    path('config/', include(config_router.urls)),
]
from .views_advanced_reports import (
    CustomerAnalysisReportView, ProductABCAnalysisView, ComparativeReportView,
    ExecutiveDashboardView, InventoryAnalysisView
)
from .views_dashboard import (
    RealTimeDashboardView, ProductPerformanceView, CustomerInsightsView,
    InvalidateCacheView
)
from .views_ml import (
    generate_demo_sales_data, train_model, get_predictions, get_forecast_components,
    get_model_performance, list_models, set_current_model, delete_model, ml_dashboard,
    check_retrain_status, auto_retrain
)
from .views_recommendations import (
    get_user_recommendations, get_recommendations_for_user_id, get_similar_products,
    get_trending_products, get_frequently_bought_together
)
from .views_product_predictions import (
    predict_product_sales, predict_category_sales, compare_products_predictions,
    get_top_products_forecast, get_stock_alerts, get_multi_period_forecast, clear_ml_cache
)
from .views_sales_predictions_dashboard import (
    sales_predictions_dashboard, top_products_predictions_dashboard, combined_predictions_dashboard
)
from .views_unified_reports import (
    UnifiedReportListView, UnifiedIntelligentReportView, test_intelligent_parser
)
from .views_audit import (
    AuditLogListView, AuditLogDetailView, AuditStatisticsView, UserActivityView,
    ActiveSessionsView, SessionHistoryView, clean_old_logs, security_alerts,
    check_current_session
)
from .views_audit_reports import (
    GenerateAuditReportView, GenerateSessionReportView
)

urlpatterns = [
    # URL para ver el carrito y añadir artículos
    path('cart/', CartView.as_view(), name='cart'),
    # URL para actualizar o eliminar un artículo específico por su ID
    path('cart/items/<int:item_id>/', CartItemView.as_view(), name='cart-item'),
    path('checkout/', StripeCheckoutView.as_view(), name='checkout'),
    path('complete-order/', CompleteOrderView.as_view(), name='complete-order'),
    path('stripe-webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
    path('sales-history/', SalesHistoryView.as_view(), name='sales-history'),
    path('sales-history/<int:pk>/', SalesHistoryDetailView.as_view(), name='sales-history-detail'),
    path('sales-history/<int:order_id>/receipt/', GenerateOrderReceiptPDF.as_view(), name='order-receipt'),
    path('my-orders/', MyOrderListView.as_view(), name='my-orders'),
    path('debug/complete-order/', ManualOrderCompletionView.as_view(), name='debug-complete-order'),
    
    # === 🚀 SISTEMA UNIFICADO DE REPORTES INTELIGENTES (NUEVO) ===
    path('reports/unified/list/', UnifiedReportListView.as_view(), name='unified-reports-list'),
    path('reports/unified/generate/', UnifiedIntelligentReportView.as_view(), name='unified-intelligent-report'),
    path('reports/unified/test/', test_intelligent_parser, name='test-intelligent-parser'),

    # === REPORTES DINÁMICOS ===
    # ❌ ELIMINADO: path('reports/generate/', GenerateDynamicReportView.as_view(), name='generate-report')
    # ✅ USAR: POST /api/sales/reports/unified/generate/ (Sistema Unificado Inteligente)
    # El sistema unificado soporta comandos en lenguaje natural, voz, y todos los formatos (JSON, PDF, Excel)

    # === REPORTES AVANZADOS ===
    path('reports/customer-analysis/', CustomerAnalysisReportView.as_view(), name='customer-analysis'),
    path('reports/product-abc/', ProductABCAnalysisView.as_view(), name='product-abc'),
    path('reports/comparative/', ComparativeReportView.as_view(), name='comparative-report'),
    path('reports/dashboard/', ExecutiveDashboardView.as_view(), name='executive-dashboard'),
    path('reports/inventory-analysis/', InventoryAnalysisView.as_view(), name='inventory-analysis'),
    
    # === DASHBOARD EN TIEMPO REAL ===
    path('dashboard/realtime/', RealTimeDashboardView.as_view(), name='realtime-dashboard'),
    path('dashboard/products/', ProductPerformanceView.as_view(), name='product-performance'),
    path('dashboard/products/<int:product_id>/', ProductPerformanceView.as_view(), name='product-performance-detail'),
    path('dashboard/customers/', CustomerInsightsView.as_view(), name='customer-insights'),
    path('dashboard/customers/<int:customer_id>/', CustomerInsightsView.as_view(), name='customer-insights-detail'),
    path('dashboard/invalidate-cache/', InvalidateCacheView.as_view(), name='invalidate-cache'),
    
    # === MACHINE LEARNING - PREDICCIÓN DE VENTAS ===
    path('ml/generate-demo-data/', generate_demo_sales_data, name='ml-generate-demo-data'),
    path('ml/train/', train_model, name='ml-train-model'),
    path('ml/predictions/', get_predictions, name='ml-predictions'),
    path('ml/forecast-components/', get_forecast_components, name='ml-forecast-components'),
    path('ml/performance/', get_model_performance, name='ml-performance'),
    path('ml/models/', list_models, name='ml-list-models'),
    path('ml/models/set-current/', set_current_model, name='ml-set-current-model'),
    path('ml/models/<str:version>/', delete_model, name='ml-delete-model'),
    path('ml/dashboard/', ml_dashboard, name='ml-dashboard'),

    # === REENTRENAMIENTO AUTOMÁTICO ===
    path('ml/retrain/status/', check_retrain_status, name='ml-retrain-status'),
    path('ml/retrain/auto/', auto_retrain, name='ml-auto-retrain'),
    
    # === SISTEMA DE RECOMENDACIONES ===
    path('ml/recommendations/', get_user_recommendations, name='user-recommendations'),
    path('ml/recommendations/user/<int:user_id>/', get_recommendations_for_user_id, name='recommendations-for-user'),
    path('ml/similar-products/<int:product_id>/', get_similar_products, name='similar-products'),
    path('ml/trending/', get_trending_products, name='trending-products'),
    path('ml/bought-together/<int:product_id>/', get_frequently_bought_together, name='bought-together'),
    
    # === PREDICCIONES POR PRODUCTO (CON FILTROS) ===
    path('predictions/product/<int:product_id>/', predict_product_sales, name='predict-product'),
    path('predictions/category/<int:category_id>/', predict_category_sales, name='predict-category'),
    path('predictions/compare/', compare_products_predictions, name='compare-products'),
    path('predictions/top-products/', get_top_products_forecast, name='top-products-forecast'),
    path('predictions/stock-alerts/', get_stock_alerts, name='stock-alerts'),
    path('predictions/multi-period/', get_multi_period_forecast, name='multi-period-forecast'),
    path('predictions/clear-cache/', clear_ml_cache, name='clear-ml-cache'),

    # === DASHBOARDS DE PREDICCIONES PARA FRONTEND (OPTIMIZADO PARA GRÁFICAS) ===
    path('dashboard/predictions/sales/', sales_predictions_dashboard, name='dashboard-sales-predictions'),
    path('dashboard/predictions/top-products/', top_products_predictions_dashboard, name='dashboard-top-products'),
    path('dashboard/predictions/combined/', combined_predictions_dashboard, name='dashboard-combined-predictions'),

    # === 📝 SISTEMA DE AUDITORÍA Y BITÁCORA (NUEVO) ===
    path('audit/logs/', AuditLogListView.as_view(), name='audit-logs-list'),
    path('audit/logs/<int:pk>/', AuditLogDetailView.as_view(), name='audit-log-detail'),
    path('audit/statistics/', AuditStatisticsView.as_view(), name='audit-statistics'),
    path('audit/user-activity/<str:username>/', UserActivityView.as_view(), name='user-activity'),
    path('audit/sessions/active/', ActiveSessionsView.as_view(), name='active-sessions'),
    path('audit/sessions/history/', SessionHistoryView.as_view(), name='session-history'),
    path('audit/clean-old-logs/', clean_old_logs, name='clean-old-logs'),
    path('audit/security-alerts/', security_alerts, name='security-alerts'),
    path('audit/check-session/', check_current_session, name='check-current-session'),  # Endpoint de prueba

    # === 📄 REPORTES DE AUDITORÍA CON EXPORTACIÓN (NUEVO) ===
    path('audit/generate-report/', GenerateAuditReportView.as_view(), name='generate-audit-report'),
    path('audit/generate-session-report/', GenerateSessionReportView.as_view(), name='generate-session-report'),
]
