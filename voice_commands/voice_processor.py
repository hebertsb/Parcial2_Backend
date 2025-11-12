"""
Procesador de comandos de texto inteligentes - Versión 2.0 Mejorada
Interpreta texto en lenguaje natural y ejecuta acciones
"""
import logging
import re
from typing import Dict, Any
from django.utils import timezone

# Importar el nuevo parser unificado
from sales.unified_command_parser import parse_command, get_available_reports

# Importar el dispatcher de reportes
from voice_commands.report_dispatcher import ReportDispatcher

logger = logging.getLogger(__name__)


class VoiceCommandProcessor:
    """
    Procesa comandos de texto inteligentes y ejecuta la acción correspondiente
    Versión mejorada con mejor interpretación y manejo de errores
    """
    
    def __init__(self, user):
        """
        Inicializa el procesador con el usuario que ejecuta el comando
        
        Args:
            user: Usuario de Django que ejecuta el comando
        """
        self.user = user
    
    def process_command(self, text: str) -> Dict[str, Any]:
        """
        Procesa un comando de texto y devuelve el resultado
        
        Args:
            text: Texto del comando en lenguaje natural
        
        Returns:
            Dict con el resultado del comando:
            {
                'success': bool,
                'command_type': str,
                'params': dict,
                'result': dict o None,
                'error': str o None,
                'confidence': float,
                'suggestions': list
            }
        """
        
        try:
            # Normalizar el texto
            text = self.normalize_text(text)
            
            logger.info(f"� Procesando comando: '{text}'")
            
            # Parsear el comando con el nuevo sistema unificado
            parsed = parse_command(text)
            
            if not parsed['success']:
                return {
                    'success': False,
                    'command_type': 'error',
                    'params': {},
                    'result': None,
                    'error': parsed.get('error', 'No se pudo procesar el comando'),
                    'confidence': 0.0,
                    'suggestions': []
                }
            
            # Verificar nivel de confianza
            if parsed['confidence'] < 0.3:
                return {
                    'success': False,
                    'command_type': 'low_confidence',
                    'params': parsed['params'],
                    'result': None,
                    'error': f"No estoy seguro de haber entendido el comando. ¿Quisiste decir '{parsed['report_name']}'?",
                    'confidence': parsed['confidence'],
                    'suggestions': parsed['suggestions']
                }
            
            logger.info(f"✅ Comando interpretado: {parsed['report_name']} (confianza: {parsed['confidence']:.2%})")
            
            # Identificar el tipo de comando
            command_type = self._identify_command_type(text, parsed)
            
            if command_type == 'ayuda':
                return self.process_help_command()
            elif command_type == 'listar_reportes':
                return self.process_list_reports_command()
            else:
                # Procesar como reporte
                return self.process_report_command(parsed)
                
        except Exception as e:
            logger.error(f"❌ Error al procesar comando: {e}", exc_info=True)
            return {
                'success': False,
                'command_type': 'error',
                'params': {},
                'result': None,
                'error': f"Error inesperado: {str(e)}",
                'confidence': 0.0,
                'suggestions': []
            }
    
    def normalize_text(self, text: str) -> str:
        """
        Normaliza el texto: minúsculas, elimina espacios extras
        """
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)  # Múltiples espacios a uno
        return text
    
    def _identify_command_type(self, text: str, parsed: Dict) -> str:
        """
        Identifica el tipo de comando basándose en palabras clave
        
        Returns:
            'reporte', 'ayuda', 'listar_reportes'
        """
        text_lower = text.lower()
        
        # Comandos de ayuda
        if any(word in text_lower for word in ['ayuda', 'help', 'cómo', 'como', 'qué puedo', 'que puedo']):
            return 'ayuda'
        
        # Listar reportes disponibles
        if any(phrase in text_lower for phrase in ['listar reportes', 'que reportes', 'qué reportes', 'reportes disponibles']):
            return 'listar_reportes'
        
        # Por defecto es un reporte
        return 'reporte'
    
    def process_report_command(self, parsed: Dict) -> Dict[str, Any]:
        """
        Procesa un comando de generación de reporte usando el resultado del parser.
        Ahora conectado con generadores REALES de reportes.
        """
        
        try:
            report_type = parsed['report_type']
            params = parsed['params']
            
            logger.info(f"📊 Generando reporte: {parsed['report_name']}")
            logger.info(f"📅 Período: {params.get('period_text', 'No especificado')}")
            logger.info(f"📄 Formato: {parsed['format']}")
            
            # ✅ GENERAR REPORTE REAL usando el dispatcher
            try:
                dispatcher = ReportDispatcher(user=self.user)
                real_data = dispatcher.dispatch(report_type, params)
                
                logger.info(f"✅ Reporte '{report_type}' generado exitosamente")
                
            except Exception as e:
                logger.error(f"❌ Error al generar reporte con dispatcher: {e}", exc_info=True)
                # Si falla el generador, retornamos un error descriptivo
                return {
                    'success': False,
                    'command_type': 'reporte',
                    'params': self._serialize_params(params),
                    'result': None,
                    'error': f"Error al generar el reporte: {str(e)}",
                    'confidence': parsed['confidence'],
                    'suggestions': []
                }
            
            # Combinar metadata del parser + datos reales del generador
            result_data = {
                'report_info': {
                    'name': parsed['report_name'],
                    'description': parsed['description'],
                    'type': report_type,
                    'format': parsed['format'],
                    'generated_at': timezone.now().isoformat(),
                    'generated_by': self.user.username
                },
                'parameters': {
                    'date_range': {
                        'start': params.get('start_date').isoformat() if params.get('start_date') else None,
                        'end': params.get('end_date').isoformat() if params.get('end_date') else None,
                        'description': params.get('period_text', 'No especificado')
                    },
                    'group_by': params.get('group_by'),
                    'limit': params.get('limit', 10),
                    'supports_ml': params.get('supports_ml', False)
                },
                'data': real_data,  # ✅ DATOS REALES del generador
                'metadata': {
                    'command_confidence': parsed['confidence'],
                    'total_records': self._count_records(real_data)
                }
            }
            
            # Si el formato cambió, notificar
            if params.get('format_changed'):
                result_data['warnings'] = [
                    f"El formato '{params['original_format']}' no está disponible para este reporte. Se usará '{parsed['format']}' en su lugar."
                ]
            
            return {
                'success': True,
                'command_type': 'reporte',
                'params': {
                    'report_type': report_type,
                    'parsed_params': self._serialize_params(params),
                    'original_command': parsed.get('original_command', '')
                },
                'result': result_data,
                'error': None,
                'confidence': parsed['confidence'],
                'suggestions': parsed['suggestions']
            }
            
        except Exception as e:
            logger.error(f"❌ Error al procesar comando de reporte: {e}", exc_info=True)
            return {
                'success': False,
                'command_type': 'reporte',
                'params': parsed.get('params', {}),
                'result': None,
                'error': f"Error al procesar el comando: {str(e)}",
                'confidence': parsed.get('confidence', 0.0),
                'suggestions': []
            }
    
    def _serialize_params(self, params: Dict) -> Dict:
        """
        Convierte parámetros a formato serializable (para JSON).
        Convierte objetos datetime a strings ISO.
        """
        serializable_params = {}
        for key, value in params.items():
            if hasattr(value, 'isoformat'):  # Es un objeto datetime
                serializable_params[key] = value.isoformat()
            else:
                serializable_params[key] = value
        return serializable_params
    
    def _count_records(self, data: Dict) -> int:
        """
        Cuenta el número de registros en los datos del reporte.
        Útil para metadata.
        """
        try:
            if isinstance(data, dict):
                # Intentar diferentes estructuras
                if 'rows' in data:
                    return len(data['rows'])
                elif 'data' in data and isinstance(data['data'], list):
                    return len(data['data'])
                elif 'predictions' in data and isinstance(data['predictions'], list):
                    return len(data['predictions'])
                elif 'recommendations' in data and isinstance(data['recommendations'], list):
                    return len(data['recommendations'])
            return 0
        except:
            return 0
    
    def process_help_command(self) -> Dict[str, Any]:
        """
        Procesa un comando de ayuda
        """
        
        help_text = """
**🤖 Sistema de Comandos Inteligentes - Ayuda**

**📊 TIPOS DE REPORTES DISPONIBLES:**

**Reportes Básicos:**
- Ventas generales
- Ventas por producto
- Ventas por cliente
- Ventas por categoría
- Ventas por fecha

**Reportes Avanzados:**
- Análisis RFM de clientes (segmentación VIP, Regular, En Riesgo)
- Análisis ABC de productos (clasificación Pareto)
- Dashboard ejecutivo (KPIs y métricas)
- Análisis de inventario
- Reportes comparativos

**Reportes con Machine Learning:**
- Predicciones de ventas futuras
- Predicciones por producto
- Sistema de recomendaciones
- Dashboard ML completo

**📅 FORMAS DE ESPECIFICAR FECHAS:**
- "hoy", "ayer"
- "esta semana", "este mes", "este año"
- "último mes", "mes pasado", "último año"
- "últimos 7 días", "últimos 30 días"
- "mes de octubre", "mes de diciembre"
- "año 2024", "del año 2023"
- "del 01/10/2024 al 18/10/2024"

**📄 FORMATOS DE SALIDA (descargas disponibles):**
- PDF - Agregar "en PDF"
- Excel - Agregar "en Excel"
- Word - Agregar "en Word" o "en DOCX"

**💡 EJEMPLOS DE COMANDOS:**
✓ "reporte de ventas del último mes en PDF"
✓ "productos más vendidos esta semana"
✓ "dashboard ejecutivo de octubre"
✓ "predicciones de ventas para los próximos 7 días"
✓ "análisis RFM de clientes en Excel"
✓ "ventas por cliente del año 2024"
✓ "top 5 productos de esta semana"

**🎯 CONSEJOS:**
- Sé específico con las fechas
- Indica el formato de salida si lo deseas
- Usa lenguaje natural, el sistema te entenderá
- Si no estás seguro, pide "listar reportes disponibles"
"""
        
        return {
            'success': True,
            'command_type': 'ayuda',
            'params': {},
            'result': {'help_text': help_text},
            'error': None,
            'confidence': 1.0,
            'suggestions': []
        }
    
    def process_list_reports_command(self) -> Dict[str, Any]:
        """
        Lista todos los reportes disponibles
        """
        
        try:
            catalog = get_available_reports()
            
            return {
                'success': True,
                'command_type': 'listar_reportes',
                'params': {},
                'result': {
                    'catalog': catalog,
                    'total_reports': catalog['total_reports'],
                    'message': f"Hay {catalog['total_reports']} tipos de reportes disponibles"
                },
                'error': None,
                'confidence': 1.0,
                'suggestions': []
            }
            
        except Exception as e:
            logger.error(f"❌ Error al listar reportes: {e}")
            return {
                'success': False,
                'command_type': 'listar_reportes',
                'params': {},
                'result': None,
                'error': str(e),
                'confidence': 0.0,
                'suggestions': []
            }
