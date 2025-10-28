# sales/models_audit.py
"""
Sistema de Auditoría y Bitácora
Registra TODAS las acciones de los usuarios con timestamp, IP, y detalles completos.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json


class AuditLog(models.Model):
    """
    Modelo para registrar TODAS las acciones de los usuarios.

    Registra:
    - Usuario que realizó la acción
    - Acción realizada
    - Timestamp exacto
    - IP del usuario
    - Detalles adicionales
    - User Agent (navegador/app)
    - Método HTTP (GET, POST, PUT, DELETE)
    - Endpoint accedido
    - Estado de la respuesta (éxito/error)
    """

    # Tipos de acciones
    ACTION_TYPES = [
        ('AUTH', 'Autenticación'),
        ('CREATE', 'Creación'),
        ('READ', 'Lectura'),
        ('UPDATE', 'Actualización'),
        ('DELETE', 'Eliminación'),
        ('REPORT', 'Generación de Reporte'),
        ('PAYMENT', 'Pago/Transacción'),
        ('CONFIG', 'Configuración'),
        ('ML', 'Acción de Machine Learning'),
        ('OTHER', 'Otra'),
    ]

    # Niveles de severidad
    SEVERITY_LEVELS = [
        ('LOW', 'Baja'),
        ('MEDIUM', 'Media'),
        ('HIGH', 'Alta'),
        ('CRITICAL', 'Crítica'),
    ]

    # Información del usuario
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text="Usuario que realizó la acción (null si es anónimo)"
    )
    username = models.CharField(
        max_length=150,
        blank=True,
        help_text="Username guardado por redundancia (en caso de eliminación del usuario)"
    )

    # Detalles de la acción
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_TYPES,
        default='OTHER',
        db_index=True,
        help_text="Tipo de acción realizada"
    )
    action_description = models.TextField(
        help_text="Descripción detallada de la acción"
    )

    # Información de la petición HTTP
    http_method = models.CharField(
        max_length=10,
        db_index=True,
        help_text="Método HTTP (GET, POST, PUT, DELETE, etc.)"
    )
    endpoint = models.CharField(
        max_length=500,
        db_index=True,
        help_text="URL del endpoint accedido"
    )
    query_params = models.TextField(
        blank=True,
        help_text="Parámetros de la URL (query string)"
    )
    request_body = models.TextField(
        blank=True,
        help_text="Cuerpo de la petición (para POST/PUT)"
    )

    # Información de la respuesta
    response_status = models.IntegerField(
        db_index=True,
        help_text="Código de estado HTTP de la respuesta"
    )
    response_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Tiempo de respuesta en milisegundos"
    )
    success = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Si la operación fue exitosa"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Mensaje de error si la operación falló"
    )

    # Información de red
    ip_address = models.GenericIPAddressField(
        db_index=True,
        help_text="Dirección IP del usuario"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User Agent del navegador/aplicación"
    )

    # Metadatos adicionales
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_LEVELS,
        default='LOW',
        db_index=True,
        help_text="Nivel de severidad de la acción"
    )
    additional_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Datos adicionales en formato JSON"
    )

    # Timestamp
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Fecha y hora exacta de la acción"
    )

    class Meta:
        db_table = 'audit_logs'
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'user']),
            models.Index(fields=['action_type', '-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
            models.Index(fields=['success', '-timestamp']),
        ]

    def __str__(self):
        user_str = self.username or 'Anónimo'
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {user_str} - {self.action_description}"

    @classmethod
    def log_action(cls, user, action_type, description, request, response=None,
                   severity='LOW', additional_data=None, response_time_ms=None):
        """
        Método helper para crear un registro de auditoría.

        Args:
            user: Usuario que realizó la acción
            action_type: Tipo de acción (ver ACTION_TYPES)
            description: Descripción de la acción
            request: Objeto HttpRequest
            response: Objeto HttpResponse (opcional)
            severity: Nivel de severidad
            additional_data: Datos adicionales (dict)
            response_time_ms: Tiempo de respuesta en ms

        Returns:
            AuditLog: Instancia creada
        """
        # Obtener IP
        ip_address = cls._get_client_ip(request)

        # Obtener User Agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # Preparar request body (censurar contraseñas)
        request_body = ''
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if hasattr(request, 'data'):
                    body_data = dict(request.data)
                else:
                    body_data = dict(request.POST)

                # Censurar campos sensibles
                sensitive_fields = ['password', 'token', 'secret', 'api_key', 'card_number']
                for field in sensitive_fields:
                    if field in body_data:
                        body_data[field] = '***CENSORED***'

                request_body = json.dumps(body_data, ensure_ascii=False)[:5000]  # Limitar a 5000 chars
            except:
                request_body = ''

        # Query params
        query_params = request.META.get('QUERY_STRING', '')

        # Response status
        response_status = response.status_code if response else 200
        success = 200 <= response_status < 400

        # Error message
        error_message = ''
        if not success and response:
            try:
                error_message = str(response.content.decode('utf-8'))[:1000]
            except:
                error_message = 'Error desconocido'

        # Crear el registro
        return cls.objects.create(
            user=user if user and user.is_authenticated else None,
            username=user.username if user and user.is_authenticated else 'Anónimo',
            action_type=action_type,
            action_description=description,
            http_method=request.method,
            endpoint=request.path,
            query_params=query_params,
            request_body=request_body,
            response_status=response_status,
            response_time_ms=response_time_ms,
            success=success,
            error_message=error_message,
            ip_address=ip_address,
            user_agent=user_agent,
            severity=severity,
            additional_data=additional_data,
        )

    @staticmethod
    def _get_client_ip(request):
        """
        Obtiene la IP real del cliente considerando proxies.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip

    def to_dict(self):
        """
        Convierte el registro a diccionario para APIs.
        """
        return {
            'id': self.id,
            'user': self.username,
            'action_type': self.get_action_type_display(),
            'action_description': self.action_description,
            'http_method': self.http_method,
            'endpoint': self.endpoint,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat(),
            'success': self.success,
            'response_status': self.response_status,
            'severity': self.get_severity_display(),
        }


class UserSession(models.Model):
    """
    Modelo para rastrear sesiones de usuarios.
    Complementa la bitácora con información de sesiones activas.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    login_time = models.DateTimeField(default=timezone.now)
    last_activity = models.DateTimeField(default=timezone.now)
    logout_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'user_sessions'
        verbose_name = 'Sesión de Usuario'
        verbose_name_plural = 'Sesiones de Usuarios'
        ordering = ['-last_activity']

    def __str__(self):
        return f"{self.user.username} - {self.ip_address} ({self.login_time.strftime('%Y-%m-%d %H:%M')})"

    def duration_minutes(self):
        """Calcula la duración de la sesión en minutos."""
        end = self.logout_time or timezone.now()
        duration = end - self.login_time
        return int(duration.total_seconds() / 60)
