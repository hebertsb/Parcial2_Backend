# sales/audit_report_generator.py
"""
Generador de Reportes de Auditoría con Filtros Dinámicos
Permite generar reportes de bitácora en PDF y Excel con filtros avanzados.
"""

from django.utils import timezone
from datetime import datetime, timedelta
from .models_audit import AuditLog, UserSession


class AuditReportGenerator:
    """
    Generador de reportes de auditoría con filtros dinámicos.
    """

    def __init__(self, filters):
        """
        Inicializa el generador con filtros.

        Args:
            filters (dict): Diccionario con filtros:
                - user: username
                - action_type: tipo de acción
                - start_date: fecha inicio
                - end_date: fecha fin
                - severity: nivel de severidad
                - success: éxito/error
                - ip_address: IP del cliente
                - endpoint: endpoint específico
        """
        self.filters = filters
        self.report_data = {
            'title': '',
            'subtitle': '',
            'headers': [],
            'rows': [],
            'totals': {},
            'metadata': {},
            'summary': {}
        }

    def generate(self):
        """
        Genera el reporte de auditoría.

        Returns:
            dict: Datos del reporte
        """
        # Obtener los logs filtrados
        logs = self._get_filtered_logs()

        # Construir el reporte
        self._build_report_data(logs)

        return self.report_data

    def _get_filtered_logs(self):
        """
        Obtiene los logs filtrados según los parámetros.
        """
        queryset = AuditLog.objects.all()

        # Filtro por usuario
        if self.filters.get('user'):
            queryset = queryset.filter(username__icontains=self.filters['user'])

        # Filtro por tipo de acción
        if self.filters.get('action_type'):
            queryset = queryset.filter(action_type=self.filters['action_type'].upper())

        # Filtro por rango de fechas
        if self.filters.get('start_date'):
            if isinstance(self.filters['start_date'], str):
                start_date = timezone.make_aware(datetime.strptime(self.filters['start_date'], '%Y-%m-%d'))
            else:
                start_date = self.filters['start_date']
            queryset = queryset.filter(timestamp__gte=start_date)

        if self.filters.get('end_date'):
            if isinstance(self.filters['end_date'], str):
                end_date = timezone.make_aware(datetime.strptime(self.filters['end_date'], '%Y-%m-%d'))
                end_date = end_date.replace(hour=23, minute=59, second=59)
            else:
                end_date = self.filters['end_date']
            queryset = queryset.filter(timestamp__lte=end_date)

        # Filtro por severidad
        if self.filters.get('severity'):
            queryset = queryset.filter(severity=self.filters['severity'].upper())

        # Filtro por éxito/error
        if self.filters.get('success') is not None:
            queryset = queryset.filter(success=self.filters['success'])

        # Filtro por IP
        if self.filters.get('ip_address'):
            queryset = queryset.filter(ip_address=self.filters['ip_address'])

        # Filtro por endpoint
        if self.filters.get('endpoint'):
            queryset = queryset.filter(endpoint__icontains=self.filters['endpoint'])

        # Limitar a 1000 registros por defecto (para evitar reportes enormes)
        limit = self.filters.get('limit', 1000)
        queryset = queryset.order_by('-timestamp')[:limit]

        return queryset

    def _build_report_data(self, logs):
        """
        Construye la estructura del reporte con los logs.
        """
        # Convertir el queryset a lista para poder hacer operaciones múltiples
        logs_list = list(logs)
        
        # Título
        self.report_data['title'] = 'Reporte de Bitácora de Auditoría'

        # Subtítulo con filtros aplicados
        subtitle_parts = []
        if self.filters.get('user'):
            subtitle_parts.append(f"Usuario: {self.filters['user']}")
        if self.filters.get('action_type'):
            subtitle_parts.append(f"Tipo: {self.filters['action_type']}")
        if self.filters.get('start_date') and self.filters.get('end_date'):
            start = self.filters['start_date']
            end = self.filters['end_date']
            if isinstance(start, str):
                start = datetime.strptime(start, '%Y-%m-%d')
            if isinstance(end, str):
                end = datetime.strptime(end, '%Y-%m-%d')
            subtitle_parts.append(f"Período: {start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}")

        self.report_data['subtitle'] = ' | '.join(subtitle_parts) if subtitle_parts else 'Todos los registros'

        # Headers
        self.report_data['headers'] = [
            'Fecha/Hora',
            'Usuario',
            'Acción',
            'Endpoint',
            'IP',
            'Estado',
            'Tiempo (ms)',
            'Severidad'
        ]

        # Rows
        for log in logs_list:
            timestamp_str = log.timestamp.strftime('%d/%m/%Y %H:%M:%S')
            action_display = log.get_action_type_display()
            status = '✓ Éxito' if log.success else '✗ Error'
            severity_display = log.get_severity_display()

            self.report_data['rows'].append([
                timestamp_str,
                log.username,
                f"{action_display}: {log.action_description[:50]}...",
                log.endpoint,
                log.ip_address,
                status,
                log.response_time_ms or '-',
                severity_display
            ])

        # Calcular totales y estadísticas
        total_logs = len(logs_list)
        total_errors = sum(1 for log in logs_list if not log.success)
        total_success = total_logs - total_errors

        # Por tipo de acción
        action_counts = {}
        for log in logs_list:
            action = log.get_action_type_display()
            action_counts[action] = action_counts.get(action, 0) + 1

        # Por severidad
        severity_counts = {}
        for log in logs_list:
            severity = log.get_severity_display()
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Usuarios únicos
        unique_users = len(set(log.username for log in logs_list))

        # IPs únicas
        unique_ips = len(set(log.ip_address for log in logs_list))

        # Tiempo promedio de respuesta
        response_times = [log.response_time_ms for log in logs_list if log.response_time_ms]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        self.report_data['totals'] = {
            'total_registros': total_logs,
            'total_exitos': total_success,
            'total_errores': total_errors,
            'tasa_error': f"{(total_errors / total_logs * 100) if total_logs > 0 else 0:.2f}%"
        }

        self.report_data['summary'] = {
            'usuarios_unicos': unique_users,
            'ips_unicas': unique_ips,
            'tiempo_promedio_ms': f"{avg_response_time:.0f}",
            'por_accion': action_counts,
            'por_severidad': severity_counts
        }

        # Metadata
        self.report_data['metadata'] = {
            'generado_en': timezone.now().strftime('%d/%m/%Y %H:%M:%S'),
            'filtros_aplicados': self.filters
        }


class AuditSessionReportGenerator:
    """
    Generador de reportes de sesiones de usuarios.
    """

    def __init__(self, filters):
        self.filters = filters
        self.report_data = {
            'title': '',
            'subtitle': '',
            'headers': [],
            'rows': [],
            'totals': {},
            'metadata': {}
        }

    def generate(self):
        """
        Genera el reporte de sesiones.
        """
        sessions = self._get_filtered_sessions()
        self._build_report_data(sessions)
        return self.report_data

    def _get_filtered_sessions(self):
        """
        Obtiene las sesiones filtradas.
        """
        queryset = UserSession.objects.all()

        # Filtro por usuario
        if self.filters.get('user'):
            queryset = queryset.filter(user__username__icontains=self.filters['user'])

        # Filtro por estado (activa/inactiva)
        if self.filters.get('is_active') is not None:
            queryset = queryset.filter(is_active=self.filters['is_active'])

        # Filtro por rango de fechas
        if self.filters.get('start_date'):
            if isinstance(self.filters['start_date'], str):
                start_date = timezone.make_aware(datetime.strptime(self.filters['start_date'], '%Y-%m-%d'))
            else:
                start_date = self.filters['start_date']
            queryset = queryset.filter(login_time__gte=start_date)

        if self.filters.get('end_date'):
            if isinstance(self.filters['end_date'], str):
                end_date = timezone.make_aware(datetime.strptime(self.filters['end_date'], '%Y-%m-%d'))
                end_date = end_date.replace(hour=23, minute=59, second=59)
            else:
                end_date = self.filters['end_date']
            queryset = queryset.filter(login_time__lte=end_date)

        # Limitar resultados
        limit = self.filters.get('limit', 500)
        queryset = queryset.order_by('-login_time')[:limit]

        return queryset

    def _build_report_data(self, sessions):
        """
        Construye el reporte de sesiones.
        """
        # Convertir el queryset a lista para poder hacer operaciones múltiples
        sessions_list = list(sessions)
        
        self.report_data['title'] = 'Reporte de Sesiones de Usuarios'

        subtitle_parts = []
        if self.filters.get('user'):
            subtitle_parts.append(f"Usuario: {self.filters['user']}")
        if self.filters.get('is_active'):
            subtitle_parts.append("Solo sesiones activas")

        self.report_data['subtitle'] = ' | '.join(subtitle_parts) if subtitle_parts else 'Todas las sesiones'

        self.report_data['headers'] = [
            'Usuario',
            'IP',
            'Inicio de Sesión',
            'Última Actividad',
            'Cierre de Sesión',
            'Duración (min)',
            'Estado'
        ]

        for session in sessions_list:
            login_time = session.login_time.strftime('%d/%m/%Y %H:%M')
            last_activity = session.last_activity.strftime('%d/%m/%Y %H:%M')
            logout_time = session.logout_time.strftime('%d/%m/%Y %H:%M') if session.logout_time else '-'
            estado = 'Activa' if session.is_active else 'Cerrada'

            self.report_data['rows'].append([
                session.user.username,
                session.ip_address,
                login_time,
                last_activity,
                logout_time,
                session.duration_minutes(),
                estado
            ])

        # Totales
        total_sessions = len(sessions_list)
        active_sessions = sum(1 for s in sessions_list if s.is_active)
        closed_sessions = total_sessions - active_sessions

        # Duración total
        total_duration = sum(s.duration_minutes() for s in sessions_list)
        avg_duration = total_duration / total_sessions if total_sessions > 0 else 0

        self.report_data['totals'] = {
            'total_sesiones': total_sessions,
            'sesiones_activas': active_sessions,
            'sesiones_cerradas': closed_sessions,
            'duracion_promedio_min': f"{avg_duration:.0f}"
        }

        self.report_data['metadata'] = {
            'generado_en': timezone.now().strftime('%d/%m/%Y %H:%M:%S'),
            'filtros_aplicados': self.filters
        }
