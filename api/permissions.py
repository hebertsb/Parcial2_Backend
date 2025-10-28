# api/permissions.py
from rest_framework.permissions import BasePermission

class IsAdminUser(BasePermission):
    """
    Permite el acceso solo a usuarios con el rol de 'Admin'.
    """
    def has_permission(self, request, view):
        # Primero, asegúrate de que el usuario esté autenticado
        if not request.user or not request.user.is_authenticated:
            return False
        # Luego, verifica que el usuario tenga un perfil y que su rol sea 'ADMIN'
        return hasattr(request.user, 'profile') and request.user.profile.role == 'ADMIN'