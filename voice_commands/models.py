from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class VoiceCommand(models.Model):
    """
    Almacena comandos de texto inteligentes procesados y su resultado
    """
    
    STATUS_CHOICES = [
        ('PROCESSING', 'Procesando'),
        ('EXECUTED', 'Ejecutado'),
        ('FAILED', 'Fallido'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='text_commands')
    command_text = models.TextField(default='comando sin texto', help_text='Texto del comando ingresado por el usuario')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROCESSING')
    
    # Información del comando interpretado
    command_type = models.CharField(max_length=50, blank=True, null=True, help_text='Tipo de comando: reporte, consulta, etc.')
    interpreted_params = models.JSONField(default=dict, blank=True, help_text='Parámetros extraídos del comando')
    
    # Resultado
    result_data = models.JSONField(default=dict, blank=True, help_text='Datos del reporte generado')
    error_message = models.TextField(blank=True, null=True)
    
    # Metadata
    processing_time_ms = models.IntegerField(null=True, blank=True, help_text='Tiempo de procesamiento en milisegundos')
    confidence_score = models.FloatField(null=True, blank=True, help_text='Confianza en la interpretación del comando (0-1)')
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Comando de Texto'
        verbose_name_plural = 'Comandos de Texto'
    
    def __str__(self):
        return f"{self.user.username} - {self.command_type or 'Sin procesar'} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class VoiceCommandHistory(models.Model):
    """
    Historial de intentos de procesamiento de un comando
    """
    
    voice_command = models.ForeignKey(VoiceCommand, on_delete=models.CASCADE, related_name='history')
    stage = models.CharField(max_length=50, help_text='Etapa del procesamiento')
    message = models.TextField(help_text='Mensaje descriptivo')
    data = models.JSONField(default=dict, blank=True)
    
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['timestamp']
        verbose_name = 'Historial de Comando'
        verbose_name_plural = 'Historial de Comandos'
    
    def __str__(self):
        return f"{self.voice_command.id} - {self.stage} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
