# notifications/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class DeviceToken(models.Model):
    """
    Modelo para almacenar los tokens FCM de los dispositivos de los usuarios.
    Un usuario puede tener múltiples dispositivos.
    """
    class Platform(models.TextChoices):
        ANDROID = 'ANDROID', 'Android'
        IOS = 'IOS', 'iOS'
        WEB = 'WEB', 'Web'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.CharField(max_length=255, unique=True, help_text='FCM device token')
    platform = models.CharField(max_length=20, choices=Platform.choices, default=Platform.WEB)
    device_name = models.CharField(max_length=100, blank=True, null=True, help_text='Nombre del dispositivo')
    is_active = models.BooleanField(default=True, help_text='Token activo/válido')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-last_used']
        verbose_name = 'Token de Dispositivo'
        verbose_name_plural = 'Tokens de Dispositivos'

    def __str__(self):
        return f'{self.user.username} - {self.platform} - {self.device_name or "Sin nombre"}'


class Notification(models.Model):
    """
    Modelo para registrar el historial de notificaciones enviadas.
    """
    class NotificationType(models.TextChoices):
        SALE_CREATED = 'SALE_CREATED', 'Venta Creada'
        SALE_UPDATED = 'SALE_UPDATED', 'Venta Actualizada'
        SALE_DELETED = 'SALE_DELETED', 'Venta Eliminada'
        PRODUCT_LOW_STOCK = 'PRODUCT_LOW_STOCK', 'Stock Bajo'
        PRODUCT_CREATED = 'PRODUCT_CREATED', 'Producto Creado'
        REPORT_GENERATED = 'REPORT_GENERATED', 'Reporte Generado'
        ML_PREDICTION = 'ML_PREDICTION', 'Predicción ML'
        SYSTEM = 'SYSTEM', 'Sistema'
        CUSTOM = 'CUSTOM', 'Personalizado'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        SENT = 'SENT', 'Enviado'
        FAILED = 'FAILED', 'Fallido'
        READ = 'READ', 'Leído'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=NotificationType.choices, default=NotificationType.CUSTOM)
    title = models.CharField(max_length=200)
    body = models.TextField()
    data = models.JSONField(blank=True, null=True, help_text='Datos adicionales en formato JSON')
    
    # Firebase fields
    fcm_message_id = models.CharField(max_length=255, blank=True, null=True, help_text='ID del mensaje FCM')
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.title} ({self.status})'

    def mark_as_sent(self, message_id=None):
        """Marca la notificación como enviada"""
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        if message_id:
            self.fcm_message_id = message_id
        self.save()

    def mark_as_failed(self, error_message):
        """Marca la notificación como fallida"""
        self.status = self.Status.FAILED
        self.error_message = error_message
        self.save()

    def mark_as_read(self):
        """Marca la notificación como leída"""
        if self.status == self.Status.SENT:
            self.status = self.Status.READ
            self.read_at = timezone.now()
            self.save()


class NotificationPreference(models.Model):
    """
    Preferencias de notificaciones por usuario.
    Permite a los usuarios controlar qué notificaciones desean recibir.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Preferencias generales
    enabled = models.BooleanField(default=True, help_text='Notificaciones habilitadas')
    
    # Preferencias por tipo
    sale_notifications = models.BooleanField(default=True, help_text='Notificaciones de ventas')
    product_notifications = models.BooleanField(default=True, help_text='Notificaciones de productos')
    report_notifications = models.BooleanField(default=True, help_text='Notificaciones de reportes')
    ml_notifications = models.BooleanField(default=True, help_text='Notificaciones de ML')
    system_notifications = models.BooleanField(default=True, help_text='Notificaciones del sistema')
    
    # Horario de notificaciones
    quiet_hours_start = models.TimeField(null=True, blank=True, help_text='Inicio de horario silencioso')
    quiet_hours_end = models.TimeField(null=True, blank=True, help_text='Fin de horario silencioso')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Preferencia de Notificación'
        verbose_name_plural = 'Preferencias de Notificaciones'

    def __str__(self):
        return f'Preferencias de {self.user.username}'

    def should_send_notification(self, notification_type):
        """Verifica si se debe enviar una notificación según las preferencias"""
        if not self.enabled:
            return False
        
        # Verificar horario silencioso
        if self.quiet_hours_start and self.quiet_hours_end:
            current_time = timezone.now().time()
            if self.quiet_hours_start <= current_time <= self.quiet_hours_end:
                return False
        
        # Verificar preferencias por tipo
        type_mapping = {
            'SALE_CREATED': self.sale_notifications,
            'SALE_UPDATED': self.sale_notifications,
            'SALE_DELETED': self.sale_notifications,
            'PRODUCT_LOW_STOCK': self.product_notifications,
            'PRODUCT_CREATED': self.product_notifications,
            'REPORT_GENERATED': self.report_notifications,
            'ML_PREDICTION': self.ml_notifications,
            'SYSTEM': self.system_notifications,
        }
        
        return type_mapping.get(notification_type, True)
