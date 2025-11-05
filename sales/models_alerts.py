"""
Modelos para el sistema de alertas automáticas de comandos de voz
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class VoiceCommandAlert(models.Model):
    """
    Almacena alertas/programaciones de comandos de voz
    Permite ejecutar comandos automáticamente según condiciones
    """

    # Tipos de alerta
    ALERT_TYPE_CHOICES = [
        ('scheduled', 'Programada'),  # Se ejecuta en horario fijo
        ('threshold', 'Por Umbral'),  # Se ejecuta cuando se cumple condición
        ('condition', 'Por Condición'),  # Se ejecuta cuando ocurre evento
    ]

    # Frecuencias
    FREQUENCY_CHOICES = [
        ('daily', 'Diario'),
        ('weekly', 'Semanal'),
        ('monthly', 'Mensual'),
        ('on_condition', 'Solo cuando se cumpla condición'),
    ]

    # Información básica
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='voice_alerts')
    command = models.TextField(help_text="Comando original del usuario")
    description = models.CharField(max_length=255, blank=True, help_text="Descripción de la alerta")

    # Tipo y frecuencia
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)

    # Condiciones (JSON)
    # Ejemplos:
    # {'type': 'stock_low', 'threshold': 10}
    # {'type': 'sales_drop', 'percentage': 20}
    # {'type': 'inventory_zero', 'products': ['prod1', 'prod2']}
    conditions = models.JSONField(
        null=True,
        blank=True,
        help_text="Condiciones para activar la alerta"
    )

    # Programación (para alertas scheduled)
    # Ejemplos:
    # {'day_of_week': 1, 'hour': 9, 'minute': 0}  # Lunes a las 9:00
    # {'day_of_month': 1, 'hour': 8, 'minute': 0}  # Día 1 de cada mes a las 8:00
    schedule = models.JSONField(
        null=True,
        blank=True,
        help_text="Programación horaria de la alerta"
    )

    # Parámetros del comando (extraídos del parser)
    command_params = models.JSONField(
        null=True,
        blank=True,
        help_text="Parámetros extraídos del comando"
    )

    # Estado
    active = models.BooleanField(default=True, help_text="Alerta activa/inactiva")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_triggered = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Última vez que se ejecutó la alerta"
    )
    next_trigger = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Próxima ejecución programada"
    )

    # Notificación
    notify_email = models.BooleanField(default=True, help_text="Enviar por email")
    notify_in_app = models.BooleanField(default=True, help_text="Notificación in-app")
    email_recipient = models.EmailField(
        blank=True,
        null=True,
        help_text="Email destino (usa el del usuario si está vacío)"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Alerta de Comando de Voz'
        verbose_name_plural = 'Alertas de Comandos de Voz'

    def __str__(self):
        return f"{self.user.username} - {self.description or self.command[:50]}"

    def should_trigger(self) -> bool:
        """
        Determina si la alerta debe ejecutarse ahora

        Returns:
            bool: True si debe ejecutarse
        """
        if not self.active:
            return False

        now = timezone.now()

        # TIPO 1: Alertas programadas (scheduled)
        if self.alert_type == 'scheduled':
            if not self.next_trigger:
                return False

            # Verificar si es hora de ejecutar
            if now >= self.next_trigger:
                return True

        # TIPO 2: Alertas por umbral (threshold)
        elif self.alert_type == 'threshold':
            return self._check_threshold_condition()

        # TIPO 3: Alertas por condición (condition)
        elif self.alert_type == 'condition':
            return self._check_condition()

        return False

    def _check_threshold_condition(self) -> bool:
        """
        Verifica si se cumple la condición de umbral

        Returns:
            bool: True si se cumple
        """
        if not self.conditions:
            return False

        condition_type = self.conditions.get('type')

        # Stock bajo
        if condition_type == 'stock_low':
            threshold = self.conditions.get('threshold', 10)
            # Aquí se haría la consulta real a la BD
            # from sales.models import Product
            # low_stock_count = Product.objects.filter(stock__lte=threshold).count()
            # return low_stock_count > 0
            logger.info(f"Verificando stock bajo (umbral: {threshold})")
            return False  # Placeholder

        # Ventas caen X%
        elif condition_type == 'sales_drop':
            percentage = self.conditions.get('percentage', 20)
            # Aquí se compararía con período anterior
            logger.info(f"Verificando caída de ventas (>{percentage}%)")
            return False  # Placeholder

        return False

    def _check_condition(self) -> bool:
        """
        Verifica si se cumple la condición general

        Returns:
            bool: True si se cumple
        """
        if not self.conditions:
            return False

        # Implementar lógica de condiciones específicas
        logger.info(f"Verificando condición: {self.conditions}")
        return False  # Placeholder

    def calculate_next_trigger(self):
        """
        Calcula la próxima fecha de ejecución para alertas programadas
        """
        if self.alert_type != 'scheduled' or not self.schedule:
            self.next_trigger = None
            return

        now = timezone.now()

        # Frecuencia diaria
        if self.frequency == 'daily':
            hour = self.schedule.get('hour', 9)
            minute = self.schedule.get('minute', 0)

            next_trigger = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # Si ya pasó hoy, programar para mañana
            if next_trigger <= now:
                from datetime import timedelta
                next_trigger += timedelta(days=1)

            self.next_trigger = next_trigger

        # Frecuencia semanal
        elif self.frequency == 'weekly':
            day_of_week = self.schedule.get('day_of_week', 1)  # 0=lunes
            hour = self.schedule.get('hour', 9)
            minute = self.schedule.get('minute', 0)

            # Calcular próximo día de la semana
            from datetime import timedelta
            days_ahead = day_of_week - now.weekday()
            if days_ahead <= 0:  # Ya pasó esta semana
                days_ahead += 7

            next_trigger = now + timedelta(days=days_ahead)
            next_trigger = next_trigger.replace(hour=hour, minute=minute, second=0, microsecond=0)

            self.next_trigger = next_trigger

        # Frecuencia mensual
        elif self.frequency == 'monthly':
            day_of_month = self.schedule.get('day_of_month', 1)
            hour = self.schedule.get('hour', 9)
            minute = self.schedule.get('minute', 0)

            # Próximo mes, mismo día
            if now.day < day_of_month:
                # Este mes
                next_trigger = now.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
            else:
                # Mes siguiente
                from datetime import timedelta
                import calendar

                # Ir al primer día del próximo mes
                if now.month == 12:
                    next_month = now.replace(year=now.year + 1, month=1, day=1)
                else:
                    next_month = now.replace(month=now.month + 1, day=1)

                # Ajustar día (por si el mes no tiene ese día)
                max_day = calendar.monthrange(next_month.year, next_month.month)[1]
                day = min(day_of_month, max_day)

                next_trigger = next_month.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)

            self.next_trigger = next_trigger

        logger.info(f"Próxima ejecución calculada: {self.next_trigger}")

    def mark_as_triggered(self):
        """
        Marca la alerta como ejecutada y calcula próxima ejecución
        """
        self.last_triggered = timezone.now()

        # Recalcular próxima ejecución si es programada
        if self.alert_type == 'scheduled':
            self.calculate_next_trigger()

        self.save()
        logger.info(f"Alerta ejecutada: {self}")

    def get_recipient_email(self):
        """
        Obtiene el email del destinatario

        Returns:
            str: Email destino
        """
        return self.email_recipient or self.user.email


class AlertExecutionLog(models.Model):
    """
    Log de ejecuciones de alertas
    """
    alert = models.ForeignKey(VoiceCommandAlert, on_delete=models.CASCADE, related_name='executions')
    executed_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, null=True)
    report_generated = models.JSONField(null=True, blank=True, help_text="Datos del reporte generado")

    class Meta:
        ordering = ['-executed_at']
        verbose_name = 'Log de Ejecución de Alerta'
        verbose_name_plural = 'Logs de Ejecución de Alertas'

    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} {self.alert} - {self.executed_at.strftime('%d/%m/%Y %H:%M')}"
