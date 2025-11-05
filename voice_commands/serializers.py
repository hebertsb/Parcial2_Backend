from rest_framework import serializers
from .models import VoiceCommand, VoiceCommandHistory


class VoiceCommandHistorySerializer(serializers.ModelSerializer):
    """Serializer para el historial de comandos"""
    
    class Meta:
        model = VoiceCommandHistory
        fields = ['id', 'stage', 'message', 'data', 'timestamp']
        read_only_fields = fields


class VoiceCommandSerializer(serializers.ModelSerializer):
    """Serializer para comandos de texto inteligentes"""
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    history = VoiceCommandHistorySerializer(many=True, read_only=True)
    
    class Meta:
        model = VoiceCommand
        fields = [
            'id', 'user', 'user_username', 'command_text',
            'status', 'command_type', 'interpreted_params', 'result_data',
            'error_message', 'processing_time_ms', 'confidence_score',
            'created_at', 'updated_at', 'history'
        ]
        read_only_fields = [
            'id', 'user', 'status', 'command_type',
            'interpreted_params', 'result_data', 'error_message',
            'processing_time_ms', 'confidence_score',
            'created_at', 'updated_at'
        ]


class VoiceCommandTextSerializer(serializers.Serializer):
    """Serializer para procesar comandos de texto"""
    
    text = serializers.CharField(
        required=True,
        max_length=1000,
        help_text='Comando de texto en lenguaje natural'
    )
