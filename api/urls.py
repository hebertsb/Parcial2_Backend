# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    register_view,
    login_view,
    LogoutView,
    UserProfileView,
    UserListView,
    UserDetailView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    ClientViewSet # Import the new ViewSet
)

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'clients', ClientViewSet, basename='client')

urlpatterns = [
    # --- Autenticación ---
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    # --- Perfil de Usuario (para el usuario logueado) ---
    path('profile/', UserProfileView.as_view(), name='user-profile'),

    # --- Gestión de Usuarios (SOLO ADMINS) ---
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user-detail'),

    # --- Gestión de Clientes (CRUD via ViewSet) ---
    path('', include(router.urls)),
]
