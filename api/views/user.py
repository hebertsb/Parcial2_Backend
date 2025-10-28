# api/views/user.py
from rest_framework import generics, status
from rest_framework.response import Response
from django.contrib.auth.models import User
from ..serializers import AdminUserSerializer
from ..permissions import IsAdminUser

# CAMBIO: Cambiamos ListAPIView por ListCreateAPIView
class UserListView(generics.ListCreateAPIView):
    """
    Vista para listar y CREAR usuarios.
    Solo accesible por administradores.
    """
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser]

class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para ver, actualizar y eliminar un usuario específico.
    Solo accesible por administradores.
    """
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance == request.user:
            return Response({"error": "No puedes eliminar tu propia cuenta de administrador."}, status=status.HTTP_400_BAD_REQUEST)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

class ClientListView(generics.ListAPIView):
    """
    Vista para listar solo a los usuarios con el rol de 'CLIENTE'.
    Solo accesible por administradores.
    """
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        """
        Este método filtra el queryset para devolver solo los usuarios
        cuyo perfil tiene el rol 'CLIENT'.
        """
        return User.objects.filter(profile__role='CLIENT')