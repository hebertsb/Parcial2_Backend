# api/urls.py
from django.urls import path
from .views import (
    register_view,
    login_view,
    LogoutView,
    UserProfileView,
    UserListView,
    UserDetailView,
    PasswordResetRequestView,  # <-- Importar
    PasswordResetConfirmView,
    ClientListView
)

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
path('clients/', ClientListView.as_view(), name='client-list'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user-detail'),
]
