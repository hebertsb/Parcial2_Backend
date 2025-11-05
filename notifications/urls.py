# notifications/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DeviceTokenViewSet, NotificationViewSet, NotificationPreferenceViewSet

router = DefaultRouter()
router.register(r'device-tokens', DeviceTokenViewSet, basename='device-token')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'preferences', NotificationPreferenceViewSet, basename='notification-preference')

urlpatterns = [
    path('', include(router.urls)),
]
