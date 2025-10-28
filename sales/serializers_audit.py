# sales/serializers_audit.py
"""
Serializers para el sistema de auditoría.
"""

from rest_framework import serializers
from .models_audit import AuditLog, UserSession


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer para registros de auditoría.
    """
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user',
            'username',
            'action_type',
            'action_type_display',
            'action_description',
            'http_method',
            'endpoint',
            'query_params',
            'request_body',
            'response_status',
            'response_time_ms',
            'success',
            'error_message',
            'ip_address',
            'user_agent',
            'severity',
            'severity_display',
            'additional_data',
            'timestamp',
        ]
        read_only_fields = fields


class AuditLogListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listados (menos campos).
    """
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'username',
            'action_type_display',
            'action_description',
            'endpoint',
            'response_status',
            'success',
            'ip_address',
            'severity_display',
            'timestamp',
        ]


class UserSessionSerializer(serializers.ModelSerializer):
    """
    Serializer para sesiones de usuario.
    """
    username = serializers.CharField(source='user.username', read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = UserSession
        fields = [
            'id',
            'user',
            'username',
            'session_key',
            'ip_address',
            'user_agent',
            'login_time',
            'last_activity',
            'logout_time',
            'is_active',
            'duration_minutes',
        ]
        read_only_fields = fields
