# sales/prompt_parser.py
"""
Parser de prompts para generación dinámica de reportes.
Interpreta comandos de texto para extraer parámetros de reportes.
"""

import re
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from django.utils import timezone


class PromptParser:
    """
    Clase para interpretar prompts de texto y extraer parámetros de reportes.
    
    Ejemplos de prompts válidos:
    - "Reporte de ventas del mes de octubre en PDF"
    - "Ventas del 01/09/2024 al 18/10/2024 en Excel"
    - "Ventas por producto del último mes"
    - "Clientes con más compras en pantalla"
    """
    
    # Formatos soportados
    FORMATS = {
        'pdf': ['pdf'],
        'excel': ['excel', 'xls', 'xlsx'],
        'screen': ['pantalla', 'screen', 'vista', 'ver']
    }
    
    # Tipos de agrupación
    GROUPINGS = {
        'product': ['producto', 'productos', 'product', 'products'],
        'client': ['cliente', 'clientes', 'client', 'clients', 'usuario', 'usuarios'],
        'category': ['categoria', 'categorias', 'category', 'categories'],
        'date': ['fecha', 'fechas', 'date', 'dates', 'dia', 'dias', 'day', 'days']
    }
    
    # Meses en español
    MONTHS = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
        'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }
    
    def __init__(self, prompt):
        self.prompt = prompt.lower().strip()
        self.params = {
            'format': 'screen',  # Por defecto mostrar en pantalla
            'start_date': None,
            'end_date': None,
            'group_by': None,
            'report_type': 'sales',  # Por defecto reporte de ventas
            'order_by': '-created_at',
            'filters': {}
        }
    
    def parse(self):
        """
        Analiza el prompt y extrae todos los parámetros.
        """
        self._extract_format()
        self._extract_dates()
        self._extract_grouping()
        self._extract_report_type()
        
        return self.params
    
    def _extract_format(self):
        """
        Extrae el formato de salida del reporte (PDF, Excel, Pantalla).
        """
        for format_key, keywords in self.FORMATS.items():
            for keyword in keywords:
                if keyword in self.prompt:
                    self.params['format'] = format_key
                    return
    
    def _extract_dates(self):
        """
        Extrae fechas del prompt usando múltiples estrategias.
        """
        # Estrategia 1: Buscar rangos explícitos "del DD/MM/YYYY al DD/MM/YYYY"
        date_range_pattern = r'del?\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+al?\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        match = re.search(date_range_pattern, self.prompt)
        
        if match:
            try:
                start_str = match.group(1).replace('-', '/')
                end_str = match.group(2).replace('-', '/')
                start_dt = self._parse_date(start_str)
                end_dt = self._parse_date(end_str)
                
                if start_dt and end_dt:
                    # Asegurar que end_dt tenga hora 23:59:59
                    end_dt = end_dt.replace(hour=23, minute=59, second=59)
                    self.params['start_date'] = timezone.make_aware(start_dt)
                    self.params['end_date'] = timezone.make_aware(end_dt)
                    return
            except:
                pass
        
        # Estrategia 2: Buscar "mes de [nombre_mes]"
        for month_name, month_num in self.MONTHS.items():
            if f"mes de {month_name}" in self.prompt or f"de {month_name}" in self.prompt:
                year = timezone.now().year
                self.params['start_date'] = timezone.make_aware(datetime(year, month_num, 1))
                
                # Calcular último día del mes
                if month_num == 12:
                    self.params['end_date'] = timezone.make_aware(datetime(year, 12, 31, 23, 59, 59))
                else:
                    self.params['end_date'] = timezone.make_aware(datetime(year, month_num + 1, 1)) - timedelta(seconds=1)
                return
        
        # Estrategia 3: Buscar "último mes" o "mes pasado"
        if 'último mes' in self.prompt or 'mes pasado' in self.prompt or 'last month' in self.prompt:
            today = timezone.now()
            first_day_current_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day_prev_month = first_day_current_month - timedelta(seconds=1)
            first_day_prev_month = last_day_prev_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            self.params['start_date'] = first_day_prev_month
            self.params['end_date'] = last_day_prev_month
            return
        
        # Estrategia 4: Buscar "último año" o "año pasado"
        if 'último año' in self.prompt or 'año pasado' in self.prompt or 'last year' in self.prompt:
            year = timezone.now().year - 1
            self.params['start_date'] = timezone.make_aware(datetime(year, 1, 1))
            self.params['end_date'] = timezone.make_aware(datetime(year, 12, 31, 23, 59, 59))
            return
        
        # Estrategia 5: Buscar "últimos X días"
        days_pattern = r'últimos?\s+(\d+)\s+días?|last\s+(\d+)\s+days?'
        match = re.search(days_pattern, self.prompt)
        if match:
            days = int(match.group(1) or match.group(2))
            self.params['end_date'] = timezone.now()
            self.params['start_date'] = self.params['end_date'] - timedelta(days=days)
            return
        
        # Estrategia 6: Buscar año específico "del año 2024"
        year_pattern = r'(?:del?\s+)?año\s+(\d{4})|year\s+(\d{4})'
        match = re.search(year_pattern, self.prompt)
        if match:
            year = int(match.group(1) or match.group(2))
            self.params['start_date'] = timezone.make_aware(datetime(year, 1, 1))
            self.params['end_date'] = timezone.make_aware(datetime(year, 12, 31, 23, 59, 59))
            return
        
        # Si no se encontraron fechas específicas, usar el mes actual por defecto
        if self.params['start_date'] is None:
            today = timezone.now()
            self.params['start_date'] = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            self.params['end_date'] = today
    
    def _parse_date(self, date_str):
        """
        Parsea una fecha en formato DD/MM/YYYY o DD-MM-YYYY.
        Retorna un objeto datetime naive que luego será convertido a aware.
        """
        try:
            # Intentar parsear con formato específico
            for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    # Asegurarse de que tiene tiempo 00:00:00
                    return dt.replace(hour=0, minute=0, second=0, microsecond=0)
                except ValueError:
                    continue
            
            # Si falla, usar dateutil (más flexible)
            dt = date_parser.parse(date_str, dayfirst=True)
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        except:
            return None
    
    def _extract_grouping(self):
        """
        Extrae el tipo de agrupación solicitado.
        """
        for group_key, keywords in self.GROUPINGS.items():
            for keyword in keywords:
                if f"por {keyword}" in self.prompt or f"agrupado por {keyword}" in self.prompt:
                    self.params['group_by'] = group_key
                    return
                if f"por {keyword}".replace(' ', '') in self.prompt.replace(' ', ''):
                    self.params['group_by'] = group_key
                    return
    
    def _extract_report_type(self):
        """
        Extrae el tipo de reporte solicitado.
        """
        # Tipos de reporte soportados
        report_keywords = {
            'sales': ['venta', 'ventas', 'sale', 'sales', 'orden', 'ordenes', 'order', 'orders'],
            'products': ['producto', 'productos', 'product', 'products', 'inventario', 'inventory', 'stock'],
            'clients': ['cliente', 'clientes', 'client', 'clients', 'usuario', 'usuarios', 'user', 'users'],
            'revenue': ['ingreso', 'ingresos', 'revenue', 'ganancia', 'ganancias']
        }
        
        for report_type, keywords in report_keywords.items():
            for keyword in keywords:
                if keyword in self.prompt:
                    self.params['report_type'] = report_type
                    return


def parse_prompt(prompt_text):
    """
    Función helper para parsear un prompt.
    
    Args:
        prompt_text (str): Texto del prompt a interpretar
    
    Returns:
        dict: Diccionario con los parámetros extraídos
    """
    parser = PromptParser(prompt_text)
    return parser.parse()
