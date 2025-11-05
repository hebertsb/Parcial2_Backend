from django.contrib import admin
from .models import VoiceCommand, VoiceCommandHistory


class VoiceCommandHistoryInline(admin.TabularInline):
    model = VoiceCommandHistory
    extra = 0
    readonly_fields = ['stage', 'message', 'data', 'timestamp']
    can_delete = False


@admin.register(VoiceCommand)
class VoiceCommandAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'command_type', 'status', 'confidence_score', 'created_at']
    list_filter = ['status', 'command_type', 'created_at']
    search_fields = ['user__username', 'command_text', 'command_type']
    readonly_fields = [
        'user', 'command_text', 'status', 
        'command_type', 'interpreted_params', 'result_data', 
        'error_message', 'processing_time_ms', 
        'confidence_score', 'created_at', 'updated_at'
    ]
    inlines = [VoiceCommandHistoryInline]
    
    fieldsets = (
        ('Información del Usuario', {
            'fields': ('user', 'created_at', 'updated_at')
        }),
        ('Comando de Texto', {
            'fields': ('command_text', 'confidence_score')
        }),
        ('Interpretación del Comando', {
            'fields': ('status', 'command_type', 'interpreted_params', 'processing_time_ms')
        }),
        ('Resultado', {
            'fields': ('result_data', 'error_message')
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(VoiceCommandHistory)
class VoiceCommandHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'voice_command', 'stage', 'timestamp']
    list_filter = ['stage', 'timestamp']
    search_fields = ['voice_command__id', 'message', 'stage']
    readonly_fields = ['voice_command', 'stage', 'message', 'data', 'timestamp']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
