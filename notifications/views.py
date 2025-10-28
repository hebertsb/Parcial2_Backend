# notifications/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.utils import timezone

from .models import DeviceToken, Notification, NotificationPreference
from .serializers import (
    DeviceTokenSerializer, DeviceTokenCreateSerializer,
    NotificationSerializer, NotificationListSerializer,
    SendNotificationSerializer, NotificationPreferenceSerializer,
    NotificationStatsSerializer
)
from .notification_service import NotificationService
from api.permissions import IsAdminUser


class DeviceTokenViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar tokens de dispositivos.
    Los usuarios solo pueden ver y gestionar sus propios tokens.
    """
    serializer_class = DeviceTokenSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filtrar tokens por usuario actual"""
        return DeviceToken.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def register(self, request):
        """
        Registra un nuevo token de dispositivo para el usuario actual.
        
        POST /api/notifications/device-tokens/register/
        {
            "token": "fcm_token_string",
            "platform": "WEB",
            "device_name": "Chrome on Windows"
        }
        """
        serializer = DeviceTokenCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device_token = NotificationService.register_device_token(
            user=request.user,
            token=serializer.validated_data['token'],
            platform=serializer.validated_data.get('platform', 'WEB'),
            device_name=serializer.validated_data.get('device_name')
        )

        return Response(
            DeviceTokenSerializer(device_token).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['post'])
    def unregister(self, request):
        """
        Desregistra (desactiva) un token de dispositivo.
        
        POST /api/notifications/device-tokens/unregister/
        {
            "token": "fcm_token_string"
        }
        """
        token = request.data.get('token')
        if not token:
            return Response(
                {'error': 'Token es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        success = NotificationService.unregister_device_token(token)
        
        if success:
            return Response(
                {'message': 'Token desactivado correctamente'},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {'error': 'Token no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def my_devices(self, request):
        """
        Lista todos los dispositivos activos del usuario actual.
        
        GET /api/notifications/device-tokens/my_devices/
        """
        devices = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(devices, many=True)
        return Response(serializer.data)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para ver notificaciones.
    Los usuarios solo pueden ver sus propias notificaciones.
    Los admins pueden enviar notificaciones.
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return NotificationListSerializer
        elif self.action == 'send':
            return SendNotificationSerializer
        return NotificationSerializer

    def get_queryset(self):
        """Filtrar notificaciones por usuario actual"""
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def unread(self, request):
        """
        Lista solo las notificaciones no leídas del usuario.
        
        GET /api/notifications/notifications/unread/
        """
        notifications = self.get_queryset().filter(
            status__in=[Notification.Status.PENDING, Notification.Status.SENT]
        )
        serializer = NotificationListSerializer(notifications, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """
        Obtiene el número de notificaciones no leídas.
        
        GET /api/notifications/notifications/unread_count/
        """
        count = NotificationService.get_unread_count(request.user)
        return Response({'count': count})

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """
        Marca una notificación como leída.
        
        POST /api/notifications/notifications/{id}/mark_as_read/
        """
        success = NotificationService.mark_notification_as_read(pk, request.user)
        
        if success:
            return Response(
                {'message': 'Notificación marcada como leída'},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {'error': 'Notificación no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        """
        Marca todas las notificaciones como leídas.
        
        POST /api/notifications/notifications/mark_all_as_read/
        """
        count = NotificationService.mark_all_as_read(request.user)
        return Response({
            'message': f'{count} notificaciones marcadas como leídas',
            'count': count
        })

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def send(self, request):
        """
        Envía una notificación a usuarios específicos o a todos los admins.
        Solo disponible para administradores.
        
        POST /api/notifications/notifications/send/
        {
            "user_ids": [1, 2, 3],  // Opcional, si está vacío se envía a todos los admins
            "title": "Título de la notificación",
            "body": "Cuerpo del mensaje",
            "notification_type": "SYSTEM",
            "data": {"key": "value"},  // Opcional
            "image_url": "https://..."  // Opcional
        }
        """
        serializer = SendNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_ids = serializer.validated_data.get('user_ids')
        
        if user_ids:
            # Enviar a usuarios específicos
            users = User.objects.filter(id__in=user_ids, is_active=True)
            result = NotificationService.send_notification_to_users(
                users=list(users),
                title=serializer.validated_data['title'],
                body=serializer.validated_data['body'],
                notification_type=serializer.validated_data.get('notification_type', 'CUSTOM'),
                data=serializer.validated_data.get('data'),
                image_url=serializer.validated_data.get('image_url')
            )
        else:
            # Enviar a todos los admins
            result = NotificationService.send_to_all_admins(
                title=serializer.validated_data['title'],
                body=serializer.validated_data['body'],
                notification_type=serializer.validated_data.get('notification_type', 'SYSTEM'),
                data=serializer.validated_data.get('data')
            )

        return Response(result, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Obtiene estadísticas de notificaciones del usuario.
        
        GET /api/notifications/notifications/stats/
        """
        queryset = self.get_queryset()
        
        stats = {
            'total_notifications': queryset.count(),
            'unread_count': queryset.filter(
                status__in=[Notification.Status.PENDING, Notification.Status.SENT]
            ).count(),
            'sent_count': queryset.filter(status=Notification.Status.SENT).count(),
            'failed_count': queryset.filter(status=Notification.Status.FAILED).count(),
            'by_type': dict(queryset.values('notification_type').annotate(
                count=Count('id')
            ).values_list('notification_type', 'count')),
            'recent_notifications': queryset[:10]
        }

        serializer = NotificationStatsSerializer(stats)
        return Response(serializer.data)


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar preferencias de notificaciones.
    Los usuarios solo pueden ver y editar sus propias preferencias.
    """
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filtrar preferencias por usuario actual"""
        return NotificationPreference.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def my_preferences(self, request):
        """
        Obtiene las preferencias del usuario actual.
        Si no existen, las crea con valores por defecto.
        
        GET /api/notifications/preferences/my_preferences/
        """
        preferences, created = NotificationPreference.objects.get_or_create(
            user=request.user
        )
        serializer = self.get_serializer(preferences)
        return Response(serializer.data)

    @action(detail=False, methods=['patch'])
    def update_preferences(self, request):
        """
        Actualiza las preferencias del usuario actual.
        
        PATCH /api/notifications/preferences/update_preferences/
        {
            "enabled": true,
            "sale_notifications": true,
            "product_notifications": false,
            ...
        }
        """
        preferences, created = NotificationPreference.objects.get_or_create(
            user=request.user
        )
        serializer = self.get_serializer(preferences, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data)
