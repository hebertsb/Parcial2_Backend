# api/views/__init__.py
from .auth import (
    register_view,
    login_view,
    LogoutView,
    UserProfileView,
    PasswordResetRequestView,  # <-- AÑADIR ESTA LÍNEA
    PasswordResetConfirmView   # <-- AÑADIR ESTA LÍNEA
)
from .user import UserListView, UserDetailView, ClientViewSet