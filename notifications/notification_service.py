# notifications/notification_service.py
from django.contrib.auth.models import User
from django.utils import timezone
from typing import List, Optional, Dict
import logging

from .models import DeviceToken, Notification, NotificationPreference
from .firebase_service import firebase_service

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Servicio de alto nivel para gestionar notificaciones.
    Maneja la lógica de negocio y utiliza FirebaseService para el envío.
    """

    @staticmethod
    def send_notification_to_user(
        user: User,
        title: str,
        body: str,
        notification_type: str = 'CUSTOM',
        data: Optional[Dict] = None,
        image_url: Optional[str] = None
    ) -> Dict:
        """
        Envía una notificación a todos los dispositivos activos de un usuario.
        
        Args:
            user: Usuario destinatario
            title: Título de la notificación
            body: Cuerpo del mensaje
            notification_type: Tipo de notificación (ver Notification.NotificationType)
            data: Datos adicionales (opcional)
            image_url: URL de imagen (opcional)
            
        Returns:
            Dict con estadísticas del envío
        """
        try:
            # Verificar preferencias del usuario
            try:
                preferences = user.notification_preferences
                if not preferences.should_send_notification(notification_type):
                    logger.info(f"Notificación no enviada a {user.username} por preferencias")
                    return {
                        'success': False,
                        'reason': 'user_preferences',
                        'message': 'Usuario tiene deshabilitadas estas notificaciones'
                    }
            except NotificationPreference.DoesNotExist:
                # Crear preferencias por defecto
                NotificationPreference.objects.create(user=user)

            # Obtener tokens activos del usuario
            device_tokens = DeviceToken.objects.filter(
                user=user,
                is_active=True
            )

            if not device_tokens.exists():
                logger.info(f"Usuario {user.username} no tiene dispositivos registrados")
                return {
                    'success': False,
                    'reason': 'no_devices',
                    'message': 'Usuario no tiene dispositivos registrados'
                }

            # Crear registro de notificación
            notification = Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                body=body,
                data=data
            )

            # Obtener lista de tokens
            tokens = [dt.token for dt in device_tokens]

            # Enviar notificación
            result = firebase_service.send_multicast_notification(
                tokens=tokens,
                title=title,
                body=body,
                data=data or {},
                image_url=image_url
            )

            # Actualizar estado de la notificación
            if result['success_count'] > 0:
                notification.mark_as_sent()
            else:
                notification.mark_as_failed("No se pudo enviar a ningún dispositivo")

            # Desactivar tokens inválidos
            if result['tokens_to_remove']:
                DeviceToken.objects.filter(
                    token__in=result['tokens_to_remove']
                ).update(is_active=False)
                logger.info(f"Desactivados {len(result['tokens_to_remove'])} tokens inválidos")

            return {
                'success': result['success_count'] > 0,
                'notification_id': notification.id,
                'devices_count': len(tokens),
                'success_count': result['success_count'],
                'failure_count': result['failure_count'],
                'invalid_tokens': len(result['tokens_to_remove'])
            }

        except Exception as e:
            logger.error(f"Error enviando notificación a {user.username}: {str(e)}")
            return {
                'success': False,
                'reason': 'error',
                'message': str(e)
            }

    @staticmethod
    def send_notification_to_users(
        users: List[User],
        title: str,
        body: str,
        notification_type: str = 'CUSTOM',
        data: Optional[Dict] = None,
        image_url: Optional[str] = None
    ) -> Dict:
        """
        Envía una notificación a múltiples usuarios.
        
        Returns:
            Dict con estadísticas agregadas del envío
        """
        results = {
            'total_users': len(users),
            'successful_users': 0,
            'failed_users': 0,
            'total_devices': 0,
            'successful_sends': 0,
            'failed_sends': 0
        }

        for user in users:
            result = NotificationService.send_notification_to_user(
                user=user,
                title=title,
                body=body,
                notification_type=notification_type,
                data=data,
                image_url=image_url
            )

            if result['success']:
                results['successful_users'] += 1
                results['total_devices'] += result.get('devices_count', 0)
                results['successful_sends'] += result.get('success_count', 0)
                results['failed_sends'] += result.get('failure_count', 0)
            else:
                results['failed_users'] += 1

        return results

    @staticmethod
    def send_to_all_admins(
        title: str,
        body: str,
        notification_type: str = 'SYSTEM',
        data: Optional[Dict] = None
    ) -> Dict:
        """
        Envía una notificación a todos los administradores.
        """
        from api.models import Profile
        
        admin_users = User.objects.filter(
            profile__role=Profile.Role.ADMIN,
            is_active=True
        )

        return NotificationService.send_notification_to_users(
            users=list(admin_users),
            title=title,
            body=body,
            notification_type=notification_type,
            data=data
        )

    @staticmethod
    def register_device_token(
        user: User,
        token: str,
        platform: str = 'WEB',
        device_name: Optional[str] = None
    ) -> DeviceToken:
        """
        Registra o actualiza un token de dispositivo para un usuario.
        
        Args:
            user: Usuario propietario del dispositivo
            token: Token FCM del dispositivo
            platform: Plataforma (ANDROID, IOS, WEB)
            device_name: Nombre descriptivo del dispositivo
            
        Returns:
            Instancia de DeviceToken
        """
        device_token, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                'user': user,
                'platform': platform,
                'device_name': device_name,
                'is_active': True,
                'last_used': timezone.now()
            }
        )

        if created:
            logger.info(f"Nuevo dispositivo registrado para {user.username}: {platform}")
        else:
            logger.info(f"Dispositivo actualizado para {user.username}: {platform}")

        return device_token

    @staticmethod
    def unregister_device_token(token: str) -> bool:
        """
        Desregistra (desactiva) un token de dispositivo.
        
        Returns:
            True si se desactivó correctamente, False si no existía
        """
        try:
            device_token = DeviceToken.objects.get(token=token)
            device_token.is_active = False
            device_token.save()
            logger.info(f"Token desactivado para {device_token.user.username}")
            return True
        except DeviceToken.DoesNotExist:
            logger.warning(f"Intento de desactivar token inexistente")
            return False

    @staticmethod
    def get_user_notifications(
        user: User,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Notification]:
        """
        Obtiene las notificaciones de un usuario.
        
        Args:
            user: Usuario
            unread_only: Solo notificaciones no leídas
            limit: Límite de resultados
            
        Returns:
            Lista de notificaciones
        """
        queryset = Notification.objects.filter(user=user)
        
        if unread_only:
            queryset = queryset.filter(status__in=['PENDING', 'SENT'])
        
        return list(queryset[:limit])

    @staticmethod
    def mark_notification_as_read(notification_id: int, user: User) -> bool:
        """
        Marca una notificación como leída.
        
        Returns:
            True si se marcó correctamente, False si no existía o no pertenece al usuario
        """
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False

    @staticmethod
    def mark_all_as_read(user: User) -> int:
        """
        Marca todas las notificaciones de un usuario como leídas.
        
        Returns:
            Número de notificaciones marcadas
        """
        count = Notification.objects.filter(
            user=user,
            status=Notification.Status.SENT
        ).update(
            status=Notification.Status.READ,
            read_at=timezone.now()
        )
        
        logger.info(f"Marcadas {count} notificaciones como leídas para {user.username}")
        return count

    @staticmethod
    def get_unread_count(user: User) -> int:
        """
        Obtiene el número de notificaciones no leídas de un usuario.
        """
        return Notification.objects.filter(
            user=user,
            status__in=[Notification.Status.PENDING, Notification.Status.SENT]
        ).count()


# Funciones auxiliares para eventos comunes

def notify_order_completed(order, customer: User):
    """Notifica cuando se completa una orden (venta)"""
    NotificationService.send_to_all_admins(
        title="Nueva Venta Registrada",
        body=f"Se ha completado una venta por ${order.total_price:.2f}",
        notification_type='SALE_CREATED',
        data={
            'order_id': str(order.id),
            'amount': str(order.total_price),
            'customer': customer.username
        }
    )


def notify_product_low_stock(product):
    """Notifica cuando un producto tiene stock bajo"""
    NotificationService.send_to_all_admins(
        title="⚠️ Stock Bajo",
        body=f"El producto '{product.name}' tiene solo {product.stock} unidades disponibles",
        notification_type='PRODUCT_LOW_STOCK',
        data={
            'product_id': str(product.id),
            'product_name': product.name,
            'stock': str(product.stock)
        }
    )


def notify_report_generated(user: User, report_type: str, report_url: str = None):
    """Notifica cuando se genera un reporte"""
    NotificationService.send_notification_to_user(
        user=user,
        title="Reporte Generado",
        body=f"Tu reporte de {report_type} está listo",
        notification_type='REPORT_GENERATED',
        data={
            'report_type': report_type,
            'report_url': report_url or ''
        }
    )


def notify_ml_prediction(user: User, prediction_data: Dict):
    """Notifica cuando se completa una predicción de ML"""
    NotificationService.send_notification_to_user(
        user=user,
        title="Predicción Completada",
        body="Tu predicción de ventas ha sido procesada",
        notification_type='ML_PREDICTION',
        data=prediction_data
    )
