from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VoiceCommandViewSet

router = DefaultRouter()
router.register('voice-commands', VoiceCommandViewSet, basename='voice-command')

urlpatterns = [
    path('', include(router.urls)),
]
