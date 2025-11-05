# sales/views_unified_reports.py
"""
Vistas para el Sistema Unificado de Reportes Inteligentes
"""

from rest_framework import views, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.http import HttpResponse
from api.permissions import IsAdminUser

from .intelligent_report_router import (
    parse_intelligent_command,
    get_available_reports
)
from .report_generator import ReportGenerator
from .advanced_reports import AdvancedReportGenerator
from .excel_exporter import export_to_excel


class UnifiedReportListView(views.APIView):
    """
    GET /api/sales/reports/unified/list/

    Lista todos los tipos de reportes disponibles en el sistema.
    Útil para que el frontend construya un menú o muestre opciones al usuario.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        """
        Retorna el catálogo completo de reportes disponibles.
        """
        catalog = get_available_reports()

        return Response({
            'success': True,
            'total_reports': catalog['total_reports'],
            'categories': catalog['categories'],
            'all_reports': catalog['all_reports'],
            'message': 'Usa el endpoint /unified/generate/ para generar cualquier reporte con lenguaje natural'
        }, status=status.HTTP_200_OK)


class UnifiedIntelligentReportView(views.APIView):
    """
    POST /api/sales/reports/unified/generate/

    Endpoint UNIFICADO e INTELIGENTE para generar cualquier tipo de reporte.

    Procesa comandos en lenguaje natural y genera el reporte apropiado.

    Body:
    {
        "command": "Dame un reporte de ventas de los últimos 7 días en PDF"
    }

    Ejemplos de comandos válidos:
    - "Reporte de ventas del mes de octubre en PDF"
    - "Dame las predicciones de los próximos 7 días"
    - "Análisis RFM de clientes en Excel"
    - "Dashboard ejecutivo del último mes"
    - "Ventas por producto de los últimos 30 días"
    - "Análisis ABC en PDF"
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        command = request.data.get('command', '').strip()

        if not command:
            return Response({
                'success': False,
                'error': 'Se requiere un comando en el campo "command"',
                'example': 'Dame un reporte de ventas de los últimos 7 días en PDF'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Parsear el comando
            parsed = parse_intelligent_command(command)

            # 2. Verificar confianza del match
            if parsed['confidence'] < 0.3:
                return Response({
                    'success': False,
                    'error': 'No se pudo interpretar el comando',
                    'command_received': command,
                    'suggestions': parsed['alternatives'],
                    'tip': 'Intenta usar palabras clave como: ventas, predicción, análisis, dashboard, etc.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 3. Generar el reporte según el tipo
            report_data = self._generate_report(parsed)

            # 4. Formatear la respuesta según el formato solicitado
            return self._format_response(report_data, parsed)

        except Exception as e:
            return Response({
                'success': False,
                'error': f'Error al procesar el comando: {str(e)}',
                'command_received': command
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _generate_report(self, parsed):
        """
        Genera el reporte según el tipo identificado.
        """
        endpoint_type = parsed['endpoint_type']
        params = parsed['params']

        # REPORTES BÁSICOS DINÁMICOS
        if endpoint_type == 'basic_dynamic':
            generator = ReportGenerator(params)
            return generator.generate()

        # REPORTES AVANZADOS
        elif endpoint_type == 'advanced':
            generator = AdvancedReportGenerator(params)

            if parsed['report_type'] == 'analisis_rfm':
                return generator.customer_rfm_analysis()
            elif parsed['report_type'] == 'analisis_abc':
                return generator.product_abc_analysis()
            elif parsed['report_type'] == 'comparativo_temporal':
                comparison = params.get('comparison', 'previous_period')
                return generator.comparative_report(comparison)
            elif parsed['report_type'] == 'dashboard_ejecutivo':
                return generator.executive_dashboard()
            elif parsed['report_type'] == 'analisis_inventario':
                return generator.inventory_analysis()

        # REPORTES ML (Predicciones)
        elif endpoint_type in ['ml_predictions', 'ml_product', 'ml_dashboard']:
            return self._generate_ml_report(parsed)

        # Por defecto: reporte básico
        else:
            generator = ReportGenerator(params)
            return generator.generate()

    def _generate_ml_report(self, parsed):
        """
        Genera reportes relacionados con Machine Learning.
        Nota: Esto requiere que los modelos ML estén entrenados.
        """
        from .ml_predictor_simple import SalesPredictor
        from datetime import datetime

        forecast_days = parsed['params'].get('forecast_days', 30)

        try:
            predictor = SalesPredictor()

            if parsed['report_type'] == 'prediccion_ventas':
                # Generar predicciones
                predictions_data = predictor.predict(days=forecast_days)

                # Formatear como reporte
                report_data = {
                    'title': f'Predicción de Ventas - Próximos {forecast_days} días',
                    'subtitle': 'Generado con Machine Learning',
                    'headers': ['Fecha', 'Ventas Predichas', 'Límite Inferior', 'Límite Superior'],
                    'rows': [],
                    'totals': {},
                    'metadata': {
                        'forecast_days': forecast_days,
                        'model_type': 'Prophet',
                        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                }

                # Construir filas
                for _, row in predictions_data.iterrows():
                    report_data['rows'].append([
                        row['ds'].strftime('%d/%m/%Y'),
                        f"${row['yhat']:.2f}",
                        f"${row['yhat_lower']:.2f}",
                        f"${row['yhat_upper']:.2f}"
                    ])

                # Calcular totales
                total_predicted = predictions_data['yhat'].sum()
                avg_daily = predictions_data['yhat'].mean()

                report_data['totals'] = {
                    'total_predicted': f"${total_predicted:.2f}",
                    'avg_daily_sales': f"${avg_daily:.2f}",
                    'forecast_period': f"{forecast_days} días"
                }

                return report_data

            else:
                return {
                    'title': 'Reporte ML',
                    'subtitle': 'Funcionalidad en desarrollo',
                    'headers': [],
                    'rows': [],
                    'totals': {},
                    'metadata': {}
                }

        except Exception as e:
            # Si falla ML, retornar estructura básica con error
            return {
                'title': 'Error en Predicción ML',
                'subtitle': str(e),
                'headers': ['Estado'],
                'rows': [['El modelo ML no está disponible o no está entrenado']],
                'totals': {},
                'metadata': {'error': str(e)}
            }

    def _format_response(self, report_data, parsed):
        """
        Formatea la respuesta según el formato solicitado (JSON, PDF, Excel).
        """
        output_format = parsed['format']

        # JSON (pantalla)
        if output_format == 'json':
            return Response({
                'success': True,
                'command': parsed.get('command', ''),
                'report_type': parsed['report_name'],
                'report_description': parsed['report_description'],
                'confidence': parsed['confidence'],
                'period': parsed['params'].get('period_text', 'N/A'),
                'format': output_format,
                'data': report_data
            }, status=status.HTTP_200_OK)

        # PDF
        elif output_format == 'pdf':
            return self._export_to_pdf(report_data, parsed)

        # Excel
        elif output_format == 'excel':
            return self._export_to_excel(report_data, parsed)

        else:
            # Por defecto JSON
            return Response({
                'success': True,
                'data': report_data
            }, status=status.HTTP_200_OK)

    def _export_to_pdf(self, report_data, parsed):
        """
        Exporta el reporte a formato PDF.
        """
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib import colors
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib.units import inch

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="reporte_{parsed["report_type"]}.pdf"'

        p = canvas.Canvas(response, pagesize=landscape(letter) if len(report_data.get('headers', [])) > 5 else letter)
        width, height = landscape(letter) if len(report_data.get('headers', [])) > 5 else letter

        # Título
        p.setFont("Helvetica-Bold", 18)
        p.drawString(50, height - 50, report_data.get('title', 'Reporte'))

        # Subtítulo
        p.setFont("Helvetica", 12)
        p.drawString(50, height - 75, report_data.get('subtitle', ''))

        y_position = height - 100

        # Tabla
        headers = report_data.get('headers', [])
        rows = report_data.get('rows', [])

        if headers and rows:
            table_data = [headers] + rows[:20]  # Limitar a 20 filas

            # Calcular anchos de columna dinámicamente
            num_cols = len(headers)
            col_width = (width - 100) / num_cols
            col_widths = [col_width] * num_cols

            table = Table(table_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A222E')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))

            table_height = table.wrap(width, height)[1]
            table.drawOn(p, 50, y_position - table_height - 20)

            y_position -= table_height + 40

        # Totales
        totals = report_data.get('totals', {})
        if totals:
            p.setFont("Helvetica-Bold", 11)
            for key, value in totals.items():
                label = key.replace('_', ' ').title()
                p.drawString(50, y_position, f"{label}: {value}")
                y_position -= 20

        p.showPage()
        p.save()

        return response

    def _export_to_excel(self, report_data, parsed):
        """
        Exporta el reporte a formato Excel.
        """
        output = export_to_excel(report_data)

        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="reporte_{parsed["report_type"]}.xlsx"'

        return response


@api_view(['POST'])
@permission_classes([IsAdminUser])
def test_intelligent_parser(request):
    """
    POST /api/sales/reports/unified/test/

    Endpoint de prueba para ver cómo se interpreta un comando sin generar el reporte.
    Útil para debugging y para que el frontend muestre sugerencias.

    Body:
    {
        "command": "Dame ventas de los últimos 7 días"
    }
    """
    command = request.data.get('command', '')

    if not command:
        return Response({
            'error': 'Se requiere el campo "command"'
        }, status=status.HTTP_400_BAD_REQUEST)

    parsed = parse_intelligent_command(command)

    return Response({
        'command_received': command,
        'interpretation': {
            'report_type': parsed['report_type'],
            'report_name': parsed['report_name'],
            'report_description': parsed['report_description'],
            'format': parsed['format'],
            'confidence': parsed['confidence'],
            'endpoint_type': parsed['endpoint_type'],
            'supports_ml': parsed['supports_ml']
        },
        'parameters': parsed['params'],
        'alternatives': parsed['alternatives'] if parsed['alternatives'] else 'Ninguna sugerencia adicional'
    }, status=status.HTTP_200_OK)
