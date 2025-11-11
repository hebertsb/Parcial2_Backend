# sales/intelligent_report_router.py
"""
Sistema Unificado Inteligente de Reportes
Procesa comandos en lenguaje natural y enruta al reporte correcto.
"""

import re
from datetime import datetime, timedelta
from django.utils import timezone
from .nlp_intent_classifier import predict_intent_or_none


class IntelligentReportRouter:
    """
    Enrutador inteligente que interpreta comandos de texto y determina:
    - Tipo de reporte a generar
    - Formato de salida
    - Parámetros necesarios
    - Si incluye predicciones ML o datos históricos
    """

    # Catálogo de reportes disponibles
    AVAILABLE_REPORTS = {
        'ventas_basico': {
            'name': 'Reporte Básico de Ventas',
            'description': 'Ventas generales sin agrupación específica',
            'keywords': ['ventas general', 'reporte de ventas', 'historial ventas'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'endpoint_type': 'basic_dynamic'
        },
        'ventas_por_producto': {
            'name': 'Ventas por Producto',
            'description': 'Ventas agrupadas por producto con estadísticas',
            'keywords': ['ventas por producto', 'productos vendidos', 'reporte productos'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'endpoint_type': 'basic_dynamic'
        },
        'ventas_por_cliente': {
            'name': 'Ventas por Cliente',
            'description': 'Ventas agrupadas por cliente',
            'keywords': ['ventas por cliente', 'clientes', 'mejores clientes'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'endpoint_type': 'basic_dynamic'
        },
        'ventas_por_categoria': {
            'name': 'Ventas por Categoría',
            'description': 'Ventas agrupadas por categoría de producto',
            'keywords': ['ventas por categoria', 'categorias'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'endpoint_type': 'basic_dynamic'
        },
        'ventas_por_fecha': {
            'name': 'Ventas por Fecha',
            'description': 'Ventas día a día',
            'keywords': ['ventas por fecha', 'ventas diarias', 'por dia'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'endpoint_type': 'basic_dynamic'
        },
        'analisis_rfm': {
            'name': 'Análisis RFM de Clientes',
            'description': 'Segmentación de clientes (VIP, Regular, En Riesgo, etc.)',
            'keywords': ['analisis rfm', 'segmentacion clientes', 'rfm', 'clientes vip'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'endpoint_type': 'advanced'
        },
        'analisis_abc': {
            'name': 'Análisis ABC de Productos',
            'description': 'Clasificación de productos por el principio de Pareto (80/20)',
            'keywords': ['analisis abc', 'pareto', 'clasificacion productos', 'abc'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'endpoint_type': 'advanced'
        },
        'comparativo_temporal': {
            'name': 'Reporte Comparativo',
            'description': 'Comparación entre dos períodos de tiempo',
            'keywords': ['comparativo', 'comparar periodos', 'comparacion'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'endpoint_type': 'advanced'
        },
        'dashboard_ejecutivo': {
            'name': 'Dashboard Ejecutivo',
            'description': 'KPIs principales y alertas del negocio',
            'keywords': ['dashboard ejecutivo', 'dashboard', 'kpis', 'resumen ejecutivo'],
            'supports_ml': False,
            'formats': ['json'],
            'endpoint_type': 'advanced'
        },
        'analisis_inventario': {
            'name': 'Análisis de Inventario',
            'description': 'Estado del inventario con rotación y alertas',
            'keywords': ['inventario', 'stock', 'analisis inventario'],
            'supports_ml': False,
            'formats': ['json', 'pdf', 'excel'],
            'endpoint_type': 'advanced'
        },
        'prediccion_ventas': {
            'name': 'Predicción de Ventas (ML)',
            'description': 'Predicciones futuras de ventas usando Machine Learning',
            'keywords': ['prediccion', 'predicciones', 'forecast', 'pronostico', 'ventas futuras'],
            'supports_ml': True,
            'formats': ['json', 'pdf', 'excel'],
            'endpoint_type': 'ml_predictions'
        },
        'prediccion_producto': {
            'name': 'Predicción por Producto (ML)',
            'description': 'Predicciones de ventas para productos específicos',
            'keywords': ['prediccion producto', 'prediccion por producto', 'forecast producto'],
            'supports_ml': True,
            'formats': ['json'],
            'endpoint_type': 'ml_product'
        },
        'recomendaciones': {
            'name': 'Sistema de Recomendaciones (ML)',
            'description': 'Recomendaciones personalizadas de productos',
            'keywords': ['recomendaciones', 'recomendar', 'sugerencias'],
            'supports_ml': True,
            'formats': ['json'],
            'endpoint_type': 'ml_recommendations'
        },
        'dashboard_ml': {
            'name': 'Dashboard de Predicciones ML',
            'description': 'Dashboard completo con predicciones y análisis ML',
            'keywords': ['dashboard ml', 'dashboard predicciones', 'ml dashboard'],
            'supports_ml': True,
            'formats': ['json'],
            'endpoint_type': 'ml_dashboard'
        }
    }

    # Meses en español
    MONTHS = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
        'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }

    def __init__(self, command):
        """
        Inicializa el router con un comando de texto.

        Args:
            command (str): Comando en lenguaje natural
        """
        self.command = command.lower().strip()
        self.result = {
            'report_type': None,
            'report_name': None,
            'report_description': None,
            'endpoint_type': None,
            'format': 'json',
            'params': {},
            'supports_ml': False,
            'confidence': 0.0,  # Nivel de confianza del match
            'alternatives': []  # Reportes alternativos sugeridos
        }

    def parse(self):
        """
        Analiza el comando y determina el reporte a generar.

        Returns:
            dict: Resultado del análisis con tipo de reporte y parámetros
        """
        # 1. Identificar el tipo de reporte
        self._identify_report_type()

        # 2. Extraer formato de salida
        self._extract_format()

        # 3. Extraer fechas y rangos
        self._extract_dates()

        # 4. Extraer parámetros adicionales
        self._extract_additional_params()

        # 5. Validar el resultado
        self._validate_result()

        return self.result

    def _identify_report_type(self):
        """
        Identifica el tipo de reporte solicitado basándose en keywords.
        """
        best_match = None
        best_score = 0
        alternatives = []

        # 0. Intento con modelo NLP si está disponible
        try:
            nlp_res = predict_intent_or_none(self.command)
        except Exception:
            nlp_res = None

        for report_key, report_info in self.AVAILABLE_REPORTS.items():
            score = 0

            # Verificar coincidencias de keywords
            for keyword in report_info['keywords']:
                if keyword in self.command:
                    score += len(keyword.split())  # Dar más peso a keywords más largas

            # Guardar alternativas con puntuación > 0
            if score > 0:
                alternatives.append({
                    'type': report_key,
                    'name': report_info['name'],
                    'score': score
                })

            # Si NLP propone exactamente este reporte con alta confianza, subir score artificialmente
            if nlp_res and nlp_res.get('label') == report_key:
                score += 10 if nlp_res.get('confidence', 0) >= 0.75 else 3

            # Actualizar mejor match
            if score > best_score:
                best_score = score
                best_match = (report_key, report_info)

        if best_match:
            report_key, report_info = best_match
            self.result['report_type'] = report_key
            self.result['report_name'] = report_info['name']
            self.result['report_description'] = report_info['description']
            self.result['endpoint_type'] = report_info['endpoint_type']
            self.result['supports_ml'] = report_info['supports_ml']
            base_conf = min(best_score / 3.0, 1.0)
            if nlp_res and nlp_res.get('label') == self.result['report_type']:
                base_conf = max(base_conf, float(nlp_res.get('confidence', 0)))
            self.result['confidence'] = base_conf

            # Ordenar alternativas por score
            alternatives.sort(key=lambda x: x['score'], reverse=True)
            self.result['alternatives'] = [alt for alt in alternatives if alt['type'] != report_key][:3]
        else:
            # Por defecto: reporte básico de ventas
            self.result['report_type'] = 'ventas_basico'
            self.result['report_name'] = 'Reporte Básico de Ventas'
            self.result['report_description'] = 'Ventas generales (opción por defecto)'
            self.result['endpoint_type'] = 'basic_dynamic'
            self.result['confidence'] = 0.3

    def _extract_format(self):
        """
        Extrae el formato de salida solicitado (JSON, PDF, Excel).
        """
        if 'pdf' in self.command:
            self.result['format'] = 'pdf'
        elif 'excel' in self.command or 'xls' in self.command or 'xlsx' in self.command:
            self.result['format'] = 'excel'
        elif 'json' in self.command or 'pantalla' in self.command or 'screen' in self.command:
            self.result['format'] = 'json'
        # Si no se especifica, queda en 'json' por defecto

    def _extract_dates(self):
        """
        Extrae fechas y rangos de tiempo del comando.
        """
        # Estrategia 1: "últimos X días"
        days_pattern = r'(?:ultimos?|pasados?|last)\s+(\d+)\s+(?:dias?|days?)'
        match = re.search(days_pattern, self.command)
        if match:
            days = int(match.group(1))
            self.result['params']['end_date'] = timezone.now()
            self.result['params']['start_date'] = self.result['params']['end_date'] - timedelta(days=days)
            self.result['params']['period_text'] = f"Últimos {days} días"
            return

        # Estrategia 2: Rangos explícitos "del DD/MM/YYYY al DD/MM/YYYY"
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

        # Estrategia 3: "mes de [nombre_mes]"
        for month_name, month_num in self.MONTHS.items():
            if f"mes de {month_name}" in self.command or f"de {month_name}" in self.command:
                year = timezone.now().year
                self.result['params']['start_date'] = timezone.make_aware(datetime(year, month_num, 1))

                if month_num == 12:
                    self.result['params']['end_date'] = timezone.make_aware(datetime(year, 12, 31, 23, 59, 59))
                else:
                    self.result['params']['end_date'] = timezone.make_aware(datetime(year, month_num + 1, 1)) - timedelta(seconds=1)

                self.result['params']['period_text'] = f"Mes de {month_name.title()}"
                return

        # Estrategia 4: "último mes" o "mes pasado"
        if 'ultimo mes' in self.command or 'mes pasado' in self.command:
            today = timezone.now()
            first_day_current = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day_prev = first_day_current - timedelta(seconds=1)
            first_day_prev = last_day_prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            self.result['params']['start_date'] = first_day_prev
            self.result['params']['end_date'] = last_day_prev
            self.result['params']['period_text'] = "Mes pasado"
            return

        # Por defecto: mes actual
        today = timezone.now()
        self.result['params']['start_date'] = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        self.result['params']['end_date'] = today
        self.result['params']['period_text'] = "Mes actual"

    def _parse_date(self, date_str):
        """
        Parsea una fecha en formato DD/MM/YYYY.
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

    def _extract_additional_params(self):
        """
        Extrae parámetros adicionales según el tipo de reporte.
        """
        # Para reportes básicos dinámicos, determinar agrupación
        if self.result['endpoint_type'] == 'basic_dynamic':
            if self.result['report_type'] == 'ventas_por_producto':
                self.result['params']['group_by'] = 'product'
                self.result['params']['report_type'] = 'sales'
            elif self.result['report_type'] == 'ventas_por_cliente':
                self.result['params']['group_by'] = 'client'
                self.result['params']['report_type'] = 'sales'
            elif self.result['report_type'] == 'ventas_por_categoria':
                self.result['params']['group_by'] = 'category'
                self.result['params']['report_type'] = 'sales'
            elif self.result['report_type'] == 'ventas_por_fecha':
                self.result['params']['group_by'] = 'date'
                self.result['params']['report_type'] = 'sales'
            else:
                self.result['params']['report_type'] = 'sales'

        # Para predicciones ML, extraer número de días a predecir
        if self.result['supports_ml']:
            # Buscar "prediccion de X dias"
            pred_pattern = r'(?:prediccion|pronostico|forecast).*?(\d+)\s+(?:dias?|days?)'
            match = re.search(pred_pattern, self.command)
            if match:
                self.result['params']['forecast_days'] = int(match.group(1))
            else:
                self.result['params']['forecast_days'] = 30  # Por defecto 30 días

        # Para comparativos, determinar tipo de comparación
        if self.result['report_type'] == 'comparativo_temporal':
            if 'mes anterior' in self.command or 'mes pasado' in self.command:
                self.result['params']['comparison'] = 'previous_month'
            else:
                self.result['params']['comparison'] = 'previous_period'

    def _validate_result(self):
        """
        Valida que el formato solicitado esté soportado por el reporte.
        """
        if self.result['report_type']:
            report_info = self.AVAILABLE_REPORTS[self.result['report_type']]

            # Verificar si el formato está soportado
            if self.result['format'] not in report_info['formats']:
                # Usar el primer formato disponible
                self.result['format'] = report_info['formats'][0]
                self.result['format_changed'] = True
                self.result['original_format'] = self.result['format']


def get_available_reports():
    """
    Retorna la lista de todos los reportes disponibles en el sistema.

    Returns:
        dict: Catálogo completo de reportes
    """
    router = IntelligentReportRouter("")

    reports_catalog = []
    for report_key, report_info in router.AVAILABLE_REPORTS.items():
        reports_catalog.append({
            'id': report_key,
            'name': report_info['name'],
            'description': report_info['description'],
            'keywords': report_info['keywords'],
            'supports_ml': report_info['supports_ml'],
            'formats': report_info['formats'],
            'endpoint_type': report_info['endpoint_type']
        })

    # Organizar por categorías
    categorized = {
        'Reportes Básicos': [r for r in reports_catalog if r['endpoint_type'] == 'basic_dynamic'],
        'Reportes Avanzados': [r for r in reports_catalog if r['endpoint_type'] == 'advanced'],
        'Reportes con Machine Learning': [r for r in reports_catalog if r['supports_ml']],
    }

    return {
        'total_reports': len(reports_catalog),
        'categories': categorized,
        'all_reports': reports_catalog
    }


def parse_intelligent_command(command):
    """
    Función helper para parsear un comando inteligente.

    Args:
        command (str): Comando en lenguaje natural

    Returns:
        dict: Resultado del análisis
    """
    router = IntelligentReportRouter(command)
    return router.parse()
