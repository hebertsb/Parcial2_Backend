# sales/filters_audit.py
"""
Filtros personalizados para el sistema de auditoría usando django-filters.
Estos filtros reemplazan el filtrado manual en las vistas.
"""

import django_filters
from django.db.models import Q
from .models_audit import AuditLog, UserSession


class AuditLogFilter(django_filters.FilterSet):
    """
    Filtro personalizado para AuditLog.
    
    Filtros disponibles:
    - user: Busca por username (case-insensitive)
    - action_type: Filtra por uno o varios tipos de acción
    - severity: Filtra por uno o varios niveles de severidad
    - success: Filtra por éxito/error
    - http_method: Filtra por método HTTP
    - start_date / end_date: Rango de fechas
    - ip_address: Busca por IP (contains)
    - endpoint: Busca por endpoint (contains)
    - search: Búsqueda global en endpoint, username, action_description
    - ordering: Ordenamiento por campos
    """
    
    # Filtro por usuario (busca en username)
    user = django_filters.CharFilter(
        field_name='username',
        lookup_expr='icontains',
        label='Usuario',
        help_text='Buscar por nombre de usuario (no distingue mayúsculas/minúsculas)'
    )
    
    # Filtro por tipo de acción (permite múltiples valores)
    action_type = django_filters.MultipleChoiceFilter(
        choices=AuditLog.ACTION_TYPES,
        label='Tipo de acción',
        help_text='Filtrar por uno o varios tipos de acción'
    )
    
    # Filtro por nivel de severidad (permite múltiples valores)
    severity = django_filters.MultipleChoiceFilter(
        choices=AuditLog.SEVERITY_LEVELS,
        label='Severidad',
        help_text='Filtrar por uno o varios niveles de severidad'
    )
    
    # Filtro por éxito/error
    success = django_filters.BooleanFilter(
        field_name='success',
        label='Éxito',
        help_text='Filtrar por operaciones exitosas (true) o fallidas (false)'
    )
    
    # Filtro por método HTTP
    http_method = django_filters.MultipleChoiceFilter(
        choices=[
            ('GET', 'GET'),
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('PATCH', 'PATCH'),
            ('DELETE', 'DELETE'),
            ('OPTIONS', 'OPTIONS'),
            ('HEAD', 'HEAD'),
        ],
        label='Método HTTP',
        help_text='Filtrar por método HTTP'
    )
    
    # Rango de fechas
    start_date = django_filters.DateTimeFilter(
        field_name='timestamp',
        lookup_expr='gte',
        label='Fecha inicio',
        help_text='Fecha/hora de inicio (formato: YYYY-MM-DD HH:MM:SS o YYYY-MM-DD)'
    )
    
    end_date = django_filters.DateTimeFilter(
        field_name='timestamp',
        lookup_expr='lte',
        label='Fecha fin',
        help_text='Fecha/hora de fin (formato: YYYY-MM-DD HH:MM:SS o YYYY-MM-DD)'
    )
    
    # Filtro alternativo: rango de fechas con django_filters.DateFromToRangeFilter
    timestamp_range = django_filters.DateFromToRangeFilter(
        field_name='timestamp',
        label='Rango de fechas',
        help_text='Filtrar por rango de fechas (after=YYYY-MM-DD&before=YYYY-MM-DD)'
    )
    
    # Filtro por dirección IP
    ip_address = django_filters.CharFilter(
        field_name='ip_address',
        lookup_expr='icontains',
        label='Dirección IP',
        help_text='Buscar por dirección IP (contains)'
    )
    
    # Filtro por endpoint
    endpoint = django_filters.CharFilter(
        field_name='endpoint',
        lookup_expr='icontains',
        label='Endpoint',
        help_text='Buscar por endpoint (contains)'
    )
    
    # Filtro por código de estado HTTP
    response_status = django_filters.NumberFilter(
        field_name='response_status',
        label='Código de estado HTTP',
        help_text='Filtrar por código de estado exacto (ej: 200, 404, 500)'
    )
    
    # Filtros por rango de código de estado
    response_status_gte = django_filters.NumberFilter(
        field_name='response_status',
        lookup_expr='gte',
        label='Código de estado >= ',
        help_text='Código de estado mayor o igual'
    )
    
    response_status_lte = django_filters.NumberFilter(
        field_name='response_status',
        lookup_expr='lte',
        label='Código de estado <= ',
        help_text='Código de estado menor o igual'
    )
    
    # Búsqueda global (busca en múltiples campos)
    search = django_filters.CharFilter(
        method='filter_search',
        label='Búsqueda general',
        help_text='Buscar en endpoint, username y descripción de acción'
    )
    
    # Ordenamiento
    ordering = django_filters.OrderingFilter(
        fields=(
            ('timestamp', 'timestamp'),
            ('response_status', 'response_status'),
            ('response_time_ms', 'response_time_ms'),
            ('username', 'username'),
            ('severity', 'severity'),
        ),
        field_labels={
            'timestamp': 'Fecha',
            'response_status': 'Código de respuesta',
            'response_time_ms': 'Tiempo de respuesta',
            'username': 'Usuario',
            'severity': 'Severidad',
        },
        label='Ordenar por',
        help_text='Campos por los que ordenar (usa "-" para descendente, ej: -timestamp)'
    )
    
    class Meta:
        model = AuditLog
        fields = [
            'user',
            'action_type',
            'severity',
            'success',
            'http_method',
            'start_date',
            'end_date',
            'ip_address',
            'endpoint',
            'response_status',
            'search',
        ]
    
    def filter_search(self, queryset, name, value):
        """
        Método personalizado para búsqueda global.
        Busca en endpoint, username y action_description.
        """
        if not value:
            return queryset
        
        return queryset.filter(
            Q(endpoint__icontains=value) |
            Q(username__icontains=value) |
            Q(action_description__icontains=value) |
            Q(ip_address__icontains=value)
        )


class UserSessionFilter(django_filters.FilterSet):
    """
    Filtro personalizado para UserSession.
    
    Filtros disponibles:
    - user: Busca por username
    - is_active: Filtra por sesiones activas/inactivas
    - start_date / end_date: Rango de fechas de login
    - ip_address: Busca por IP
    - search: Búsqueda global
    """
    
    # Filtro por usuario
    user = django_filters.CharFilter(
        field_name='user__username',
        lookup_expr='icontains',
        label='Usuario',
        help_text='Buscar por nombre de usuario'
    )
    
    # Filtro por estado de sesión
    is_active = django_filters.BooleanFilter(
        field_name='is_active',
        label='Sesión activa',
        help_text='Filtrar por sesiones activas (true) o cerradas (false)'
    )
    
    # Rango de fechas de login
    login_start = django_filters.DateTimeFilter(
        field_name='login_time',
        lookup_expr='gte',
        label='Login desde',
        help_text='Fecha de login desde'
    )
    
    login_end = django_filters.DateTimeFilter(
        field_name='login_time',
        lookup_expr='lte',
        label='Login hasta',
        help_text='Fecha de login hasta'
    )
    
    # Filtro por IP
    ip_address = django_filters.CharFilter(
        field_name='ip_address',
        lookup_expr='icontains',
        label='Dirección IP',
        help_text='Buscar por dirección IP'
    )
    
    # Búsqueda global
    search = django_filters.CharFilter(
        method='filter_search',
        label='Búsqueda general',
        help_text='Buscar en username, IP, session_key'
    )
    
    # Ordenamiento
    ordering = django_filters.OrderingFilter(
        fields=(
            ('login_time', 'login_time'),
            ('last_activity', 'last_activity'),
            ('logout_time', 'logout_time'),
        ),
        field_labels={
            'login_time': 'Fecha de login',
            'last_activity': 'Última actividad',
            'logout_time': 'Fecha de logout',
        },
        label='Ordenar por'
    )
    
    class Meta:
        model = UserSession
        fields = [
            'user',
            'is_active',
            'login_start',
            'login_end',
            'ip_address',
            'search',
        ]
    
    def filter_search(self, queryset, name, value):
        """
        Método personalizado para búsqueda global en sesiones.
        """
        if not value:
            return queryset
        
        return queryset.filter(
            Q(user__username__icontains=value) |
            Q(ip_address__icontains=value) |
            Q(session_key__icontains=value)
        )


# Exportar filtros
__all__ = ['AuditLogFilter', 'UserSessionFilter']
