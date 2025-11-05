# sales/views_advanced_reports.py
"""
Vistas para reportes dinámicos avanzados
"""

from rest_framework import views, permissions, status
from rest_framework.response import Response
from django.http import HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta
import re

from .advanced_reports import AdvancedReportGenerator
from .excel_exporter import export_to_excel
from api.permissions import IsAdminUser


class CustomerAnalysisReportView(views.APIView):
    """
    POST /api/orders/reports/customer-analysis/
    
    Análisis RFM de clientes con segmentación automática.
    
    Body:
    {
        "start_date": "2024-01-01",  # Opcional
        "end_date": "2024-12-31",    # Opcional
        "format": "pdf|excel|json"   # Opcional, default: json
    }
    """
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        try:
            params = self._extract_params(request.data)
            generator = AdvancedReportGenerator(params)
            report_data = generator.customer_rfm_analysis()
            
            return self._format_response(report_data, params.get('format', 'json'))
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _extract_params(self, data):
        """Extrae y valida parámetros de la solicitud."""
        params = {}
        
        # Fechas
        if data.get('start_date'):
            params['start_date'] = self._parse_date(data['start_date'])
        
        if data.get('end_date'):
            params['end_date'] = self._parse_date(data['end_date'])
        
        # Formato
        params['format'] = data.get('format', 'json').lower()
        
        return params
    
    def _parse_date(self, date_str):
        """Parsea una fecha en varios formatos."""
        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
            try:
                dt = datetime.strptime(date_str, fmt)
                return timezone.make_aware(dt)
            except ValueError:
                continue
        raise ValueError(f"Invalid date format: {date_str}")
    
    def _format_response(self, report_data, format_type):
        """Formatea la respuesta según el tipo solicitado."""
        if format_type == 'excel':
            return self._export_to_excel(report_data)
        elif format_type == 'pdf':
            return self._export_to_pdf(report_data)
        else:
            return Response(report_data, status=status.HTTP_200_OK)
    
    def _export_to_excel(self, report_data):
        """Exporta el reporte a Excel."""
        try:
            output = export_to_excel(report_data)
            
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="analisis_clientes.xlsx"'
            
            return response
        except ImportError:
            return Response(
                {'error': 'openpyxl no está instalado'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _export_to_pdf(self, report_data):
        """Exporta el reporte a PDF."""
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib import colors
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib.units import inch
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="analisis_clientes.pdf"'
        
        p = canvas.Canvas(response, pagesize=landscape(letter))
        width, height = landscape(letter)
        
        # Título
        p.setFont("Helvetica-Bold", 18)
        p.drawString(50, height - 50, report_data['title'])
        
        # Subtítulo
        p.setFont("Helvetica", 12)
        p.drawString(50, height - 75, report_data['subtitle'])
        
        # Tabla
        table_data = [report_data['headers']] + report_data['rows'][:20]  # Primeros 20
        
        table = Table(table_data, colWidths=[1.5*inch, 2*inch, 1*inch, 0.8*inch, 1*inch, 1*inch, 1.2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A222E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        
        table_height = table.wrap(width, height)[1]
        table.drawOn(p, 50, height - 120 - table_height)
        
        # Totales
        y_pos = height - 140 - table_height
        p.setFont("Helvetica-Bold", 11)
        for key, value in report_data.get('totals', {}).items():
            p.drawString(50, y_pos, f"{key.replace('_', ' ').title()}: {value}")
            y_pos -= 20
        
        p.showPage()
        p.save()
        
        return response


class ProductABCAnalysisView(views.APIView):
    """
    POST /api/orders/reports/product-abc/
    
    Análisis ABC de productos (Principio de Pareto).
    """
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        try:
            params = self._extract_params(request.data)
            generator = AdvancedReportGenerator(params)
            report_data = generator.product_abc_analysis()
            
            return self._format_response(report_data, params.get('format', 'json'))
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _extract_params(self, data):
        return CustomerAnalysisReportView()._extract_params(data)
    
    def _format_response(self, report_data, format_type):
        return CustomerAnalysisReportView()._format_response(report_data, format_type)


class ComparativeReportView(views.APIView):
    """
    POST /api/orders/reports/comparative/
    
    Reporte comparativo entre períodos.
    
    Body:
    {
        "start_date": "2024-10-01",
        "end_date": "2024-10-31",
        "comparison": "previous_month|previous_period",  # Opcional
        "format": "pdf|excel|json"
    }
    """
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        try:
            params = self._extract_params(request.data)
            comparison_period = request.data.get('comparison', 'previous_month')
            
            generator = AdvancedReportGenerator(params)
            report_data = generator.comparative_report(comparison_period)
            
            return self._format_response(report_data, params.get('format', 'json'))
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _extract_params(self, data):
        return CustomerAnalysisReportView()._extract_params(data)
    
    def _format_response(self, report_data, format_type):
        return CustomerAnalysisReportView()._format_response(report_data, format_type)


class ExecutiveDashboardView(views.APIView):
    """
    POST /api/orders/reports/dashboard/
    
    Dashboard ejecutivo con KPIs principales.
    
    Body:
    {
        "start_date": "2024-10-01",  # Opcional
        "end_date": "2024-10-31",    # Opcional
        "format": "json"             # Opcional
    }
    """
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        try:
            params = self._extract_params(request.data)
            generator = AdvancedReportGenerator(params)
            report_data = generator.executive_dashboard()
            
            return Response(report_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _extract_params(self, data):
        return CustomerAnalysisReportView()._extract_params(data)


class InventoryAnalysisView(views.APIView):
    """
    POST /api/orders/reports/inventory-analysis/
    
    Análisis inteligente de inventario.
    
    Body:
    {
        "format": "pdf|excel|json"
    }
    """
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        try:
            params = {'format': request.data.get('format', 'json')}
            generator = AdvancedReportGenerator(params)
            report_data = generator.inventory_analysis()
            
            return self._format_response(report_data, params.get('format', 'json'))
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _format_response(self, report_data, format_type):
        return CustomerAnalysisReportView()._format_response(report_data, format_type)
