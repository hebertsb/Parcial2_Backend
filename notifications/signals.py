# notifications/signals.py
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
import logging

from .models import NotificationPreference
from .notification_service import (
    notify_order_completed,
    notify_product_low_stock,
    NotificationService
)

logger = logging.getLogger(__name__)


# ============================================================================
# SEÑALES DE USUARIOS
# ============================================================================

@receiver(post_save, sender=User)
def create_notification_preferences(sender, instance, created, **kwargs):
    """
    Crea automáticamente preferencias de notificación cuando se crea un usuario.
    """
    if created:
        NotificationPreference.objects.get_or_create(user=instance)
        logger.info(f"Preferencias de notificación creadas para {instance.username}")


# ============================================================================
# SEÑALES DE VENTAS/ÓRDENES
# ============================================================================

@receiver(post_save, sender='sales.Order')
def order_completed_notification(sender, instance, created, **kwargs):
    """
    Envía notificación cuando una orden se completa (se convierte en venta).
    """
    # Solo notificar cuando el estado cambia a COMPLETED
    if not created and instance.status == 'COMPLETED':
        try:
            # Notificar a admins
            NotificationService.send_to_all_admins(
                title="💰 Nueva Venta Completada",
                body=f"Venta completada por {instance.customer.username} - ${instance.total_price:.2f}",
                notification_type='SALE_CREATED',
                data={
                    'order_id': str(instance.id),
                    'amount': str(instance.total_price),
                    'customer': instance.customer.username
                }
            )
            
            # También notificar al cliente
            NotificationService.send_notification_to_user(
                user=instance.customer,
                title="✅ ¡Compra Exitosa!",
                body=f"Tu compra por ${instance.total_price:.2f} ha sido completada",
                notification_type='SALE_CREATED',
                data={
                    'order_id': str(instance.id),
                    'amount': str(instance.total_price)
                }
            )
            
            logger.info(f"Notificación de orden completada enviada para Order ID: {instance.id}")
        except Exception as e:
            logger.error(f"Error enviando notificación de orden: {str(e)}")


@receiver(post_save, sender='sales.Order')
def order_created_notification(sender, instance, created, **kwargs):
    """
    Envía notificación cuando se crea una nueva orden.
    """
    if created:
        try:
            # Notificar al cliente que creó la orden
            NotificationService.send_notification_to_user(
                user=instance.customer,
                title="🛒 Orden Creada",
                body=f"Tu orden #{instance.id} ha sido creada exitosamente",
                notification_type='SALE_CREATED',
                data={
                    'order_id': str(instance.id),
                    'status': instance.status
                }
            )
            
            logger.info(f"Notificación de orden creada enviada para Order ID: {instance.id}")
        except Exception as e:
            logger.error(f"Error enviando notificación de orden: {str(e)}")


@receiver(post_delete, sender='sales.Order')
def order_deleted_notification(sender, instance, **kwargs):
    """
    Envía notificación cuando se elimina una orden/venta.
    """
    try:
        NotificationService.send_to_all_admins(
            title="🗑️ Orden Eliminada",
            body=f"Se ha eliminado la orden #{instance.id} de {instance.customer.username}",
            notification_type='SALE_DELETED',
            data={
                'order_id': str(instance.id),
                'amount': str(instance.total_price)
            }
        )
        logger.info(f"Notificación de eliminación enviada para Order ID: {instance.id}")
    except Exception as e:
        logger.error(f"Error enviando notificación de eliminación: {str(e)}")


# ============================================================================
# SEÑALES DE PRODUCTOS
# ============================================================================

@receiver(post_save, sender='products.Product')
def product_created_notification(sender, instance, created, **kwargs):
    """
    Envía notificación cuando se crea un nuevo producto.
    """
    if created:
        try:
            NotificationService.send_to_all_admins(
                title="🆕 Nuevo Producto",
                body=f"Se ha agregado el producto '{instance.name}' al inventario",
                notification_type='PRODUCT_CREATED',
                data={
                    'product_id': str(instance.id),
                    'product_name': instance.name,
                    'price': str(instance.price),
                    'stock': str(instance.stock)
                }
            )
            logger.info(f"Notificación de producto enviada para Product ID: {instance.id}")
        except Exception as e:
            logger.error(f"Error enviando notificación de producto: {str(e)}")


@receiver(pre_save, sender='products.Product')
def check_low_stock(sender, instance, **kwargs):
    """
    Verifica si el stock es bajo y envía notificación.
    Solo se envía cuando el stock baja por debajo del umbral.
    """
    if instance.pk:  # Solo para productos existentes
        try:
            # Obtener el producto anterior
            old_product = sender.objects.get(pk=instance.pk)
            
            # Definir umbral de stock bajo
            LOW_STOCK_THRESHOLD = 10
            
            # Si el stock anterior era >= umbral y ahora es < umbral
            if old_product.stock >= LOW_STOCK_THRESHOLD and instance.stock < LOW_STOCK_THRESHOLD:
                # Usar post_save para enviar la notificación después de guardar
                instance._notify_low_stock = True
            else:
                instance._notify_low_stock = False
                
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='products.Product')
def product_low_stock_notification(sender, instance, created, **kwargs):
    """
    Envía notificación si el producto tiene stock bajo.
    Esta señal se ejecuta después de pre_save.
    """
    if not created and getattr(instance, '_notify_low_stock', False):
        try:
            notify_product_low_stock(instance)
            logger.info(f"Notificación de stock bajo enviada para Product ID: {instance.id}")
        except Exception as e:
            logger.error(f"Error enviando notificación de stock bajo: {str(e)}")


# ============================================================================
# SEÑALES DE REPORTES (Ejemplo para integración futura)
# ============================================================================

# Puedes agregar señales personalizadas para reportes
# from django.dispatch import Signal
# report_generated = Signal()
#
# @receiver(report_generated)
# def report_generated_notification(sender, user, report_type, report_url, **kwargs):
#     """Notifica cuando se genera un reporte"""
#     try:
#         from .notification_service import notify_report_generated
#         notify_report_generated(user, report_type, report_url)
#     except Exception as e:
#         logger.error(f"Error enviando notificación de reporte: {str(e)}")
