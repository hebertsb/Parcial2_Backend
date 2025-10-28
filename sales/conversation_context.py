"""
Sistema de Contexto Conversacional
Permite mantener el contexto de comandos previos para interacciones naturales
"""

from datetime import datetime
from typing import Dict, Optional, List
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class ConversationContext:
    """
    Mantiene el contexto de la conversación del usuario.
    Permite comandos parciales como "ahora en PDF" o "y también por categoría"
    """

    def __init__(self, session_id: str = None):
        """
        Inicializa el contexto de conversación

        Args:
            session_id: ID de sesión único del usuario
        """
        self.session_id = session_id
        self.history: List[Dict] = []
        self.last_command = None
        self.last_params = None
        self.last_report_type = None
        self.last_format = None
        self.created_at = timezone.now()
        self.last_updated = timezone.now()

    def add(self, command: str, params: Dict, report_type: str, format: str = 'json'):
        """
        Agrega un comando al historial de conversación

        Args:
            command: Comando original del usuario
            params: Parámetros extraídos
            report_type: Tipo de reporte identificado
            format: Formato de salida
        """
        entry = {
            'command': command,
            'params': params.copy() if params else {},
            'report_type': report_type,
            'format': format,
            'timestamp': timezone.now()
        }

        self.history.append(entry)
        self.last_command = command
        self.last_params = params.copy() if params else {}
        self.last_report_type = report_type
        self.last_format = format
        self.last_updated = timezone.now()

        # Mantener solo los últimos 10 comandos en historial
        if len(self.history) > 10:
            self.history.pop(0)

        logger.info(f"Contexto actualizado - Comando: {command[:50]}...")

    def is_partial_command(self, command: str) -> bool:
        """
        Detecta si el comando es parcial (requiere contexto previo)

        Args:
            command: Comando a evaluar

        Returns:
            True si es un comando parcial
        """
        # Palabras que indican que es parcial
        partial_indicators = [
            # Cambio de formato
            'en pdf', 'en excel', 'en json', 'ahora en', 'formato',
            'cambiar a', 'convertir a',

            # Cambio de agrupación
            'por producto', 'por cliente', 'por categoria', 'por fecha',
            'y tambien', 'ademas', 'ahora por',

            # Modificación de fechas
            'del mes', 'de la semana', 'del ano',

            # Palabras de continuación
            'ahora', 'tambien', 'ademas', 'igualmente'
        ]

        command_lower = command.lower()

        # Es parcial si:
        # 1. Empieza con indicador de continuación
        if any(command_lower.startswith(indicator) for indicator in ['ahora', 'tambien', 'ademas', 'y ']):
            return True

        # 2. Solo menciona formato sin tipo de reporte
        if any(fmt in command_lower for fmt in ['en pdf', 'en excel', 'en json']) and \
           not any(word in command_lower for word in ['reporte', 'ventas', 'productos', 'clientes', 'inventario', 'dashboard']):
            return True

        # 3. Solo menciona agrupación sin contexto completo
        if any(grp in command_lower for grp in ['por producto', 'por cliente', 'por categoria']) and \
           len(command_lower.split()) <= 4:  # Comando muy corto
            return True

        return False

    def merge_with_previous(self, partial_command: str) -> Optional[Dict]:
        """
        Fusiona un comando parcial con el contexto previo

        Args:
            partial_command: Comando parcial del usuario

        Returns:
            Dict con parámetros combinados o None si no hay contexto previo
        """
        if not self.last_params:
            logger.warning("No hay contexto previo para fusionar")
            return None

        command_lower = partial_command.lower()
        merged_params = self.last_params.copy()
        merged_report_type = self.last_report_type
        merged_format = self.last_format

        # ESTRATEGIA 1: Cambio de formato
        if any(fmt in command_lower for fmt in ['en pdf', 'en excel', 'en json']):
            if 'pdf' in command_lower:
                merged_format = 'pdf'
            elif 'excel' in command_lower:
                merged_format = 'excel'
            elif 'json' in command_lower:
                merged_format = 'json'

            logger.info(f"Cambio de formato detectado: {self.last_format} → {merged_format}")

            return {
                'params': merged_params,
                'report_type': merged_report_type,
                'format': merged_format,
                'context_used': True,
                'original_command': self.last_command,
                'modification': f"Formato cambiado a {merged_format}"
            }

        # ESTRATEGIA 2: Cambio de agrupación (cambiar tipo de reporte)
        if any(grp in command_lower for grp in ['por producto', 'por cliente', 'por categoria', 'por fecha']):
            # Mantener fechas, cambiar tipo de reporte
            if 'por producto' in command_lower:
                merged_report_type = 'ventas_por_producto'
            elif 'por cliente' in command_lower:
                merged_report_type = 'ventas_por_cliente'
            elif 'por categoria' in command_lower:
                merged_report_type = 'ventas_por_categoria'
            elif 'por fecha' in command_lower:
                merged_report_type = 'ventas_por_fecha'

            logger.info(f"Cambio de agrupación: {self.last_report_type} → {merged_report_type}")

            return {
                'params': merged_params,
                'report_type': merged_report_type,
                'format': merged_format,
                'context_used': True,
                'original_command': self.last_command,
                'modification': f"Agrupación cambiada a {merged_report_type}"
            }

        # ESTRATEGIA 3: Modificación de fechas
        # "del mes de octubre" → mantener tipo, cambiar fechas
        if any(month in command_lower for month in ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                                                      'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']):
            # Se necesitará re-parsear las fechas, pero mantener tipo de reporte
            return {
                'params': {},  # Las fechas se extraerán del nuevo comando
                'report_type': merged_report_type,
                'format': merged_format,
                'context_used': True,
                'original_command': self.last_command,
                'modification': "Fechas actualizadas",
                'reparse_dates': True
            }

        # Si no se pudo fusionar de forma específica
        logger.warning(f"No se pudo determinar cómo fusionar: {partial_command}")
        return None

    def get_suggestion(self) -> Optional[str]:
        """
        Genera una sugerencia de próximo comando basado en el historial

        Returns:
            Sugerencia de comando o None
        """
        if not self.last_report_type:
            return None

        suggestions_map = {
            'ventas_basico': [
                "Ver por producto",
                "Ver por cliente",
                "Ver por categoría",
                "Comparar con mes anterior"
            ],
            'ventas_por_producto': [
                "Ver top 10",
                "Ver por categoría",
                "Exportar en PDF"
            ],
            'ventas_por_cliente': [
                "Ver top 5 clientes",
                "Análisis RFM",
                "Exportar en Excel"
            ],
            'comparativo_temporal': [
                "Ver productos más vendidos",
                "Ver por categoría",
                "Análisis de tendencia"
            ]
        }

        suggestions = suggestions_map.get(self.last_report_type, [])
        return suggestions[0] if suggestions else None

    def clear(self):
        """
        Limpia el contexto de conversación
        """
        self.history.clear()
        self.last_command = None
        self.last_params = None
        self.last_report_type = None
        self.last_format = None
        logger.info("Contexto limpiado")

    def get_summary(self) -> Dict:
        """
        Obtiene un resumen del contexto actual

        Returns:
            Dict con información del contexto
        """
        return {
            'session_id': self.session_id,
            'commands_count': len(self.history),
            'last_command': self.last_command,
            'last_report_type': self.last_report_type,
            'last_format': self.last_format,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }

    def __str__(self):
        return f"ConversationContext(session={self.session_id}, commands={len(self.history)}, last={self.last_report_type})"

    def __repr__(self):
        return self.__str__()


# Diccionario global para mantener contextos por sesión
_contexts = {}


def get_context(session_id: str) -> ConversationContext:
    """
    Obtiene o crea un contexto de conversación para una sesión

    Args:
        session_id: ID único de sesión

    Returns:
        ConversationContext para la sesión
    """
    if session_id not in _contexts:
        _contexts[session_id] = ConversationContext(session_id)
        logger.info(f"Nuevo contexto creado para sesión: {session_id}")
    return _contexts[session_id]


def clear_context(session_id: str):
    """
    Limpia el contexto de una sesión específica

    Args:
        session_id: ID de sesión a limpiar
    """
    if session_id in _contexts:
        _contexts[session_id].clear()
        del _contexts[session_id]
        logger.info(f"Contexto eliminado para sesión: {session_id}")


def clear_all_contexts():
    """
    Limpia todos los contextos (útil para testing)
    """
    _contexts.clear()
    logger.info("Todos los contextos eliminados")
