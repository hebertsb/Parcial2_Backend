# sales/views_audit.py
"""
Vistas para consultar y administrar la bitácora de auditoría.
"""

from rest_framework import views, generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count, Q, Max, Min
from django.utils import timezone
from datetime import timedelta
from django_filters.rest_framework import DjangoFilterBackend
from api.permissions import IsAdminUser

from .models_audit import AuditLog, UserSession
from .serializers_audit import AuditLogSerializer, UserSessionSerializer, AuditLogListSerializer
from .filters_audit import AuditLogFilter, UserSessionFilter


class AuditLogPagination(PageNumberPagination):
    """
    Paginación personalizada para logs de auditoría.
    Por defecto muestra 50 registros por página.
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500


class AuditLogListView(generics.ListAPIView):
    """
    GET /api/sales/audit/logs/

    Lista todos los registros de auditoría con filtros avanzados usando django-filters.

    Query params disponibles (filtrado automático):
    - user: Filtrar por username (icontains)
    - action_type: Filtrar por tipo de acción (AUTH, CREATE, READ, etc.) - múltiple
    - start_date: Fecha inicio (YYYY-MM-DD)
    - end_date: Fecha fin (YYYY-MM-DD)
    - severity: Filtrar por severidad (LOW, MEDIUM, HIGH, CRITICAL) - múltiple
    - success: Filtrar por éxito (true/false)
    - http_method: Filtrar por método HTTP (GET, POST, etc.) - múltiple
    - ip_address: Filtrar por IP (icontains)
    - endpoint: Filtrar por endpoint (icontains)
    - response_status: Filtrar por código de estado HTTP exacto
    - response_status_gte: Código de estado mayor o igual
    - response_status_lte: Código de estado menor o igual
    - search: Búsqueda global en endpoint, username, action_description, ip_address
    - ordering: Ordenar por campo (ej: -timestamp, response_time_ms)
    - page: Número de página
    - page_size: Tamaño de página (max: 500)
    """
    queryset = AuditLog.objects.all().order_by('-timestamp')
    serializer_class = AuditLogListSerializer
    permission_classes = [IsAdminUser]
    pagination_class = AuditLogPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = AuditLogFilter


class AuditLogDetailView(generics.RetrieveAPIView):
    """
    GET /api/sales/audit/logs/<id>/

    Obtiene el detalle completo de un registro de auditoría.
    """
    permission_classes = [IsAdminUser]
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.all()


class AuditStatisticsView(views.APIView):
    """
    GET /api/sales/audit/statistics/

    Estadísticas generales de la bitácora.

    Query params:
    - days: Días hacia atrás para analizar (default: 7)
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        days = int(request.query_params.get('days', 7))
        start_date = timezone.now() - timedelta(days=days)

        logs = AuditLog.objects.filter(timestamp__gte=start_date)

        # Estadísticas generales
        total_actions = logs.count()
        total_errors = logs.filter(success=False).count()
        total_users = logs.values('username').distinct().count()

        # Por tipo de acción
        by_action = logs.values('action_type').annotate(
            count=Count('id')
        ).order_by('-count')

        # Por severidad
        by_severity = logs.values('severity').annotate(
            count=Count('id')
        ).order_by('-count')

        # Por día (últimos N días)
        by_day = logs.extra(
            select={'day': 'DATE(timestamp)'}
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day')

        # Usuarios más activos
        top_users = logs.values('username').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        # IPs más activas
        top_ips = logs.values('ip_address').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        # Endpoints más accedidos
        top_endpoints = logs.values('endpoint').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        # Errores recientes
        recent_errors = logs.filter(success=False).order_by('-timestamp')[:10]
        recent_errors_data = AuditLogSerializer(recent_errors, many=True).data

        # Acciones críticas recientes
        critical_actions = logs.filter(severity='CRITICAL').order_by('-timestamp')[:10]
        critical_actions_data = AuditLogSerializer(critical_actions, many=True).data

        return Response({
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'summary': {
                'total_actions': total_actions,
                'total_errors': total_errors,
                'total_users': total_users,
                'error_rate': f"{(total_errors / total_actions * 100) if total_actions > 0 else 0:.2f}%"
            },
            'by_action_type': list(by_action),
            'by_severity': list(by_severity),
            'by_day': list(by_day),
            'top_users': list(top_users),
            'top_ips': list(top_ips),
            'top_endpoints': list(top_endpoints),
            'recent_errors': recent_errors_data,
            'critical_actions': critical_actions_data
        })


class UserActivityView(views.APIView):
    """
    GET /api/sales/audit/user-activity/<username>/

    Actividad detallada de un usuario específico.

    Query params:
    - days: Días hacia atrás (default: 30)
    """
    permission_classes = [IsAdminUser]

    def get(self, request, username):
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        logs = AuditLog.objects.filter(
            username=username,
            timestamp__gte=start_date
        )

        # Estadísticas del usuario
        total_actions = logs.count()
        total_errors = logs.filter(success=False).count()

        # Últimas acciones
        recent_actions = logs.order_by('-timestamp')[:20]
        recent_actions_data = AuditLogSerializer(recent_actions, many=True).data

        # Por tipo de acción
        by_action = logs.values('action_type').annotate(
            count=Count('id')
        ).order_by('-count')

        # IPs usadas
        ips_used = logs.values('ip_address').annotate(
            count=Count('id'),
            last_used=Max('timestamp')
        ).order_by('-last_used')

        # Sesiones activas
        active_sessions = UserSession.objects.filter(
            user__username=username,
            is_active=True
        )
        active_sessions_data = UserSessionSerializer(active_sessions, many=True).data

        return Response({
            'username': username,
            'period': {
                'days': days,
                'start_date': start_date.isoformat()
            },
            'summary': {
                'total_actions': total_actions,
                'total_errors': total_errors,
                'error_rate': f"{(total_errors / total_actions * 100) if total_actions > 0 else 0:.2f}%"
            },
            'recent_actions': recent_actions_data,
            'by_action_type': list(by_action),
            'ips_used': list(ips_used),
            'active_sessions': active_sessions_data
        })


class ActiveSessionsView(generics.ListAPIView):
    """
    GET /api/sales/audit/sessions/active/

    Lista de todas las sesiones activas con filtrado y paginación.
    
    Query params (filtrado automático):
    - user: Filtrar por username
    - ip_address: Filtrar por IP
    - search: Búsqueda global
    - page: Número de página
    - page_size: Tamaño de página
    """
    queryset = UserSession.objects.filter(is_active=True).order_by('-last_activity')
    serializer_class = UserSessionSerializer
    permission_classes = [IsAdminUser]
    pagination_class = AuditLogPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = UserSessionFilter


class SessionHistoryView(generics.ListAPIView):
    """
    GET /api/sales/audit/sessions/history/

    Historial completo de sesiones con filtrado y paginación.

    Query params (filtrado automático):
    - user: Filtrar por username
    - is_active: Filtrar por estado (true/false)
    - login_start: Fecha de login desde
    - login_end: Fecha de login hasta
    - ip_address: Filtrar por IP
    - search: Búsqueda global
    - ordering: Ordenar por campo
    - page: Número de página
    - page_size: Tamaño de página
    """
    queryset = UserSession.objects.all().order_by('-login_time')
    serializer_class = UserSessionSerializer
    permission_classes = [IsAdminUser]
    pagination_class = AuditLogPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = UserSessionFilter


@api_view(['POST'])
@permission_classes([IsAdminUser])
def clean_old_logs(request):
    """
    POST /api/sales/audit/clean-old-logs/

    Elimina logs antiguos para liberar espacio.

    Body:
    {
        "days": 90  // Eliminar logs más antiguos que N días
    }
    """
    days = request.data.get('days', 90)

    if days < 30:
        return Response({
            'error': 'No se pueden eliminar logs de menos de 30 días'
        }, status=status.HTTP_400_BAD_REQUEST)

    cutoff_date = timezone.now() - timedelta(days=days)

    deleted_count = AuditLog.objects.filter(timestamp__lt=cutoff_date).delete()[0]

    return Response({
        'success': True,
        'message': f'Se eliminaron {deleted_count} registros más antiguos que {days} días',
        'cutoff_date': cutoff_date.isoformat()
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def security_alerts(request):
    """
    GET /api/sales/audit/security-alerts/

    Alertas de seguridad basadas en la bitácora.

    Detecta:
    - Múltiples intentos fallidos de login
    - Accesos desde IPs desconocidas
    - Acciones de alta severidad
    - Cambios masivos en corto tiempo
    """
    # Últimas 24 horas
    last_24h = timezone.now() - timedelta(hours=24)

    alerts = []

    # Detectar múltiples intentos fallidos de login con detalles
    failed_logins = AuditLog.objects.filter(
        timestamp__gte=last_24h,
        action_type='AUTH',
        success=False
    ).values('ip_address').annotate(
        count=Count('id')
    ).filter(count__gte=5)

    for item in failed_logins:
        # Alerta resumen por IP
        alerts.append({
            'type': 'failed_login_attempts_summary',
            'severity': 'HIGH',
            'message': f"🔒 IP {item['ip_address']} ha fallado {item['count']} veces al intentar iniciar sesión",
            'ip': item['ip_address'],
            'count': item['count'],
            'recommendation': 'Considerar bloquear esta IP temporalmente'
        })
        
        # Obtener los intentos fallidos específicos de esta IP
        failed_attempts = AuditLog.objects.filter(
            timestamp__gte=last_24h,
            action_type='AUTH',
            success=False,
            ip_address=item['ip_address']
        ).order_by('-timestamp')[:5]  # Últimos 5 intentos
        
        for attempt in failed_attempts:
            alerts.append({
                'type': 'failed_login_detail',
                'severity': 'HIGH',
                'message': f"🔴 Intento fallido: {attempt.action_description}",
                'log_id': attempt.id,
                'ip_address': attempt.ip_address,
                'username_attempted': attempt.username if attempt.username != 'Anónimo' else 'Desconocido',
                'timestamp': attempt.timestamp.isoformat(),
                'endpoint': attempt.endpoint,
                'error_message': attempt.error_message[:200] if attempt.error_message else None,
                'user_agent': attempt.user_agent[:100] if attempt.user_agent else None
            })

    # Detectar acciones críticas y listar cada una con detalles
    critical_actions_queryset = AuditLog.objects.filter(
        timestamp__gte=last_24h,
        severity='CRITICAL'
    ).order_by('-timestamp')

    critical_count = critical_actions_queryset.count()

    if critical_count > 0:
        # Alerta resumen
        alerts.append({
            'type': 'critical_actions_summary',
            'severity': 'CRITICAL',
            'message': f"⚠️ Se han registrado {critical_count} acciones críticas en las últimas 24 horas",
            'count': critical_count,
            'details_below': True
        })
        
        # Agregar cada acción crítica como alerta individual con detalles completos
        for log in critical_actions_queryset[:20]:  # Limitar a las 20 más recientes
            alerts.append({
                'type': 'critical_action_detail',
                'severity': 'CRITICAL',
                'message': f"🔴 {log.action_description}",
                'log_id': log.id,
                'username': log.username,
                'action_type': log.action_type,
                'action_type_display': log.get_action_type_display(),
                'endpoint': log.endpoint,
                'http_method': log.http_method,
                'ip_address': log.ip_address,
                'timestamp': log.timestamp.isoformat(),
                'success': log.success,
                'response_status': log.response_status,
                'error_message': log.error_message if not log.success else None,
                'user_agent': log.user_agent[:100] if log.user_agent else None
            })

    # Detectar accesos desde múltiples IPs por el mismo usuario con detalles
    multi_ip_users = AuditLog.objects.filter(
        timestamp__gte=last_24h
    ).values('username').annotate(
        ip_count=Count('ip_address', distinct=True)
    ).filter(ip_count__gte=3)

    for item in multi_ip_users:
        if item['username'] != 'Anónimo':
            # Obtener las IPs específicas que usó este usuario
            user_ips = AuditLog.objects.filter(
                timestamp__gte=last_24h,
                username=item['username']
            ).values('ip_address').annotate(
                access_count=Count('id'),
                first_seen=Min('timestamp'),
                last_seen=Max('timestamp')
            ).order_by('-access_count')
            
            ip_list = []
            for ip_data in user_ips:
                ip_list.append({
                    'ip': ip_data['ip_address'],
                    'accesses': ip_data['access_count'],
                    'first_seen': ip_data['first_seen'].isoformat(),
                    'last_seen': ip_data['last_seen'].isoformat()
                })
            
            alerts.append({
                'type': 'multiple_ips_summary',
                'severity': 'MEDIUM',
                'message': f"⚠️ Usuario {item['username']} ha accedido desde {item['ip_count']} IPs diferentes en las últimas 24h",
                'username': item['username'],
                'ip_count': item['ip_count'],
                'ips_used': ip_list,
                'recommendation': 'Verificar si el usuario está compartiendo credenciales o si su cuenta fue comprometida'
            })
    
    # Detectar errores de servidor (5xx) recientes
    server_errors = AuditLog.objects.filter(
        timestamp__gte=last_24h,
        response_status__gte=500,
        response_status__lt=600
    ).order_by('-timestamp')[:10]
    
    if server_errors.count() > 0:
        alerts.append({
            'type': 'server_errors_summary',
            'severity': 'HIGH',
            'message': f"🔥 Se detectaron {server_errors.count()} errores de servidor (5xx) en las últimas 24h",
            'count': server_errors.count(),
            'recommendation': 'Revisar logs del servidor y verificar estabilidad del sistema'
        })
        
        for error in server_errors[:5]:  # Mostrar los 5 más recientes
            alerts.append({
                'type': 'server_error_detail',
                'severity': 'HIGH',
                'message': f"🔥 Error {error.response_status}: {error.endpoint}",
                'log_id': error.id,
                'endpoint': error.endpoint,
                'http_method': error.http_method,
                'response_status': error.response_status,
                'username': error.username,
                'timestamp': error.timestamp.isoformat(),
                'error_message': error.error_message[:200] if error.error_message else 'Sin detalles'
            })
    
    # Detectar acciones DELETE (eliminaciones) recientes
    delete_actions = AuditLog.objects.filter(
        timestamp__gte=last_24h,
        action_type='DELETE'
    ).order_by('-timestamp')[:10]
    
    delete_count = AuditLog.objects.filter(
        timestamp__gte=last_24h,
        action_type='DELETE'
    ).count()
    
    if delete_count >= 5:  # Si hay 5 o más eliminaciones
        alerts.append({
            'type': 'delete_actions_summary',
            'severity': 'MEDIUM',
            'message': f"🗑️ Se registraron {delete_count} eliminaciones en las últimas 24h",
            'count': delete_count,
            'recommendation': 'Verificar que las eliminaciones sean intencionadas'
        })
        
        for delete_log in delete_actions[:5]:
            alerts.append({
                'type': 'delete_action_detail',
                'severity': 'MEDIUM',
                'message': f"🗑️ {delete_log.username} eliminó: {delete_log.action_description}",
                'log_id': delete_log.id,
                'username': delete_log.username,
                'endpoint': delete_log.endpoint,
                'timestamp': delete_log.timestamp.isoformat(),
                'success': delete_log.success
            })
    
    # Detectar acciones masivas de un solo usuario (posible automatización/script)
    user_action_counts = AuditLog.objects.filter(
        timestamp__gte=last_24h
    ).values('username').annotate(
        action_count=Count('id')
    ).filter(action_count__gte=100).order_by('-action_count')  # Más de 100 acciones
    
    for user_data in user_action_counts:
        if user_data['username'] != 'Anónimo':
            alerts.append({
                'type': 'high_activity_user',
                'severity': 'LOW',
                'message': f"📊 Usuario {user_data['username']} realizó {user_data['action_count']} acciones en 24h",
                'username': user_data['username'],
                'action_count': user_data['action_count'],
                'recommendation': 'Actividad inusualmente alta - verificar si es comportamiento normal o automatización'
            })

    return Response({
        'total_alerts': len(alerts),
        'alerts': alerts,
        'period': '24 horas',
        'alert_types': {
            'CRITICAL': len([a for a in alerts if a.get('severity') == 'CRITICAL']),
            'HIGH': len([a for a in alerts if a.get('severity') == 'HIGH']),
            'MEDIUM': len([a for a in alerts if a.get('severity') == 'MEDIUM']),
            'LOW': len([a for a in alerts if a.get('severity') == 'LOW'])
        }
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def check_current_session(request):
    """
    GET /api/sales/audit/check-session/
    
    Endpoint de prueba para verificar si la sesión actual está siendo detectada.
    Retorna información detallada sobre el usuario y su sesión.
    """
    import hashlib
    
    response_data = {
        'authenticated': False,
        'user_info': None,
        'session_info': None,
        'request_info': None,
        'registered_session': None
    }
    
    # Información del usuario
    if request.user and request.user.is_authenticated:
        response_data['authenticated'] = True
        response_data['user_info'] = {
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'is_staff': request.user.is_staff,
            'is_superuser': request.user.is_superuser
        }
        
        # Información de la sesión de Django
        if hasattr(request, 'session'):
            if not request.session.session_key:
                request.session.create()
            
            response_data['session_info'] = {
                'session_key': request.session.session_key,
                'has_session': True,
                'session_empty': request.session.is_empty()
            }
        else:
            response_data['session_info'] = {
                'has_session': False,
                'jwt_auth': True,
                'note': 'Usando autenticación JWT (sin sesión tradicional)'
            }
        
        # Información de la petición
        ip_address = AuditLog._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        response_data['request_info'] = {
            'ip_address': ip_address,
            'user_agent': user_agent[:100],
            'method': request.method,
            'path': request.path
        }
        
        # Buscar sesión registrada en UserSession
        # Intentar con session_key de Django primero
        session_key = None
        if hasattr(request, 'session') and request.session.session_key:
            session_key = request.session.session_key
        else:
            # Si es JWT, generar el mismo hash que el middleware
            session_key = hashlib.md5(
                f"{request.user.id}_{ip_address}_{user_agent[:50]}".encode()
            ).hexdigest()
        
        # Buscar en la base de datos
        user_session = UserSession.objects.filter(
            session_key=session_key,
            is_active=True
        ).first()
        
        if user_session:
            response_data['registered_session'] = {
                'found': True,
                'id': user_session.id,
                'session_key': user_session.session_key,
                'login_time': user_session.login_time,
                'last_activity': user_session.last_activity,
                'ip_address': user_session.ip_address,
                'duration_minutes': (timezone.now() - user_session.login_time).total_seconds() // 60
            }
        else:
            response_data['registered_session'] = {
                'found': False,
                'message': 'No se encontró sesión registrada. El middleware debería crearla en la próxima petición.',
                'searched_key': session_key[:30] + '...'
            }
        
        # Todas las sesiones activas del usuario
        all_sessions = UserSession.objects.filter(
            user=request.user,
            is_active=True
        ).count()
        
        response_data['user_active_sessions'] = all_sessions
    
    return Response(response_data)
