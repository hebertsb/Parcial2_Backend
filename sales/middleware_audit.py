# sales/middleware_audit.py
"""
Middleware de Auditoría
Captura TODAS las peticiones HTTP y las registra en la bitácora automáticamente.
"""

import time
import json
from django.utils.deprecation import MiddlewareMixin
from django.urls import resolve
from .models_audit import AuditLog, UserSession
from django.utils import timezone


class AuditMiddleware(MiddlewareMixin):
    """
    Middleware que intercepta TODAS las peticiones HTTP y las registra en la bitácora.

    Registra:
    - Autenticación (login/logout)
    - Operaciones CRUD
    - Generación de reportes
    - Pagos
    - Cualquier otra acción
    """

    # Endpoints que NO se deben loggear (para evitar spam en la bitácora)
    EXCLUDE_PATHS = [
        '/static/',
        '/media/',
        '/favicon.ico',
        '/admin/jsi18n/',  # Admin translations
    ]
    
    # Métodos HTTP que NO se deben loggear (para evitar spam)
    EXCLUDE_METHODS = ['OPTIONS']  # OPTIONS son preflight CORS, no necesitan logging

    # Mapeo de endpoints a tipos de acción
    ENDPOINT_ACTION_MAP = {
        'login': ('AUTH', 'Inicio de sesión'),
        'logout': ('AUTH', 'Cierre de sesión'),
        'register': ('AUTH', 'Registro de usuario'),
        
        'cart': ('CREATE', 'Operación en carrito de compras'),
        'checkout': ('PAYMENT', 'Proceso de pago'),
        'order': ('CREATE', 'Gestión de órdenes'),
        'report': ('REPORT', 'Generación de reporte'),
        'ml': ('ML', 'Operación de Machine Learning'),
        'predict': ('ML', 'Predicción con ML'),
        'train': ('ML', 'Entrenamiento de modelo ML'),
        'dashboard': ('READ', 'Consulta de dashboard'),
        'product': ('READ', 'Consulta de productos'),
        'sales-history': ('READ', 'Consulta de historial de ventas'),
    }

    def process_request(self, request):
        """
        Se ejecuta antes de procesar la petición.
        Guarda el timestamp de inicio para medir el tiempo de respuesta.
        """
        request._audit_start_time = time.time()
        return None

    def process_response(self, request, response):
        """
        Se ejecuta después de procesar la petición.
        Registra la acción en la bitácora.
        """
        # Verificar si se debe excluir este path o método
        if self._should_exclude(request.path) or request.method in self.EXCLUDE_METHODS:
            return response

        # Calcular tiempo de respuesta
        response_time_ms = None
        if hasattr(request, '_audit_start_time'):
            response_time_ms = int((time.time() - request._audit_start_time) * 1000)

        # Determinar el tipo de acción y descripción
        action_type, description = self._determine_action(request, response)

        # Determinar severidad
        severity = self._determine_severity(request, response)

        # Crear el registro de auditoría
        try:
            # Solo intentar loggear si no es un error de autenticación básico en endpoints públicos
            # Esto evita spam en la bitácora
            if response.status_code == 403 and request.path.startswith('/api/shop/'):
                # Endpoint público con error 403 - probablemente error de configuración
                # No loggear para evitar spam
                return response
            
            AuditLog.log_action(
                user=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                action_type=action_type,
                description=description,
                request=request,
                response=response,
                severity=severity,
                additional_data=self._get_additional_data(request, response),
                response_time_ms=response_time_ms
            )
        except Exception as e:
            # Si falla el logging, no debe romper la aplicación
            print(f"Error al registrar en bitácora: {e}")

        # Actualizar última actividad de la sesión
        if (hasattr(request, 'user') and 
            request.user is not None and 
            hasattr(request.user, 'is_authenticated') and 
            request.user.is_authenticated):
            self._update_session_activity(request)

        return response

    def _should_exclude(self, path):
        """
        Determina si un path debe ser excluido del logging.
        """
        for excluded in self.EXCLUDE_PATHS:
            if path.startswith(excluded):
                return True
        return False

    def _determine_action(self, request, response):
        """
        Determina el tipo de acción y la descripción basándose en el endpoint y método HTTP.

        Returns:
            tuple: (action_type, description)
        """
        path = request.path.lower()
        method = request.method

        # Buscar en el mapeo de endpoints
        for keyword, (action_type, base_description) in self.ENDPOINT_ACTION_MAP.items():
            if keyword in path:
                description = self._build_description(method, base_description, path)
                return action_type, description

        # Acciones basadas en método HTTP si no hay match específico
        if method == 'GET':
            return 'READ', f'Consulta a {path}'
        elif method == 'POST':
            return 'CREATE', f'Creación en {path}'
        elif method in ['PUT', 'PATCH']:
            return 'UPDATE', f'Actualización en {path}'
        elif method == 'DELETE':
            return 'DELETE', f'Eliminación en {path}'
        else:
            return 'OTHER', f'{method} a {path}'

    def _build_description(self, method, base_description, path):
        """
        Construye una descripción detallada de la acción.
        """
        # Extraer detalles adicionales del path
        path_parts = path.split('/')

        # Si hay IDs en el path, agregarlos
        ids = [p for p in path_parts if p.isdigit()]
        if ids:
            base_description += f" (ID: {', '.join(ids)})"

        # Prefijo según el método HTTP
        method_prefix = {
            'GET': 'Consulta',
            'POST': 'Creación',
            'PUT': 'Actualización completa',
            'PATCH': 'Actualización parcial',
            'DELETE': 'Eliminación'
        }.get(method, method)

        return f"{method_prefix}: {base_description}"

    def _determine_severity(self, request, response):
        """
        Determina el nivel de severidad de la acción.
        """
        path = request.path.lower()
        method = request.method
        status_code = response.status_code

        # Crítica: Errores del servidor
        if status_code >= 500:
            return 'CRITICAL'

        # Alta: Operaciones sensibles o errores de cliente
        if any(keyword in path for keyword in ['payment', 'checkout', 'delete', 'admin']):
            return 'HIGH'

        if status_code >= 400:
            return 'HIGH'

        # Media: Operaciones de escritura
        if method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return 'MEDIUM'

        # Baja: Operaciones de lectura exitosas
        return 'LOW'

    def _get_additional_data(self, request, response):
        """
        Recopila datos adicionales relevantes.
        """
        additional_data = {}

        # Intentar obtener el nombre de la vista
        try:
            resolved = resolve(request.path)
            additional_data['view_name'] = resolved.view_name
            if resolved.kwargs:
                additional_data['url_params'] = resolved.kwargs
        except Exception:
            pass

        # Si es una operación de ML, agregar detalles
        if 'ml' in request.path.lower() or 'predict' in request.path.lower():
            additional_data['ml_operation'] = True

        # Si es un reporte, agregar detalles
        if 'report' in request.path.lower():
            additional_data['report_operation'] = True

        # Agregar información de autenticación
        if (hasattr(request, 'user') and 
            request.user is not None and 
            hasattr(request.user, 'is_authenticated') and 
            request.user.is_authenticated):
            try:
                additional_data['user_id'] = request.user.id
                additional_data['is_staff'] = request.user.is_staff
                additional_data['is_superuser'] = request.user.is_superuser
            except Exception:
                pass

        return additional_data if additional_data else None

    def _update_session_activity(self, request):
        """
        Actualiza la última actividad de la sesión del usuario.
        """
        try:
            if hasattr(request, 'session') and request.session.session_key:
                UserSession.objects.filter(
                    session_key=request.session.session_key,
                    is_active=True
                ).update(last_activity=timezone.now())
        except:
            pass


class SessionTrackingMiddleware(MiddlewareMixin):
    """
    Middleware adicional para rastrear sesiones de usuarios.
    Crea registros de sesión en login y los cierra en logout.
    Compatible con JWT y sesiones tradicionales de Django.
    """

    def process_request(self, request):
        """
        Verifica y crea sesiones de usuario.
        Solo procesa para usuarios autenticados.
        Funciona tanto con JWT como con sesiones tradicionales.
        """
        # Verificar que el usuario esté correctamente autenticado
        if (hasattr(request, 'user') and 
            request.user is not None and 
            hasattr(request.user, 'is_authenticated') and 
            request.user.is_authenticated):
            
            # Intentar obtener o crear session_key
            session_key = None
            
            # Opción 1: Sesión tradicional de Django
            if hasattr(request, 'session'):
                # Asegurar que la sesión tenga una key
                if not request.session.session_key:
                    request.session.create()
                session_key = request.session.session_key
            
            # Opción 2: Si no hay sesión pero hay JWT, generar identificador único
            if not session_key:
                # Para JWT, usar una combinación de user_id + IP como identificador
                import hashlib
                ip = self._get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')[:50]
                session_key = hashlib.md5(
                    f"{request.user.id}_{ip}_{user_agent}".encode()
                ).hexdigest()
            
            if session_key:
                self._ensure_session_record(request, session_key)

        return None

    def _ensure_session_record(self, request, session_key):
        """
        Asegura que exista un registro de sesión para el usuario actual.
        Compatible con JWT y sesiones tradicionales.
        """
        try:
            user = request.user

            # Verificar si ya existe una sesión activa para este session_key
            existing_session = UserSession.objects.filter(
                session_key=session_key,
                is_active=True
            ).first()
            
            if not existing_session:
                # Obtener IP
                ip_address = self._get_client_ip(request)

                # User Agent
                user_agent = request.META.get('HTTP_USER_AGENT', '')

                # Crear registro de sesión
                UserSession.objects.create(
                    user=user,
                    session_key=session_key,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                print(f"✅ Nueva sesión creada para {user.username} (key: {session_key[:20]}...)")
            else:
                # Actualizar última actividad de la sesión existente
                existing_session.last_activity = timezone.now()
                existing_session.save(update_fields=['last_activity'])
                
        except Exception as e:
            print(f"❌ Error al crear/actualizar sesión: {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    def _get_client_ip(request):
        """
        Obtiene la IP real del cliente.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip
