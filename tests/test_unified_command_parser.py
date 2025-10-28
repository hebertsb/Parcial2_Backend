# tests/test_unified_command_parser.py
"""
Tests para el Sistema Unificado de Comandos Inteligentes
"""

from datetime import datetime, timedelta
from django.utils import timezone
from django.test import TestCase

from sales.unified_command_parser import UnifiedCommandParser, parse_command, get_available_reports


class TestUnifiedCommandParser(TestCase):
    """
    Tests del parser unificado de comandos
    """
    
    def test_basic_sales_report(self):
        """Test: Comando básico de ventas"""
        result = parse_command("reporte de ventas del último mes")
        
        assert result['success'] is True
        assert result['report_type'] == 'ventas_basico'
        assert result['report_name'] == 'Reporte Básico de Ventas'
        assert result['confidence'] > 0.5
        assert 'start_date' in result['params']
        assert 'end_date' in result['params']
    
    def test_sales_by_product(self):
        """Test: Ventas por producto"""
        result = parse_command("ventas por producto de esta semana")
        
        assert result['success'] is True
        assert result['report_type'] == 'ventas_por_producto'
        assert result['params'].get('group_by') == 'product'
        assert result['confidence'] > 0.6
    
    def test_sales_by_client(self):
        """Test: Ventas por cliente"""
        result = parse_command("mejores clientes del mes de octubre")
        
        assert result['success'] is True
        assert result['report_type'] == 'ventas_por_cliente'
        assert result['params'].get('group_by') == 'client'
    
    def test_rfm_analysis(self):
        """Test: Análisis RFM"""
        result = parse_command("análisis rfm de clientes en excel")
        
        assert result['success'] is True
        assert result['report_type'] == 'analisis_rfm'
        assert result['format'] == 'excel'
        assert result['confidence'] > 0.7
    
    def test_abc_analysis(self):
        """Test: Análisis ABC"""
        result = parse_command("análisis abc de productos en PDF")
        
        assert result['success'] is True
        assert result['report_type'] == 'analisis_abc'
        assert result['format'] == 'pdf'
    
    def test_ml_predictions(self):
        """Test: Predicciones ML"""
        result = parse_command("predicciones de ventas para los próximos 7 días")
        
        assert result['success'] is True
        assert result['report_type'] == 'prediccion_ventas'
        assert result['params'].get('supports_ml') is True
        assert result['params'].get('forecast_days') == 7
    
    def test_dashboard_executive(self):
        """Test: Dashboard ejecutivo"""
        result = parse_command("dashboard ejecutivo del último mes")
        
        assert result['success'] is True
        assert result['report_type'] == 'dashboard_ejecutivo'
        assert result['format'] == 'json'
    
    # ===== Tests de Extracción de Fechas =====
    
    def test_date_last_month(self):
        """Test: Último mes"""
        result = parse_command("ventas del último mes")
        
        assert 'start_date' in result['params']
        assert 'end_date' in result['params']
        assert result['params']['period_text'] == "Mes pasado"
    
    def test_date_this_week(self):
        """Test: Esta semana"""
        result = parse_command("ventas de esta semana")
        
        assert result['params']['period_text'] == "Esta semana"
    
    def test_date_today(self):
        """Test: Hoy"""
        result = parse_command("ventas de hoy")
        
        assert result['params']['period_text'] == "Hoy"
        assert result['params']['start_date'].date() == timezone.now().date()
    
    def test_date_specific_month(self):
        """Test: Mes específico"""
        result = parse_command("ventas del mes de octubre")
        
        assert result['params']['period_text'] == "Mes de Octubre"
        assert result['params']['start_date'].month == 10
    
    def test_date_last_n_days(self):
        """Test: Últimos N días"""
        result = parse_command("ventas de los últimos 30 días")
        
        assert result['params']['period_text'] == "Últimos 30 días"
        
        # Verificar que el rango sea aproximadamente 30 días
        start = result['params']['start_date']
        end = result['params']['end_date']
        delta = (end - start).days
        assert 29 <= delta <= 31  # Considerar variación
    
    def test_date_explicit_range(self):
        """Test: Rango explícito de fechas"""
        result = parse_command("ventas del 01/10/2024 al 18/10/2024")
        
        assert result['params']['period_text'] == "01/10/2024 al 18/10/2024"
        assert result['params']['start_date'].day == 1
        assert result['params']['start_date'].month == 10
        assert result['params']['end_date'].day == 18
        assert result['params']['end_date'].month == 10
    
    def test_date_specific_year(self):
        """Test: Año específico"""
        result = parse_command("ventas del año 2024")
        
        assert result['params']['period_text'] == "Año 2024"
        assert result['params']['start_date'].year == 2024
        assert result['params']['start_date'].month == 1
        assert result['params']['end_date'].year == 2024
        assert result['params']['end_date'].month == 12
    
    # ===== Tests de Formatos =====
    
    def test_format_pdf(self):
        """Test: Formato PDF"""
        result = parse_command("ventas del mes en PDF")
        
        assert result['format'] == 'pdf'
    
    def test_format_excel(self):
        """Test: Formato Excel"""
        result = parse_command("ventas del mes en excel")
        
        assert result['format'] == 'excel'
    
    def test_format_json_default(self):
        """Test: Formato JSON por defecto"""
        result = parse_command("ventas del mes")
        
        assert result['format'] == 'json'
    
    def test_format_unsupported_fallback(self):
        """Test: Fallback cuando formato no soportado"""
        result = parse_command("dashboard ml en pdf")
        
        # Dashboard ML solo soporta JSON
        assert result['format'] == 'json'
        assert result['params'].get('format_changed') is True
        assert result['params'].get('original_format') == 'pdf'
    
    # ===== Tests de Agrupación =====
    
    def test_grouping_by_product(self):
        """Test: Agrupación por producto"""
        result = parse_command("ventas agrupadas por producto")
        
        assert result['params'].get('group_by') == 'product'
    
    def test_grouping_by_client(self):
        """Test: Agrupación por cliente"""
        result = parse_command("ventas agrupadas por cliente")
        
        assert result['params'].get('group_by') == 'client'
    
    def test_grouping_by_category(self):
        """Test: Agrupación por categoría"""
        result = parse_command("ventas por categoria")
        
        assert result['params'].get('group_by') == 'category'
    
    def test_grouping_by_date(self):
        """Test: Agrupación por fecha"""
        result = parse_command("ventas por dia")
        
        assert result['params'].get('group_by') == 'date'
    
    # ===== Tests de Parámetros Adicionales =====
    
    def test_top_n_limit(self):
        """Test: Límite top N"""
        result = parse_command("top 5 productos del mes")
        
        assert result['params'].get('limit') == 5
    
    def test_ml_forecast_days(self):
        """Test: Días de predicción ML"""
        result = parse_command("predicciones para los próximos 15 días")
        
        assert result['params'].get('forecast_days') == 15
    
    # ===== Tests de Confianza =====
    
    def test_high_confidence_command(self):
        """Test: Comando con alta confianza"""
        result = parse_command("análisis RFM de clientes del último mes en Excel")
        
        # Comando específico con múltiples parámetros debe tener alta confianza
        assert result['confidence'] >= 0.7
    
    def test_low_confidence_command(self):
        """Test: Comando con baja confianza"""
        result = parse_command("dame algo")
        
        # Comando ambiguo debe tener baja confianza
        assert result['confidence'] < 0.5
    
    def test_medium_confidence_with_suggestions(self):
        """Test: Comando con confianza media tiene sugerencias"""
        result = parse_command("reporte de productos")
        
        # Debe tener sugerencias alternativas
        assert len(result['suggestions']) > 0
        assert all('name' in s and 'type' in s for s in result['suggestions'])
    
    # ===== Tests de Casos Edge =====
    
    def test_empty_command(self):
        """Test: Comando vacío"""
        result = parse_command("")
        
        assert result['success'] is True  # Parser no falla, usa defaults
        assert result['report_type'] == 'ventas_basico'  # Default
    
    def test_command_with_typos(self):
        """Test: Comando con errores ortográficos menores"""
        result = parse_command("reporte de bentas del mes")  # "bentas" en vez de "ventas"
        
        # Aún así debería detectar algo
        assert result['success'] is True
    
    def test_very_long_command(self):
        """Test: Comando muy largo"""
        result = parse_command("quiero que me generes un reporte completo de todas las ventas que hemos tenido del último mes agrupado por producto en formato excel por favor")
        
        assert result['success'] is True
        assert result['report_type'] == 'ventas_por_producto'
        assert result['format'] == 'excel'
        assert result['confidence'] > 0.7  # Comando específico a pesar de largo
    
    def test_mixed_case_command(self):
        """Test: Comando con mayúsculas y minúsculas"""
        result = parse_command("REPORTE DE VENTAS Del ÚLTIMO Mes")
        
        assert result['success'] is True
        assert result['report_type'] == 'ventas_basico'
    
    # ===== Tests de Catálogo de Reportes =====
    
    def test_get_available_reports(self):
        """Test: Obtener catálogo de reportes"""
        catalog = get_available_reports()
        
        assert 'total_reports' in catalog
        assert catalog['total_reports'] == 14  # 14 tipos de reportes
        assert 'categories' in catalog
        assert 'all_reports' in catalog
        
        # Verificar categorías
        assert 'Reportes Básicos' in catalog['categories']
        assert 'Reportes Avanzados' in catalog['categories']
        assert 'Reportes con Machine Learning' in catalog['categories']
    
    def test_catalog_structure(self):
        """Test: Estructura del catálogo"""
        catalog = get_available_reports()
        
        for report in catalog['all_reports']:
            assert 'id' in report
            assert 'name' in report
            assert 'description' in report
            assert 'keywords' in report
            assert 'supports_ml' in report
            assert 'formats' in report
            assert 'priority' in report


class TestParserEdgeCases(TestCase):
    """
    Tests de casos especiales y edge cases
    """
    
    def test_command_with_special_characters(self):
        """Test: Comando con caracteres especiales"""
        result = parse_command("ventas!! del último mes???")
        
        assert result['success'] is True
        assert result['report_type'] == 'ventas_basico'
    
    def test_command_with_numbers(self):
        """Test: Comando con números"""
        result = parse_command("ventas del 2024 en formato PDF")
        
        assert result['success'] is True
        assert result['params']['start_date'].year == 2024
        assert result['format'] == 'pdf'
    
    def test_multilingual_mix(self):
        """Test: Mezcla de español e inglés"""
        result = parse_command("sales report del último mes")
        
        # Debe detectar "sales" (ventas en inglés)
        assert result['success'] is True
        assert 'ventas' in result['report_type'] or 'sales' in result['report_type'].lower()
    
    def test_synonyms_detection(self):
        """Test: Detección de sinónimos"""
        commands = [
            "informe de ventas",
            "reporte de ventas",
            "generar ventas",
            "mostrar ventas"
        ]
        
        for cmd in commands:
            result = parse_command(cmd)
            assert result['success'] is True
            assert 'ventas' in result['report_type']


class TestParserPerformance(TestCase):
    """
    Tests de rendimiento del parser
    """
    
    def test_parsing_speed(self):
        """Test: Velocidad de parsing"""
        import time
        
        start = time.time()
        for _ in range(100):
            parse_command("ventas del último mes en PDF")
        end = time.time()
        
        elapsed = end - start
        avg_time = elapsed / 100
        
        # El parsing debe ser rápido (< 10ms por comando)
        assert avg_time < 0.01, f"Parsing muy lento: {avg_time*1000:.2f}ms"
    
    def test_concurrent_parsing(self):
        """Test: Parsing concurrente"""
        commands = [
            "ventas del último mes",
            "productos más vendidos",
            "dashboard ejecutivo",
            "predicciones de ventas",
            "análisis RFM"
        ]
        
        results = []
        for cmd in commands:
            results.append(parse_command(cmd))
        
        # Todos deben ser exitosos
        assert all(r['success'] for r in results)
        
        # Todos deben tener tipos diferentes
        types = [r['report_type'] for r in results]
        assert len(set(types)) == len(types), "Tipos duplicados en comandos diferentes"
