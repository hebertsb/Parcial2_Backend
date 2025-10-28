# sales/unified_command_parser.py
"""
Sistema Unificado de Análisis de Comandos Inteligentes
Combina las mejores características de prompt_parser.py e intelligent_report_router.py
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
import logging
import unicodedata

logger = logging.getLogger(__name__)


class UnifiedCommandParser:
    """
    Parser inteligente que interpreta comandos en lenguaje natural y extrae:
    - Tipo de reporte/acción solicitada
    - Formato de salida (JSON, PDF, Excel)
    - Rango de fechas
    - Parámetros de agrupación y filtros
    - Predicciones ML si aplica
    """

    # Catálogo completo de reportes disponibles
    REPORT_CATALOG = {
        'ventas_basico': {
            'name': 'Reporte Básico de Ventas',
            'description': 'Ventas generales sin agrupación específica',
            'keywords': ['ventas general', 'reporte de ventas', 'historial ventas', 'ventas'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'priority': 5
        },
        'ventas_por_producto': {
            'name': 'Ventas por Producto',
            'description': 'Ventas agrupadas por producto con estadísticas',
            'keywords': ['ventas por producto', 'productos vendidos', 'reporte productos', 'por producto', 'producto mas vendido', 'productos mas vendidos', 'cual producto', 'que producto', 'que productos', 'cuales productos', 'producto que mas se vendio', 'productos que mas se vendieron', 'cual fue el producto'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'priority': 9  # Mayor prioridad cuando se pregunta por producto específico
        },
        'ventas_por_cliente': {
            'name': 'Ventas por Cliente',
            'description': 'Ventas agrupadas por cliente',
            'keywords': ['ventas por cliente', 'clientes', 'mejores clientes', 'por cliente', 'compradores', 'cual cliente', 'que cliente', 'quien compro', 'quienes compraron', 'clientes que compraron', 'cliente que mas compro', 'clientes que mas compraron', 'cual fue el cliente'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'priority': 9  # Mayor prioridad para preguntas específicas
        },
        'ventas_por_categoria': {
            'name': 'Ventas por Categoría',
            'description': 'Ventas agrupadas por categoría de producto',
            'keywords': ['ventas por categoria', 'categorias', 'por categoria', 'categoria mas vendida', 'categorias mas vendidas', 'cual categoria', 'que categoria', 'categorias vendidas', 'categoria de producto', 'categoria que mas se vendio', 'categorias que mas se vendieron', 'cual fue la categoria'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'priority': 9  # Mayor prioridad cuando se menciona "categoría"
        },
        'ventas_por_fecha': {
            'name': 'Ventas por Fecha',
            'description': 'Ventas día a día',
            'keywords': ['ventas por fecha', 'ventas diarias', 'por dia', 'por fecha'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'priority': 7
        },
        'analisis_rfm': {
            'name': 'Análisis RFM de Clientes',
            'description': 'Segmentación de clientes (VIP, Regular, En Riesgo)',
            'keywords': ['analisis rfm', 'segmentacion clientes', 'rfm', 'clientes vip', 'segmentar'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'priority': 9
        },
        'analisis_abc': {
            'name': 'Análisis ABC de Productos',
            'description': 'Clasificación de productos por el principio de Pareto',
            'keywords': ['analisis abc', 'pareto', 'clasificacion productos', 'abc'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'priority': 9
        },
        'comparativo_temporal': {
            'name': 'Reporte Comparativo',
            'description': 'Comparación entre dos períodos de tiempo',
            'keywords': ['comparativo', 'comparar periodos', 'comparacion', 'vs', 'versus', 'contra', 'comparado con', 'respecto a', 'respecto al', 'diferencia', 'diferencia entre', 'crecimiento', 'crecimiento de', 'crecimiento respecto', 'evolucion', 'mes a mes', 'ano a ano', 'año a año', 'semana a semana', 'periodo a periodo', 'cambio', 'variacion', 'incremento', 'decremento'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'priority': 9  # Aumentar de 7 a 9 para comparaciones explícitas
        },
        'dashboard_ejecutivo': {
            'name': 'Dashboard Ejecutivo',
            'description': 'KPIs principales y alertas del negocio',
            'keywords': ['dashboard ejecutivo', 'dashboard', 'kpis', 'resumen ejecutivo', 'ejecutivo'],
            'supports_ml': False,
            'formats': ['json'],
            'priority': 8
        },
        'analisis_inventario': {
            'name': 'Análisis de Inventario',
            'description': 'Estado del inventario con rotación y alertas',
            'keywords': ['inventario', 'stock', 'analisis inventario', 'existencias', 'stock bajo', 'bajo stock', 'productos con stock', 'productos con bajo stock', 'que productos tienen stock', 'sin stock', 'poco stock', 'productos sin stock', 'productos con poco stock', 'nivel de stock', 'estado del stock', 'disponibilidad'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'priority': 10  # Aumentar prioridad cuando se pregunta por stock
        },
        'prediccion_ventas': {
            'name': 'Predicción de Ventas (ML)',
            'description': 'Predicciones futuras de ventas usando Machine Learning',
            'keywords': ['prediccion de ventas', 'predicciones de ventas', 'prediccion', 'predicciones', 'forecast', 'pronostico', 'ventas futuras', 'predecir', 'predice', 'proxima semana', 'proximas semanas', 'proximo mes', 'proximos meses'],
            'supports_ml': True,
            'formats': ['json', 'pdf', 'excel'],
            'priority': 10
        },
        'prediccion_producto': {
            'name': 'Predicción por Producto (ML)',
            'description': 'Predicciones de ventas para productos específicos',
            'keywords': ['prediccion producto', 'prediccion por producto', 'forecast producto'],
            'supports_ml': True,
            'formats': ['json'],
            'priority': 10
        },
        'recomendaciones': {
            'name': 'Sistema de Recomendaciones (ML)',
            'description': 'Recomendaciones personalizadas de productos',
            'keywords': ['recomendaciones', 'recomendar', 'sugerencias', 'sugerir'],
            'supports_ml': True,
            'formats': ['json'],
            'priority': 9
        },
        'dashboard_ml': {
            'name': 'Dashboard de Predicciones ML',
            'description': 'Dashboard completo con predicciones y análisis ML',
            'keywords': ['dashboard ml', 'dashboard predicciones', 'ml dashboard', 'machine learning'],
            'supports_ml': True,
            'formats': ['json'],
            'priority': 10
        }
    }

    # Sinónimos extendidos para mejor detección
    SYNONYMS = {
        'reporte': ['informe', 'report', 'reporte', 'reportar', 'genera', 'generar', 'dame', 'mostrar', 'muestra'],
        'ventas': ['venta', 'ventas', 'sale', 'sales', 'orden', 'ordenes', 'order', 'orders', 'vendido', 'vendidos'],
        'producto': ['producto', 'productos', 'product', 'products', 'articulo', 'articulos', 'item', 'items'],
        'cliente': ['cliente', 'clientes', 'client', 'clients', 'usuario', 'usuarios', 'user', 'comprador', 'compradores'],
        'fecha': ['fecha', 'fechas', 'date', 'dates', 'dia', 'dias', 'day', 'days'],
        'categoria': ['categoria', 'categorias', 'category', 'categories'],
    }

    # Meses en español
    MONTHS = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
        'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }

    # Números en palabras (español)
    NUMBER_WORDS = {
        'un': 1, 'uno': 1, 'una': 1,
        'dos': 2,
        'tres': 3,
        'cuatro': 4,
        'cinco': 5,
        'seis': 6,
        'siete': 7,
        'ocho': 8,
        'nueve': 9,
        'diez': 10,
        'once': 11,
        'doce': 12,
        'trece': 13,
        'catorce': 14,
        'quince': 15,
        'dieciseis': 16, 'dieciséis': 16,
        'diecisiete': 17,
        'dieciocho': 18,
        'diecinueve': 19,
        'veinte': 20,
        'veintiuno': 21,
        'veintidos': 22,
        'treinta': 30,
        'cuarenta': 40,
        'cincuenta': 50,
        'sesenta': 60,
        'setenta': 70,
        'ochenta': 80,
        'noventa': 90,
        # Números ordinales para fechas
        'primero': 1, 'primer': 1, 'primera': 1,
        'segundo': 2, 'segunda': 2,
        'tercero': 3, 'tercer': 3, 'tercera': 3,
        'cuarto': 4, 'cuarta': 4,
        'quinto': 5, 'quinta': 5,
        'sexto': 6, 'sexta': 6,
        'septimo': 7, 'septima': 7,
        'octavo': 8, 'octava': 8,
        'noveno': 9, 'novena': 9,
        'decimo': 10, 'decima': 10,
    }

    @staticmethod
    def _remove_accents(text: str) -> str:
        """
        Elimina tildes/acentos del texto para normalización.
        Convierte 'predicción' a 'prediccion', 'días' a 'dias', etc.

        Args:
            text: Texto con posibles acentos

        Returns:
            Texto sin acentos
        """
        # Normalizar a NFD (descompone caracteres acentuados)
        nfd = unicodedata.normalize('NFD', text)
        # Filtrar solo caracteres no-diacríticos (sin tildes)
        return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')

    def __init__(self, command: str):
        """
        Inicializa el parser con un comando de texto

        Args:
            command: Comando en lenguaje natural
        """
        # Normalizar: lowercase, strip, y remover acentos
        self.command = self._remove_accents(command.lower().strip())
        self.original_command = command.strip()
        self.result = {
            'success': True,
            'report_type': None,
            'report_name': None,
            'description': None,
            'format': 'json',
            'params': {},
            'confidence': 0.0,
            'suggestions': [],
            'error': None
        }

    def parse(self) -> Dict:
        """
        Analiza el comando completo y extrae toda la información

        Returns:
            dict: Resultado del análisis con tipo de reporte y parámetros
        """
        try:
            # 1. Identificar el tipo de reporte
            self._identify_report_type()

            # 2. Extraer formato de salida
            self._extract_format()

            # 3. Extraer fechas y rangos (SOLO si NO es un reporte ML de predicciones)
            # Las predicciones ML no usan fechas del pasado, predicen el futuro
            if not self.result['params'].get('supports_ml'):
                self._extract_dates()

            # 4. Extraer agrupación
            self._extract_grouping()

            # 5. Extraer parámetros adicionales
            self._extract_additional_params()

            # 6. Extraer filtros numéricos (top N, mayor/menor a X, entre X y Y)
            self._extract_numeric_filters()

            # 7. Detectar períodos de comparación implícitos (si es comparativo_temporal)
            self._detect_comparison_periods()

            # 8. Detectar si es un comando de alerta/programación
            self._detect_alert_command()

            # 9. Calcular confianza final
            self._calculate_confidence()

            # 10. Validar resultado
            self._validate_result()

            return self.result

        except Exception as e:
            logger.error(f"Error al parsear comando '{self.command}': {e}")
            self.result['success'] = False
            self.result['error'] = f"Error al procesar el comando: {str(e)}"
            return self.result

    def parse_with_context(self, context=None) -> Dict:
        """
        Analiza el comando con soporte de contexto conversacional

        Args:
            context: ConversationContext con historial previo

        Returns:
            dict: Resultado del análisis (puede usar contexto previo)
        """
        if context is None:
            # Sin contexto, parsear normalmente
            return self.parse()

        # Verificar si es un comando parcial que requiere contexto
        if context.is_partial_command(self.command):
            logger.info(f"Comando parcial detectado: {self.command}")

            # Intentar fusionar con contexto previo
            merged = context.merge_with_previous(self.command)

            if merged:
                # Usar parámetros del contexto
                self.result['success'] = True
                self.result['report_type'] = merged['report_type']
                self.result['format'] = merged['format']
                self.result['params'] = merged['params']
                self.result['context_used'] = True
                self.result['original_command'] = merged['original_command']
                self.result['modification'] = merged['modification']

                # Si necesita re-parsear fechas
                if merged.get('reparse_dates'):
                    self._extract_dates()

                # Obtener información del reporte
                report_info = self.REPORT_CATALOG.get(merged['report_type'], {})
                self.result['report_name'] = report_info.get('name', 'Reporte')
                self.result['description'] = report_info.get('description', '')

                # Calcular confianza (más baja porque usa contexto)
                self.result['confidence'] = 0.7

                logger.info(f"Comando parcial fusionado: {merged['modification']}")
                return self.result

        # No es parcial o no se pudo fusionar, parsear normalmente
        return self.parse()

    def _identify_report_type(self):
        """
        Identifica el tipo de reporte basándose en keywords con scoring inteligente
        """
        best_match = None
        best_score = 0
        alternatives = []

        for report_key, report_info in self.REPORT_CATALOG.items():
            score = 0
            
            # Verificar coincidencias de keywords
            for keyword in report_info['keywords']:
                if keyword in self.command:
                    # Dar más peso a keywords más específicas (más largas)
                    keyword_weight = len(keyword.split()) * 2
                    # Bonus si la keyword aparece al principio
                    if self.command.startswith(keyword):
                        keyword_weight *= 1.5
                    score += keyword_weight
            
            # Aplicar prioridad del reporte
            score *= (report_info['priority'] / 10.0)
            
            # Guardar alternativas con puntuación > 0
            if score > 0:
                alternatives.append({
                    'type': report_key,
                    'name': report_info['name'],
                    'score': score,
                    'confidence': min(score / 15.0, 1.0)
                })
            
            # Actualizar mejor match
            if score > best_score:
                best_score = score
                best_match = (report_key, report_info)

        if best_match:
            report_key, report_info = best_match
            self.result['report_type'] = report_key
            self.result['report_name'] = report_info['name']
            self.result['description'] = report_info['description']
            self.result['params']['supports_ml'] = report_info['supports_ml']
            self.result['params']['available_formats'] = report_info['formats']
            
            # Ordenar alternativas por score
            alternatives.sort(key=lambda x: x['score'], reverse=True)
            # Eliminar el match principal de las alternativas
            self.result['suggestions'] = [
                {'name': alt['name'], 'type': alt['type'], 'confidence': alt['confidence']}
                for alt in alternatives if alt['type'] != report_key
            ][:3]
        else:
            # Por defecto: reporte básico de ventas
            self.result['report_type'] = 'ventas_basico'
            self.result['report_name'] = 'Reporte Básico de Ventas'
            self.result['description'] = 'Ventas generales (opción por defecto)'
            self.result['params']['supports_ml'] = False
            self.result['params']['available_formats'] = ['json', 'pdf', 'excel']

    def _extract_format(self):
        """
        Extrae el formato de salida solicitado
        """
        format_keywords = {
            'pdf': ['pdf', 'en pdf', 'formato pdf'],
            'excel': ['excel', 'xls', 'xlsx', 'en excel', 'hoja de calculo', 'spreadsheet'],
            'json': ['json', 'pantalla', 'screen', 'en pantalla', 'datos', 'api']
        }
        
        for format_type, keywords in format_keywords.items():
            for keyword in keywords:
                if keyword in self.command:
                    self.result['format'] = format_type
                    return
        
        # Por defecto JSON
        self.result['format'] = 'json'

    def _extract_dates(self):
        """
        Extrae fechas y rangos de tiempo con múltiples estrategias.
        ORDEN IMPORTANTE: De más específico a más general.
        """
        # ===== ESTRATEGIAS MÁS ESPECÍFICAS (DÍAS EXACTOS) =====

        # Estrategia 0a: "del [palabra] al [palabra] de mes" (ambos números en palabras)
        # Ej: "del primero al quince de octubre", "del primero al diez de octubre"
        range_both_words_pattern = r'del?\s+(\w+)\s+al?\s+(\w+)\s+de\s+(\w+)'
        match = re.search(range_both_words_pattern, self.command)
        if match:
            start_word = match.group(1).lower()
            end_word = match.group(2).lower()
            month_name = match.group(3)

            # Intentar convertir ambas palabras a números
            if start_word in self.NUMBER_WORDS and end_word in self.NUMBER_WORDS:
                start_day = self.NUMBER_WORDS[start_word]
                end_day = self.NUMBER_WORDS[end_word]

                # Determinar mes
                month_num = self.MONTHS.get(month_name, timezone.now().month)
                year = timezone.now().year

                try:
                    start_dt = datetime(year, month_num, start_day, 0, 0, 0)
                    end_dt = datetime(year, month_num, end_day, 23, 59, 59)

                    self.result['params']['start_date'] = timezone.make_aware(start_dt)
                    self.result['params']['end_date'] = timezone.make_aware(end_dt)
                    self.result['params']['period_text'] = f"Del {start_day} al {end_day} de {month_name.title()}"
                    return
                except ValueError:
                    pass  # Fecha inválida

        # Estrategia 0b: "del [palabra] de mes al DD de mes" (inicio en palabra, fin digital)
        # Ej: "del primero de octubre al 19 de octubre", "del primero al 10 de octubre"
        range_word_digit_pattern = r'del?\s+(\w+)(?:\s+de\s+(\w+))?\s+al?\s+(\d{1,2})\s+de\s+(\w+)'
        match = re.search(range_word_digit_pattern, self.command)
        if match:
            start_word = match.group(1).lower()
            start_month_name = match.group(2)
            end_day = int(match.group(3))
            end_month_name = match.group(4)

            # Intentar convertir la palabra a número
            if start_word in self.NUMBER_WORDS:
                start_day = self.NUMBER_WORDS[start_word]

                # Determinar mes de inicio
                if start_month_name and start_month_name in self.MONTHS:
                    start_month_num = self.MONTHS[start_month_name]
                elif end_month_name in self.MONTHS:
                    start_month_num = self.MONTHS[end_month_name]
                else:
                    start_month_num = timezone.now().month

                # Determinar mes de fin
                end_month_num = self.MONTHS.get(end_month_name, timezone.now().month)

                year = timezone.now().year

                try:
                    start_dt = datetime(year, start_month_num, start_day, 0, 0, 0)
                    end_dt = datetime(year, end_month_num, end_day, 23, 59, 59)

                    self.result['params']['start_date'] = timezone.make_aware(start_dt)
                    self.result['params']['end_date'] = timezone.make_aware(end_dt)
                    self.result['params']['period_text'] = f"Del {start_day} al {end_day} de {end_month_name.title()}"
                    return
                except ValueError:
                    pass  # Fecha inválida, continuar con otras estrategias

        # Estrategia 1: "del DD de mes al DD de mes" (rango dentro del mismo mes o entre meses)
        # Ej: "del 3 al 10 de octubre", "del 28 de septiembre al 5 de octubre"
        range_month_pattern = r'del?\s+(\d{1,2})(?:\s+de\s+(\w+))?\s+al?\s+(\d{1,2})\s+de\s+(\w+)'
        match = re.search(range_month_pattern, self.command)
        if match:
            start_day = int(match.group(1))
            start_month_name = match.group(2)  # Puede ser None si no se especifica
            end_day = int(match.group(3))
            end_month_name = match.group(4)

            # Determinar el mes de inicio
            if start_month_name and start_month_name in self.MONTHS:
                start_month_num = self.MONTHS[start_month_name]
            elif end_month_name in self.MONTHS:
                # Si no se especifica mes de inicio, usar el mismo que el final
                start_month_num = self.MONTHS[end_month_name]
            else:
                start_month_num = timezone.now().month

            # Determinar el mes de fin
            end_month_num = self.MONTHS.get(end_month_name, timezone.now().month)

            year = timezone.now().year

            try:
                start_dt = datetime(year, start_month_num, start_day, 0, 0, 0)
                end_dt = datetime(year, end_month_num, end_day, 23, 59, 59)

                self.result['params']['start_date'] = timezone.make_aware(start_dt)
                self.result['params']['end_date'] = timezone.make_aware(end_dt)
                self.result['params']['period_text'] = f"Del {start_day} al {end_day} de {end_month_name.title()}"
                return
            except ValueError:
                pass  # Fecha inválida, continuar con otras estrategias

        # Estrategia 2a: "[palabra] de mes" (día específico en palabra)
        # Ej: "primero de octubre", "del segundo de enero"
        specific_day_word_pattern = r'(?:del?\s+)?(\w+)\s+de\s+(\w+)'
        match = re.search(specific_day_word_pattern, self.command)
        if match:
            day_word = match.group(1).lower()
            month_name = match.group(2)

            # Solo procesar si la palabra es un número y el mes es válido
            if day_word in self.NUMBER_WORDS and month_name in self.MONTHS:
                day = self.NUMBER_WORDS[day_word]
                month_num = self.MONTHS[month_name]
                year = timezone.now().year

                try:
                    # Crear fecha para ese día específico
                    start_dt = datetime(year, month_num, day, 0, 0, 0)
                    end_dt = datetime(year, month_num, day, 23, 59, 59)

                    self.result['params']['start_date'] = timezone.make_aware(start_dt)
                    self.result['params']['end_date'] = timezone.make_aware(end_dt)
                    self.result['params']['period_text'] = f"{day} de {month_name.title()}"
                    return
                except ValueError:
                    pass  # Día inválido para ese mes

        # Estrategia 2b: "DD de mes" o "del DD de mes" (un día específico digital)
        # Ej: "3 de octubre", "del 15 de enero"
        specific_day_pattern = r'(?:del?\s+)?(\d{1,2})\s+de\s+(\w+)'
        match = re.search(specific_day_pattern, self.command)
        if match:
            day = int(match.group(1))
            month_name = match.group(2)

            if month_name in self.MONTHS:
                month_num = self.MONTHS[month_name]
                year = timezone.now().year

                try:
                    # Crear fecha para ese día específico
                    start_dt = datetime(year, month_num, day, 0, 0, 0)
                    end_dt = datetime(year, month_num, day, 23, 59, 59)

                    self.result['params']['start_date'] = timezone.make_aware(start_dt)
                    self.result['params']['end_date'] = timezone.make_aware(end_dt)
                    self.result['params']['period_text'] = f"{day} de {month_name.title()}"
                    return
                except ValueError:
                    pass  # Día inválido para ese mes

        # Estrategia 3: "DD/MM/YYYY" o "DD-MM-YYYY" o "DD/MM" o "DD-MM" (fecha corta)
        # Ej: "3/10/2024", "15-01", "03/10"
        short_date_pattern = r'(?:del?\s+)?(\d{1,2}[/-]\d{1,2})(?:[/-](\d{2,4}))?'
        match = re.search(short_date_pattern, self.command)
        if match:
            date_str = match.group(1).replace('-', '/')
            year_str = match.group(2)

            # Si no hay año, usar el actual
            if not year_str:
                date_str += f"/{timezone.now().year}"
            else:
                date_str += f"/{year_str}"

            parsed_dt = self._parse_date(date_str)
            if parsed_dt:
                start_dt = parsed_dt.replace(hour=0, minute=0, second=0)
                end_dt = parsed_dt.replace(hour=23, minute=59, second=59)

                self.result['params']['start_date'] = timezone.make_aware(start_dt)
                self.result['params']['end_date'] = timezone.make_aware(end_dt)
                self.result['params']['period_text'] = f"{parsed_dt.strftime('%d/%m/%Y')}"
                return

        # ===== ESTRATEGIAS DE RANGOS =====

        # Estrategia 4: "últimos X días"
        days_pattern = r'(?:ultimos?|pasados?|last)\s+(\d+)\s+(?:dias?|days?)'
        match = re.search(days_pattern, self.command)
        if match:
            days = int(match.group(1))
            self.result['params']['end_date'] = timezone.now()
            self.result['params']['start_date'] = self.result['params']['end_date'] - timedelta(days=days)
            self.result['params']['period_text'] = f"Últimos {days} días"
            return

        # Estrategia 5: Rangos explícitos "del DD/MM/YYYY al DD/MM/YYYY"
        date_range_pattern = r'del?\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+al?\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        match = re.search(date_range_pattern, self.command)
        if match:
            start_str = match.group(1).replace('-', '/')
            end_str = match.group(2).replace('-', '/')
            start_dt = self._parse_date(start_str)
            end_dt = self._parse_date(end_str)

            if start_dt and end_dt:
                self.result['params']['start_date'] = timezone.make_aware(start_dt)
                self.result['params']['end_date'] = timezone.make_aware(end_dt.replace(hour=23, minute=59, second=59))
                self.result['params']['period_text'] = f"{start_str} al {end_str}"
                return

        # ===== ESTRATEGIAS DE MESES COMPLETOS (MÁS GENERALES) =====

        # Estrategia 6: "último mes" o "mes pasado" (ANTES del loop de meses)
        if 'ultimo mes' in self.command or 'mes pasado' in self.command or ('últi' in self.command and 'mes' in self.command):
            today = timezone.now()
            first_day_current = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day_prev = first_day_current - timedelta(seconds=1)
            first_day_prev = last_day_prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            self.result['params']['start_date'] = first_day_prev
            self.result['params']['end_date'] = last_day_prev
            self.result['params']['period_text'] = "Mes pasado"
            return

        # Estrategia 7: "mes de [nombre_mes]" (SOLO si no hay día específico)
        # Ej: "mes de octubre", "de octubre" (pero NO "3 de octubre", eso ya se detectó arriba)
        for month_name, month_num in self.MONTHS.items():
            # IMPORTANTE: Solo detectar mes completo si NO hay un día específico en el comando
            # Evitar falsos positivos cuando se dice "3 de octubre" (eso ya fue detectado arriba)
            has_specific_day = re.search(r'\d{1,2}\s+de\s+' + month_name, self.command)

            if has_specific_day:
                # Si hay un día específico, ya fue procesado arriba. No hacer nada aquí.
                continue

            # Buscar SOLO si dice explícitamente "mes de" o está muy claro que se refiere al mes completo
            if f"mes de {month_name}" in self.command or f"todo {month_name}" in self.command or f"completo de {month_name}" in self.command:
                year = timezone.now().year
                self.result['params']['start_date'] = timezone.make_aware(datetime(year, month_num, 1))

                if month_num == 12:
                    self.result['params']['end_date'] = timezone.make_aware(datetime(year, 12, 31, 23, 59, 59))
                else:
                    self.result['params']['end_date'] = timezone.make_aware(datetime(year, month_num + 1, 1)) - timedelta(seconds=1)

                self.result['params']['period_text'] = f"Mes de {month_name.title()}"
                return

        # Estrategia 8: "este mes" o "mes actual"
        if 'este mes' in self.command or 'mes actual' in self.command:
            today = timezone.now()
            self.result['params']['start_date'] = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            self.result['params']['end_date'] = today
            self.result['params']['period_text'] = "Mes actual"
            return

        # Estrategia 9: "esta semana"
        if 'esta semana' in self.command or 'semana actual' in self.command:
            today = timezone.now()
            start_week = today - timedelta(days=today.weekday())
            self.result['params']['start_date'] = start_week.replace(hour=0, minute=0, second=0, microsecond=0)
            self.result['params']['end_date'] = today
            self.result['params']['period_text'] = "Esta semana"
            return

        # Estrategia 9b: "semana anterior", "semana pasada", "la semana pasada"
        if ('semana anterior' in self.command or 'semana pasada' in self.command or
            'la semana anterior' in self.command or 'la semana pasada' in self.command):
            today = timezone.now()
            # Calcular el inicio de la semana actual (lunes a las 00:00:00)
            start_current_week = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            # La semana anterior termina el domingo (justo antes del lunes de esta semana)
            end_last_week = start_current_week - timedelta(seconds=1)
            # La semana anterior empieza el lunes (7 días antes del lunes de esta semana)
            start_last_week = start_current_week - timedelta(days=7)

            self.result['params']['start_date'] = start_last_week
            self.result['params']['end_date'] = end_last_week
            self.result['params']['period_text'] = "Semana anterior"
            return

        # Estrategia 10: "hoy"
        if 'hoy' in self.command or 'today' in self.command:
            today = timezone.now()
            self.result['params']['start_date'] = today.replace(hour=0, minute=0, second=0, microsecond=0)
            self.result['params']['end_date'] = today
            self.result['params']['period_text'] = "Hoy"
            return

        # Estrategia 11: "año [número]" o "del año [número]"
        year_pattern = r'(?:del?\s+)?año\s+(\d{4})'
        match = re.search(year_pattern, self.command)
        if match:
            year = int(match.group(1))
            self.result['params']['start_date'] = timezone.make_aware(datetime(year, 1, 1))
            self.result['params']['end_date'] = timezone.make_aware(datetime(year, 12, 31, 23, 59, 59))
            self.result['params']['period_text'] = f"Año {year}"
            return

        # Por defecto: mes actual
        today = timezone.now()
        self.result['params']['start_date'] = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        self.result['params']['end_date'] = today
        self.result['params']['period_text'] = "Mes actual (por defecto)"

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parsea una fecha en múltiples formatos
        """
        try:
            for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y']:
                try:
                    return datetime.strptime(date_str, fmt).replace(hour=0, minute=0, second=0)
                except ValueError:
                    continue
            return None
        except:
            return None

    def _extract_grouping(self):
        """
        Extrae el tipo de agrupación solicitado
        """
        grouping_keywords = {
            'product': ['por producto', 'por productos', 'agrupado por producto', 'de producto', 'de productos'],
            'client': ['por cliente', 'por clientes', 'agrupado por cliente', 'de cliente', 'de clientes', 'por usuario'],
            'category': ['por categoria', 'por categorias', 'agrupado por categoria'],
            'date': ['por fecha', 'por dia', 'diario', 'diarios', 'por fechas', 'por dias']
        }
        
        for group_type, keywords in grouping_keywords.items():
            for keyword in keywords:
                if keyword in self.command:
                    self.result['params']['group_by'] = group_type
                    return

    def _extract_additional_params(self):
        """
        Extrae parámetros adicionales según el tipo de reporte
        """
        # Para predicciones ML, extraer número de días a predecir
        if self.result['params'].get('supports_ml'):
            days = None
            unit = None  # días, semanas, meses, años

            # ESTRATEGIA 1: Buscar números digitales con unidad de tiempo
            # Patrón: "7 días", "2 semanas", "3 meses", "1 año"
            digit_unit_pattern = r'(?:para|de|proximo|proximos|siguiente|siguientes)?\s*(\d+)\s+(dia|dias|day|days|semana|semanas|week|weeks|mes|meses|month|months|ano|anos|year|years)'
            match = re.search(digit_unit_pattern, self.command)
            if match:
                number = int(match.group(1))
                unit = match.group(2).lower()
                days = self._convert_to_days(number, unit)

            # ESTRATEGIA 2: Buscar números en palabras con unidad de tiempo
            # Patrón: "dos días", "tres semanas", "dos meses"
            if days is None:
                word_unit_pattern = r'(?:para|de|proximo|proximos|siguiente|siguientes)?\s*(\w+)\s+(dia|dias|semana|semanas|mes|meses|ano|anos)'
                match = re.search(word_unit_pattern, self.command)
                if match:
                    number_word = match.group(1).lower()
                    unit = match.group(2).lower()
                    if number_word in self.NUMBER_WORDS:
                        number = self.NUMBER_WORDS[number_word]
                        days = self._convert_to_days(number, unit)

            # ESTRATEGIA 3: Caso especial - "próxima/siguiente [unidad]" sin número explícito
            # Ej: "próxima semana", "siguiente mes"
            if days is None:
                # Buscar "próxima/siguiente" seguido de unidad de tiempo
                implicit_pattern = r'(?:proxima|siguiente)\s+(semana|semanas|mes|meses|ano|anos)'
                match = re.search(implicit_pattern, self.command)
                if match:
                    unit = match.group(1).lower()
                    # Implícitamente es 1 unidad
                    days = self._convert_to_days(1, unit)

            # ESTRATEGIA 4: Buscar números en palabras sin preposición
            # Ej: "dos días", "tres semanas"
            if days is None:
                for number_word, number_value in self.NUMBER_WORDS.items():
                    # Buscar con diferentes unidades
                    for unit_word in ['dia', 'dias', 'semana', 'semanas', 'mes', 'meses', 'ano', 'anos']:
                        if f"{number_word} {unit_word}" in self.command:
                            days = self._convert_to_days(number_value, unit_word)
                            break
                    if days:
                        break

            # Asignar días encontrados o valor por defecto
            if days:
                self.result['params']['forecast_days'] = days
                self.result['params']['days'] = days
            else:
                # Por defecto 30 días
                self.result['params']['forecast_days'] = 30
                self.result['params']['days'] = 30

    def _convert_to_days(self, number: int, unit: str) -> int:
        """
        Convierte una cantidad con unidad de tiempo a días.

        Args:
            number: Cantidad (ej: 2, 3, 7)
            unit: Unidad de tiempo (día/días, semana/semanas, mes/meses, año/años)

        Returns:
            Número de días equivalente
        """
        unit = unit.lower()

        # Días
        if unit in ['dia', 'dias', 'day', 'days']:
            return number

        # Semanas (7 días por semana)
        elif unit in ['semana', 'semanas', 'week', 'weeks']:
            return number * 7

        # Meses (30 días por mes - aproximación)
        elif unit in ['mes', 'meses', 'month', 'months']:
            return number * 30

        # Años (365 días por año)
        elif unit in ['ano', 'anos', 'year', 'years']:
            return number * 365

        else:
            # Por defecto, asumir días
            return number

    def _extract_numeric_filters(self):
        """
        Extrae filtros numéricos del comando:
        - Top N / Mejores N / Primeros N
        - Mayor a X / Más de X
        - Menor a X / Menos de X
        - Entre X y Y
        """

        # FILTRO 1: Top N / Mejores N / Primeros N
        # Ej: "top 10 productos", "mejores 5 clientes", "primeros 3"
        top_pattern = r'(?:top|mejores|primeros)\s+(\d+)'
        match = re.search(top_pattern, self.command)
        if match:
            limit = int(match.group(1))
            self.result['params']['limit'] = limit
            self.result['params']['order_by'] = 'DESC'  # Ordenar descendente
            logger.info(f"Detectado filtro TOP {limit}")

        # También detectar "top" con número en palabras
        # Ej: "mejores cinco", "top diez"
        top_word_pattern = r'(?:top|mejores|primeros)\s+(\w+)'
        match = re.search(top_word_pattern, self.command)
        if match and 'limit' not in self.result['params']:
            number_word = match.group(1).lower()
            if number_word in self.NUMBER_WORDS:
                limit = self.NUMBER_WORDS[number_word]
                self.result['params']['limit'] = limit
                self.result['params']['order_by'] = 'DESC'
                logger.info(f"Detectado filtro TOP {limit} (en palabras)")

        # FILTRO 2: Mayor a X / Más de X
        # Ej: "ventas mayores a 1000", "clientes que gastaron más de 500"
        greater_pattern = r'(?:mayor(?:es)?|mas)\s+(?:a|de|que)\s+(\d+(?:\.\d+)?)'
        match = re.search(greater_pattern, self.command)
        if match:
            min_amount = float(match.group(1))
            self.result['params']['min_amount'] = min_amount
            logger.info(f"Detectado filtro MAYOR A {min_amount}")

        # FILTRO 3: Menor a X / Menos de X
        # Ej: "productos con precio menor a 50", "ventas menos de 100"
        less_pattern = r'(?:menor(?:es)?|menos)\s+(?:a|de|que)\s+(\d+(?:\.\d+)?)'
        match = re.search(less_pattern, self.command)
        if match:
            max_amount = float(match.group(1))
            self.result['params']['max_amount'] = max_amount
            logger.info(f"Detectado filtro MENOR A {max_amount}")

        # FILTRO 4: Entre X y Y
        # Ej: "ventas entre 100 y 500", "productos entre 50 y 200"
        between_pattern = r'entre\s+(\d+(?:\.\d+)?)\s+y\s+(\d+(?:\.\d+)?)'
        match = re.search(between_pattern, self.command)
        if match:
            min_amount = float(match.group(1))
            max_amount = float(match.group(2))
            self.result['params']['min_amount'] = min_amount
            self.result['params']['max_amount'] = max_amount
            logger.info(f"Detectado filtro ENTRE {min_amount} Y {max_amount}")

        # FILTRO 5: Detectar moneda
        # Ej: "dólares", "pesos", "soles", "$", "USD"
        if any(word in self.command for word in ['dolar', 'dolares', 'usd', '$']):
            self.result['params']['currency'] = 'USD'
        elif any(word in self.command for word in ['peso', 'pesos', 'mxn']):
            self.result['params']['currency'] = 'MXN'
        elif any(word in self.command for word in ['sol', 'soles', 'pen']):
            self.result['params']['currency'] = 'PEN'
        elif any(word in self.command for word in ['euro', 'euros', 'eur', '€']):
            self.result['params']['currency'] = 'EUR'

    def _detect_comparison_periods(self):
        """
        Detecta períodos implícitos en comparaciones.
        Ej: "crecimiento respecto al mes pasado" → compara este mes vs mes pasado
        """

        # Solo procesar si es un reporte comparativo
        if self.result['report_type'] != 'comparativo_temporal':
            return

        today = timezone.now()

        # PATRÓN 1: "este mes vs mes pasado" o "crecimiento respecto al mes pasado"
        if any(phrase in self.command for phrase in ['respecto al mes pasado', 'versus mes pasado', 'vs mes pasado', 'contra mes pasado', 'comparado con mes pasado']):
            # Período 1: Este mes (desde día 1 hasta hoy)
            start1 = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end1 = today

            # Período 2: Mes pasado (mes completo)
            first_current = today.replace(day=1, hour=0, minute=0, second=0)
            last_prev = first_current - timedelta(seconds=1)
            start2 = last_prev.replace(day=1, hour=0, minute=0, second=0)
            end2 = last_prev

            self.result['params']['period1_start'] = start1
            self.result['params']['period1_end'] = end1
            self.result['params']['period2_start'] = start2
            self.result['params']['period2_end'] = end2
            self.result['params']['period1_text'] = "Este mes"
            self.result['params']['period2_text'] = "Mes pasado"
            logger.info("Detectada comparación: este mes vs mes pasado")
            return

        # PATRÓN 2: "esta semana vs semana pasada"
        if any(phrase in self.command for phrase in ['esta semana versus semana', 'esta semana vs semana', 'semana actual contra semana', 'esta semana comparado con semana']):
            # Período 1: Esta semana (desde lunes hasta hoy)
            start1 = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end1 = today

            # Período 2: Semana pasada (lunes a domingo completo)
            start_current_week = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            start2 = start_current_week - timedelta(days=7)
            end2 = start_current_week - timedelta(seconds=1)

            self.result['params']['period1_start'] = start1
            self.result['params']['period1_end'] = end1
            self.result['params']['period2_start'] = start2
            self.result['params']['period2_end'] = end2
            self.result['params']['period1_text'] = "Esta semana"
            self.result['params']['period2_text'] = "Semana anterior"
            logger.info("Detectada comparación: esta semana vs semana anterior")
            return

        # PATRÓN 3: "octubre vs septiembre" o "mes de octubre versus septiembre"
        # Detectar dos meses mencionados
        months_mentioned = []
        for month_name, month_num in self.MONTHS.items():
            if month_name in self.command:
                months_mentioned.append((month_name, month_num))

        if len(months_mentioned) == 2:
            # Dos meses detectados
            month1_name, month1_num = months_mentioned[0]
            month2_name, month2_num = months_mentioned[1]

            year = today.year

            # Período 1: Primer mes mencionado
            start1 = timezone.make_aware(datetime(year, month1_num, 1, 0, 0, 0))
            if month1_num == 12:
                end1 = timezone.make_aware(datetime(year, 12, 31, 23, 59, 59))
            else:
                end1 = timezone.make_aware(datetime(year, month1_num + 1, 1, 0, 0, 0)) - timedelta(seconds=1)

            # Período 2: Segundo mes mencionado
            start2 = timezone.make_aware(datetime(year, month2_num, 1, 0, 0, 0))
            if month2_num == 12:
                end2 = timezone.make_aware(datetime(year, 12, 31, 23, 59, 59))
            else:
                end2 = timezone.make_aware(datetime(year, month2_num + 1, 1, 0, 0, 0)) - timedelta(seconds=1)

            self.result['params']['period1_start'] = start1
            self.result['params']['period1_end'] = end1
            self.result['params']['period2_start'] = start2
            self.result['params']['period2_end'] = end2
            self.result['params']['period1_text'] = month1_name.title()
            self.result['params']['period2_text'] = month2_name.title()
            logger.info(f"Detectada comparación: {month1_name} vs {month2_name}")
            return

        # PATRÓN 4: "año actual vs año pasado" o "este año contra año anterior"
        if any(phrase in self.command for phrase in ['ano actual vs ano', 'este ano versus ano', 'ano actual contra ano']):
            # Período 1: Este año (desde enero 1 hasta hoy)
            start1 = timezone.make_aware(datetime(today.year, 1, 1, 0, 0, 0))
            end1 = today

            # Período 2: Año pasado (año completo)
            start2 = timezone.make_aware(datetime(today.year - 1, 1, 1, 0, 0, 0))
            end2 = timezone.make_aware(datetime(today.year - 1, 12, 31, 23, 59, 59))

            self.result['params']['period1_start'] = start1
            self.result['params']['period1_end'] = end1
            self.result['params']['period2_start'] = start2
            self.result['params']['period2_end'] = end2
            self.result['params']['period1_text'] = f"Año {today.year}"
            self.result['params']['period2_text'] = f"Año {today.year - 1}"
            logger.info(f"Detectada comparación: año {today.year} vs año {today.year - 1}")
            return

    def _detect_alert_command(self):
        """
        Detecta si el comando es para crear una alerta/programación

        Modifica self.result para indicar que es un comando de alerta
        """

        alert_keywords = [
            # Notificaciones
            'avisame', 'avisa', 'notificame', 'notifica', 'alertame', 'alerta',
            # Programación
            'cada dia', 'cada semana', 'cada mes', 'cada lunes', 'cada martes',
            'diario', 'semanal', 'mensual',
            # Condicionales
            'cuando', 'si', 'en caso de'
        ]

        # Verificar si contiene keywords de alerta
        if not any(keyword in self.command for keyword in alert_keywords):
            return

        # ES UN COMANDO DE ALERTA
        self.result['is_alert'] = True
        self.result['alert_params'] = {}

        logger.info("Comando de alerta detectado")

        # PATRÓN 1: "avísame cuando [condición]"
        if any(word in self.command for word in ['avisame cuando', 'notificame cuando', 'alertame cuando']):
            self.result['alert_params']['type'] = 'condition'

            # Detectar condiciones específicas
            if 'stock bajo' in self.command or 'bajo stock' in self.command or 'stock este bajo' in self.command:
                self.result['alert_params']['condition_type'] = 'stock_low'

                # Extraer umbral si lo menciona
                threshold_match = re.search(r'(?:menor|menos|bajo)\s+(?:de|a|que)\s+(\d+)', self.command)
                if threshold_match:
                    self.result['alert_params']['threshold'] = int(threshold_match.group(1))
                else:
                    self.result['alert_params']['threshold'] = 10  # Por defecto

                logger.info(f"Condición: stock bajo (umbral: {self.result['alert_params']['threshold']})")

            elif 'ventas caen' in self.command or 'ventas bajen' in self.command or 'caida de ventas' in self.command:
                self.result['alert_params']['condition_type'] = 'sales_drop'

                # Extraer porcentaje
                pct_match = re.search(r'(\d+)\s*%', self.command)
                if pct_match:
                    self.result['alert_params']['percentage'] = int(pct_match.group(1))
                else:
                    self.result['alert_params']['percentage'] = 20  # Por defecto

                logger.info(f"Condición: caída de ventas (>{self.result['alert_params']['percentage']}%)")

            elif 'sin stock' in self.command or 'inventario cero' in self.command:
                self.result['alert_params']['condition_type'] = 'inventory_zero'
                logger.info("Condición: inventario en cero")

        # PATRÓN 2: "envíame/manda [reporte] cada [frecuencia]"
        elif any(phrase in self.command for phrase in ['cada dia', 'cada semana', 'cada mes', 'cada lunes',
                                                        'diario', 'semanal', 'mensual']):
            self.result['alert_params']['type'] = 'scheduled'

            # Detectar frecuencia
            if 'cada dia' in self.command or 'diario' in self.command or 'todos los dias' in self.command:
                self.result['alert_params']['frequency'] = 'daily'

                # Extraer hora si la menciona
                hour_match = re.search(r'(\d{1,2})\s*(?:am|pm|hs|horas)', self.command)
                if hour_match:
                    hour = int(hour_match.group(1))
                    self.result['alert_params']['hour'] = hour if hour <= 12 else hour - 12
                else:
                    self.result['alert_params']['hour'] = 9  # 9 AM por defecto

                logger.info(f"Programación: diaria a las {self.result['alert_params']['hour']}:00")

            elif 'cada semana' in self.command or 'semanal' in self.command or 'todas las semanas' in self.command:
                self.result['alert_params']['frequency'] = 'weekly'

                # Detectar día de la semana
                days_map = {
                    'lunes': 0, 'martes': 1, 'miercoles': 2, 'jueves': 3,
                    'viernes': 4, 'sabado': 5, 'domingo': 6
                }

                day_of_week = 0  # Lunes por defecto
                for day_name, day_num in days_map.items():
                    if day_name in self.command:
                        day_of_week = day_num
                        break

                self.result['alert_params']['day_of_week'] = day_of_week
                self.result['alert_params']['hour'] = 9  # 9 AM por defecto

                day_name = list(days_map.keys())[day_of_week]
                logger.info(f"Programación: semanal cada {day_name} a las 9:00")

            elif 'cada mes' in self.command or 'mensual' in self.command or 'todos los meses' in self.command:
                self.result['alert_params']['frequency'] = 'monthly'

                # Detectar día del mes
                day_match = re.search(r'dia\s+(\d{1,2})', self.command)
                if day_match:
                    day_of_month = int(day_match.group(1))
                else:
                    day_of_month = 1  # Primer día del mes por defecto

                self.result['alert_params']['day_of_month'] = day_of_month
                self.result['alert_params']['hour'] = 9  # 9 AM por defecto

                logger.info(f"Programación: mensual día {day_of_month} a las 9:00")

        # Extraer el comando base (sin las palabras de alerta)
        # Ejemplo: "avísame cuando stock bajo" → base_command = "stock bajo"
        base_command = self.command
        for keyword in ['avisame', 'avisa', 'notificame', 'notifica', 'alertame', 'alerta',
                        'cuando', 'si', 'cada', 'enviame', 'manda']:
            base_command = base_command.replace(keyword, '').strip()

        self.result['alert_params']['base_command'] = base_command

    def _calculate_confidence(self):
        """
        Calcula el nivel de confianza del parsing
        """
        confidence = 0.0
        
        # Base: si encontró un tipo de reporte
        if self.result['report_type']:
            confidence += 0.4
        
        # Bonus: si detectó fechas específicas
        if 'start_date' in self.result['params'] and 'end_date' in self.result['params']:
            confidence += 0.2
        
        # Bonus: si detectó formato específico
        if self.result['format'] in ['pdf', 'excel']:
            confidence += 0.1
        
        # Bonus: si detectó agrupación
        if self.result['params'].get('group_by'):
            confidence += 0.15
        
        # Bonus: comandos más largos y específicos
        word_count = len(self.command.split())
        if word_count >= 5:
            confidence += 0.15
        
        self.result['confidence'] = min(confidence, 1.0)

    def _validate_result(self):
        """
        Valida que el formato solicitado esté soportado por el reporte
        """
        if self.result['report_type']:
            report_info = self.REPORT_CATALOG[self.result['report_type']]
            
            # Verificar si el formato está soportado
            if self.result['format'] not in report_info['formats']:
                original_format = self.result['format']
                self.result['format'] = report_info['formats'][0]
                self.result['params']['format_changed'] = True
                self.result['params']['original_format'] = original_format
                logger.warning(f"Formato '{original_format}' no soportado para '{self.result['report_name']}'. Usando '{self.result['format']}'")


def parse_command(command: str) -> Dict:
    """
    Función helper para parsear un comando

    Args:
        command: Comando en lenguaje natural

    Returns:
        dict: Resultado del análisis
    """
    parser = UnifiedCommandParser(command)
    return parser.parse()


def parse_command_with_context(command: str, context=None) -> Dict:
    """
    Función helper para parsear un comando con contexto conversacional

    Args:
        command: Comando en lenguaje natural
        context: ConversationContext opcional con historial previo

    Returns:
        dict: Resultado del análisis (puede usar contexto previo)
    """
    parser = UnifiedCommandParser(command)
    return parser.parse_with_context(context)


def get_available_reports() -> Dict:
    """
    Retorna el catálogo completo de reportes disponibles
    
    Returns:
        dict: Catálogo de reportes organizados por categorías
    """
    parser = UnifiedCommandParser("")
    
    reports_list = []
    for report_key, report_info in parser.REPORT_CATALOG.items():
        reports_list.append({
            'id': report_key,
            'name': report_info['name'],
            'description': report_info['description'],
            'keywords': report_info['keywords'],
            'supports_ml': report_info['supports_ml'],
            'formats': report_info['formats'],
            'priority': report_info['priority']
        })
    
    # Organizar por categorías
    categorized = {
        'Reportes Básicos': [r for r in reports_list if not r['supports_ml'] and r['priority'] <= 7],
        'Reportes Avanzados': [r for r in reports_list if not r['supports_ml'] and r['priority'] > 7],
        'Reportes con Machine Learning': [r for r in reports_list if r['supports_ml']],
    }
    
    return {
        'total_reports': len(reports_list),
        'categories': categorized,
        'all_reports': sorted(reports_list, key=lambda x: x['priority'], reverse=True)
    }
