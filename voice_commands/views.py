import time
import logging
import io
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import VoiceCommand, VoiceCommandHistory
from .serializers import (
    VoiceCommandSerializer,
    VoiceCommandTextSerializer
)
from .voice_processor import VoiceCommandProcessor

logger = logging.getLogger(__name__)


class VoiceCommandViewSet(viewsets.ModelViewSet):
    """
    ViewSet para comandos de texto inteligentes
    
    Endpoints:
    - GET /text-commands/ - Listar comandos del usuario
    - GET /text-commands/{id}/ - Detalle de un comando
    - POST /text-commands/process/ - Procesar un comando de texto
    - GET /text-commands/history/ - Historial de todos los comandos
    - GET /text-commands/capabilities/ - Capacidades del sistema
    """
    
    serializer_class = VoiceCommandSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Solo comandos del usuario actual"""
        return VoiceCommand.objects.filter(user=self.request.user).prefetch_related('history')
    
    @action(detail=False, methods=['POST'], url_path='process')
    def process_text(self, request):
        """
        Procesa un comando de texto inteligente y genera el reporte correspondiente
        
        **Request:**
        ```json
        {
            "text": "generar reporte de ventas del último mes en PDF"
        }
        ```
        
        **Ejemplos de comandos válidos:**
        - "reporte de ventas del último mes"
        - "productos más vendidos esta semana"
        - "dashboard ejecutivo del mes de octubre"
        - "predicciones de ventas para los próximos 7 días"
        - "análisis RFM de clientes en Excel"
        - "ventas por cliente del año 2024"
        
        **Response:**
        ```json
        {
            "success": true,
            "data": {
                "id": 1,
                "transcribed_text": "generar reporte de ventas del último mes",
                "status": "EXECUTED",
                "command_type": "reporte",
                "result_data": {...},
                "processing_time_ms": 850
            },
            "message": "Comando procesado exitosamente"
        }
        ```
        """
        
        start_time = time.time()
        
        # Validar el input
        serializer = VoiceCommandTextSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'Datos inválidos',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        text = serializer.validated_data['text']
        
        # Crear el comando en BD
        voice_command = VoiceCommand.objects.create(
            user=request.user,
            command_text=text,
            status='PROCESSING'
        )
        
        VoiceCommandHistory.objects.create(
            voice_command=voice_command,
            stage='TEXT_INPUT',
            message=f'Comando recibido: "{text}"',
            data={'source': 'text_api'}
        )
        
        try:
            # Procesar el comando
            processor = VoiceCommandProcessor(user=request.user)
            command_result = processor.process_command(text)
            
            # Actualizar el comando
            voice_command.command_type = command_result.get('command_type')
            voice_command.interpreted_params = command_result.get('params', {})
            voice_command.confidence_score = command_result.get('confidence', 0.0)  # ✅ GUARDAMOS CONFIDENCE
            
            if command_result.get('success'):
                voice_command.status = 'EXECUTED'
                voice_command.result_data = command_result.get('result', {})
                
                VoiceCommandHistory.objects.create(
                    voice_command=voice_command,
                    stage='EXECUTION_SUCCESS',
                    message='Comando ejecutado exitosamente',
                    data={'command_type': command_result.get('command_type')}
                )
            else:
                voice_command.status = 'FAILED'
                voice_command.error_message = command_result.get('error', 'Error desconocido')
                
                VoiceCommandHistory.objects.create(
                    voice_command=voice_command,
                    stage='EXECUTION_FAILED',
                    message=f'Error: {voice_command.error_message}',
                    data={}
                )
            
            # Tiempo de procesamiento
            end_time = time.time()
            voice_command.processing_time_ms = int((end_time - start_time) * 1000)
            voice_command.save()
            
            # Serializar y devolver
            serializer = VoiceCommandSerializer(voice_command)
            
            return Response({
                'success': command_result.get('success', False),
                'data': serializer.data,
                'message': 'Comando procesado exitosamente' if command_result.get('success') else voice_command.error_message
            }, status=status.HTTP_200_OK if command_result.get('success') else status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"❌ Error al procesar texto: {e}")
            
            voice_command.status = 'FAILED'
            voice_command.error_message = str(e)
            voice_command.save()
            
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['GET'], url_path='history')
    def history(self, request):
        """
        Obtiene el historial de todos los comandos del usuario
        """
        
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'success': True,
            'count': queryset.count(),
            'data': serializer.data
        })
    
    @action(detail=False, methods=['GET'], url_path='capabilities')
    def capabilities(self, request):
        """
        Retorna las capacidades del sistema de comandos inteligentes
        """
        
        return Response({
            'success': True,
            'data': {
                'system_name': 'Sistema de Comandos Inteligentes',
                'version': '2.0',
                'supported_commands': [
                    'Reportes de Ventas',
                    'Reportes de Productos',
                    'Reportes de Clientes',
                    'Análisis Avanzados (RFM, ABC)',
                    'Predicciones ML',
                    'Dashboard Ejecutivo'
                ],
                'examples': [
                    'reporte de ventas del último mes',
                    'productos más vendidos esta semana',
                    'dashboard ejecutivo de octubre',
                    'predicciones de ventas para 7 días',
                    'análisis RFM de clientes en Excel',
                    'ventas por cliente del año 2024',
                    'análisis ABC de productos en PDF'
                ],
                'supported_formats': ['JSON', 'PDF', 'Excel'],
                'supported_date_ranges': [
                    'hoy', 'ayer', 'esta semana', 'este mes', 'este año',
                    'última semana', 'último mes', 'último año',
                    'últimos X días',
                    'mes de [nombre]',
                    'año [número]',
                    'del DD/MM/YYYY al DD/MM/YYYY'
                ]
            }
        })
    
    @action(detail=True, methods=['GET'], url_path='download/pdf')
    def download_pdf(self, request, pk=None):
        """
        Descarga el reporte en formato PDF
        
        GET /api/voice-commands/{id}/download/pdf/
        """
        try:
            voice_command = self.get_object()
            
            # Verificar que el comando se ejecutó exitosamente
            if voice_command.status != 'EXECUTED':
                return Response({
                    'error': 'El comando no se ejecutó correctamente. No se puede generar PDF.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Importar librerías de PDF
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
            
            # Crear buffer
            buffer = io.BytesIO()
            
            # Obtener datos del reporte
            result_data = voice_command.result_data or {}
            report_info = result_data.get('report_info', {})
            parameters = result_data.get('parameters', {})
            metadata = result_data.get('metadata', {})
            
            # Crear documento PDF
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            
            # Estilo personalizado para título
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1a73e8'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            
            # Título
            title = Paragraph(report_info.get('name', 'Reporte de Comandos Inteligentes'), title_style)
            elements.append(title)
            elements.append(Spacer(1, 0.3*inch))
            
            # Información del comando
            command_info = [
                ['Comando Original:', voice_command.command_text],
                ['Estado:', voice_command.status],
                ['Confianza:', f"{(voice_command.confidence_score * 100):.0f}%" if voice_command.confidence_score else "N/A"],
                ['Tiempo de Procesamiento:', f"{voice_command.processing_time_ms}ms" if voice_command.processing_time_ms else "N/A"],
                ['Generado por:', voice_command.user.username],
                ['Fecha de Generación:', voice_command.created_at.strftime('%d/%m/%Y %H:%M:%S')],
            ]
            
            t1 = Table(command_info, colWidths=[2.5*inch, 4*inch])
            t1.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f0fe')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey)
            ]))
            elements.append(t1)
            elements.append(Spacer(1, 0.5*inch))
            
            # Parámetros del reporte
            if parameters:
                param_title = Paragraph('<b>Parámetros del Reporte</b>', styles['Heading2'])
                elements.append(param_title)
                elements.append(Spacer(1, 0.2*inch))
                
                date_range = parameters.get('date_range', {})
                param_data = []
                
                if date_range.get('description'):
                    param_data.append(['Período:', date_range['description']])
                if date_range.get('start'):
                    param_data.append(['Fecha Inicio:', date_range['start'][:10]])
                if date_range.get('end'):
                    param_data.append(['Fecha Fin:', date_range['end'][:10]])
                if parameters.get('group_by'):
                    param_data.append(['Agrupado por:', parameters['group_by'].title()])
                if parameters.get('limit'):
                    param_data.append(['Límite:', str(parameters['limit'])])
                
                if param_data:
                    t2 = Table(param_data, colWidths=[2*inch, 4.5*inch])
                    t2.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f3f4')),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
                    ]))
                    elements.append(t2)
                    elements.append(Spacer(1, 0.3*inch))
            
            # Descripción del reporte
            if report_info.get('description'):
                desc_title = Paragraph('<b>Descripción</b>', styles['Heading2'])
                elements.append(desc_title)
                elements.append(Spacer(1, 0.1*inch))
                desc = Paragraph(report_info['description'], styles['BodyText'])
                elements.append(desc)
                elements.append(Spacer(1, 0.3*inch))

            # ============ DATOS DEL REPORTE (LA TABLA PRINCIPAL) ============
            # Esta es la parte que faltaba: escribir los datos reales del reporte
            report_data = result_data.get('data', {})

            if report_data:
                # Título de los datos
                data_title = Paragraph('<b>Datos del Reporte</b>', styles['Heading2'])
                elements.append(data_title)
                elements.append(Spacer(1, 0.2*inch))

                # Construir tabla de datos
                # Intentar extraer headers y rows del reporte
                headers = report_data.get('headers', [])
                rows = report_data.get('rows', [])

                # Si no hay estructura headers/rows, intentar otras estructuras
                if not headers and not rows:
                    # ESTRUCTURA ML: Predicciones con 'predictions'
                    if 'predictions' in report_data:
                        predictions = report_data['predictions']
                        if len(predictions) > 0:
                            # Headers para predicciones ML
                            headers = ['Fecha', 'Ventas Predichas', 'Límite Inferior', 'Límite Superior', 'Confianza']
                            rows = []
                            for pred in predictions[:50]:  # Limitar a 50
                                rows.append([
                                    pred.get('date', 'N/A'),
                                    f"${pred.get('predicted_sales', 0):,.2f}",
                                    f"${pred.get('lower_bound', 0):,.2f}",
                                    f"${pred.get('upper_bound', 0):,.2f}",
                                    f"{pred.get('confidence', 0) * 100:.0f}%"
                                ])
                    # Estructura alternativa: lista de diccionarios
                    elif isinstance(report_data, list) and len(report_data) > 0:
                        if isinstance(report_data[0], dict):
                            headers = list(report_data[0].keys())
                            rows = [[str(item.get(h, '')) for h in headers] for item in report_data]
                    # Estructura alternativa: diccionario con 'data'
                    elif 'data' in report_data and isinstance(report_data['data'], list):
                        data_list = report_data['data']
                        if len(data_list) > 0 and isinstance(data_list[0], dict):
                            headers = list(data_list[0].keys())
                            rows = [[str(item.get(h, '')) for h in headers] for item in data_list]

                if headers and rows:
                    # Preparar datos para la tabla (headers + rows)
                    table_data = [headers] + rows[:50]  # Limitar a 50 filas para evitar PDFs muy grandes

                    # Crear tabla
                    data_table = Table(table_data)
                    data_table.setStyle(TableStyle([
                        # Estilo del header
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        # Estilo de las filas
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f3f4')]),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ]))
                    elements.append(data_table)

                    # Nota si se truncaron filas
                    if len(rows) > 50:
                        note = Paragraph(
                            f'<i>Mostrando 50 de {len(rows)} registros. Descargue el reporte completo en Excel.</i>',
                            styles['Normal']
                        )
                        elements.append(Spacer(1, 0.1*inch))
                        elements.append(note)

                    elements.append(Spacer(1, 0.3*inch))

                    # Si es una predicción ML, agregar el resumen
                    if 'summary' in report_data:
                        summary = report_data['summary']
                        summary_title = Paragraph('<b>Resumen de Predicciones</b>', styles['Heading2'])
                        elements.append(summary_title)
                        elements.append(Spacer(1, 0.2*inch))

                        summary_data = [
                            ['Total de días predichos:', str(summary.get('total_days', 'N/A'))],
                            ['Ventas totales predichas:', f"${summary.get('total_predicted_sales', 0):,.2f}"],
                            ['Promedio diario predicho:', f"${summary.get('average_daily_sales', 0):,.2f}"],
                            ['Promedio histórico:', f"${summary.get('historical_average', 0):,.2f}"],
                            ['Tasa de crecimiento:', f"{summary.get('growth_rate_percent', 0):+.2f}%"],
                        ]

                        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
                        summary_table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f0fe')),
                            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, -1), 10),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
                        ]))
                        elements.append(summary_table)
                        elements.append(Spacer(1, 0.3*inch))

            # Nota al pie
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.grey,
                alignment=TA_CENTER
            )
            footer = Paragraph(
                f'Generado por Sistema de Comandos Inteligentes v2.0 | {metadata.get("generated_at", "")[:10]}',
                footer_style
            )
            elements.append(Spacer(1, 0.5*inch))
            elements.append(footer)
            
            # Construir PDF
            doc.build(elements)
            
            # Preparar respuesta
            buffer.seek(0)
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            filename = f'reporte_{voice_command.id}_{voice_command.created_at.strftime("%Y%m%d")}.pdf'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            logger.info(f"📄 PDF generado exitosamente para comando {voice_command.id}")
            return response
            
        except Exception as e:
            logger.error(f"❌ Error al generar PDF: {e}", exc_info=True)
            return Response({
                'error': f'Error al generar PDF: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['GET'], url_path='download/excel')
    def download_excel(self, request, pk=None):
        """
        Descarga el reporte en formato Excel
        
        GET /api/voice-commands/{id}/download/excel/
        """
        try:
            voice_command = self.get_object()
            
            # Verificar que el comando se ejecutó exitosamente
            if voice_command.status != 'EXECUTED':
                return Response({
                    'error': 'El comando no se ejecutó correctamente. No se puede generar Excel.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Importar librerías de Excel
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
            
            # Crear workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Reporte"
            
            # Obtener datos del reporte
            result_data = voice_command.result_data or {}
            report_info = result_data.get('report_info', {})
            parameters = result_data.get('parameters', {})
            
            # Estilos
            title_font = Font(name='Calibri', size=16, bold=True, color='1a73e8')
            header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
            header_fill = PatternFill(start_color='1a73e8', end_color='1a73e8', fill_type='solid')
            border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            # Título
            ws['A1'] = report_info.get('name', 'Reporte de Comandos Inteligentes')
            ws['A1'].font = title_font
            ws.merge_cells('A1:B1')
            
            # Información del comando
            row = 3
            ws[f'A{row}'] = 'Comando Original:'
            ws[f'B{row}'] = voice_command.command_text
            ws[f'A{row}'].font = Font(bold=True)
            
            row += 1
            ws[f'A{row}'] = 'Estado:'
            ws[f'B{row}'] = voice_command.status
            ws[f'A{row}'].font = Font(bold=True)
            
            row += 1
            ws[f'A{row}'] = 'Confianza:'
            ws[f'B{row}'] = f"{(voice_command.confidence_score * 100):.0f}%" if voice_command.confidence_score else "N/A"
            ws[f'A{row}'].font = Font(bold=True)
            
            row += 1
            ws[f'A{row}'] = 'Tiempo de Procesamiento:'
            ws[f'B{row}'] = f"{voice_command.processing_time_ms}ms" if voice_command.processing_time_ms else "N/A"
            ws[f'A{row}'].font = Font(bold=True)
            
            row += 1
            ws[f'A{row}'] = 'Generado por:'
            ws[f'B{row}'] = voice_command.user.username
            ws[f'A{row}'].font = Font(bold=True)
            
            row += 1
            ws[f'A{row}'] = 'Fecha de Generación:'
            ws[f'B{row}'] = voice_command.created_at.strftime('%d/%m/%Y %H:%M:%S')
            ws[f'A{row}'].font = Font(bold=True)
            
            # Parámetros del reporte
            if parameters:
                row += 2
                ws[f'A{row}'] = 'Parámetros del Reporte'
                ws[f'A{row}'].font = Font(bold=True, size=12)
                ws.merge_cells(f'A{row}:B{row}')
                
                date_range = parameters.get('date_range', {})
                
                if date_range.get('description'):
                    row += 1
                    ws[f'A{row}'] = 'Período:'
                    ws[f'B{row}'] = date_range['description']
                    ws[f'A{row}'].font = Font(bold=True)
                
                if date_range.get('start'):
                    row += 1
                    ws[f'A{row}'] = 'Fecha Inicio:'
                    ws[f'B{row}'] = date_range['start'][:10]
                    ws[f'A{row}'].font = Font(bold=True)
                
                if date_range.get('end'):
                    row += 1
                    ws[f'A{row}'] = 'Fecha Fin:'
                    ws[f'B{row}'] = date_range['end'][:10]
                    ws[f'A{row}'].font = Font(bold=True)
                
                if parameters.get('group_by'):
                    row += 1
                    ws[f'A{row}'] = 'Agrupado por:'
                    ws[f'B{row}'] = parameters['group_by'].title()
                    ws[f'A{row}'].font = Font(bold=True)
                
                if parameters.get('limit'):
                    row += 1
                    ws[f'A{row}'] = 'Límite:'
                    ws[f'B{row}'] = parameters['limit']
                    ws[f'A{row}'].font = Font(bold=True)

            # ============ DATOS DEL REPORTE (LA TABLA PRINCIPAL) ============
            # Esta es la parte que faltaba: escribir los datos reales del reporte
            report_data = result_data.get('data', {})

            if report_data:
                row += 3  # Espacio
                ws[f'A{row}'] = 'Datos del Reporte'
                ws[f'A{row}'].font = Font(bold=True, size=14, color='1a73e8')
                ws.merge_cells(f'A{row}:E{row}')
                row += 2

                # Intentar extraer headers y rows del reporte
                headers = report_data.get('headers', [])
                rows = report_data.get('rows', [])

                # Si no hay estructura headers/rows, intentar otras estructuras
                if not headers and not rows:
                    # ESTRUCTURA ML: Predicciones con 'predictions'
                    if 'predictions' in report_data:
                        predictions = report_data['predictions']
                        if len(predictions) > 0:
                            # Headers para predicciones ML
                            headers = ['Fecha', 'Ventas Predichas', 'Límite Inferior', 'Límite Superior', 'Confianza']
                            rows = []
                            for pred in predictions:
                                rows.append([
                                    pred.get('date', 'N/A'),
                                    f"${pred.get('predicted_sales', 0):,.2f}",
                                    f"${pred.get('lower_bound', 0):,.2f}",
                                    f"${pred.get('upper_bound', 0):,.2f}",
                                    f"{pred.get('confidence', 0) * 100:.0f}%"
                                ])
                    # Estructura alternativa: lista de diccionarios
                    elif isinstance(report_data, list) and len(report_data) > 0:
                        if isinstance(report_data[0], dict):
                            headers = list(report_data[0].keys())
                            rows = [[item.get(h, '') for h in headers] for item in report_data]
                    # Estructura alternativa: diccionario con 'data'
                    elif 'data' in report_data and isinstance(report_data['data'], list):
                        data_list = report_data['data']
                        if len(data_list) > 0 and isinstance(data_list[0], dict):
                            headers = list(data_list[0].keys())
                            rows = [[item.get(h, '') for h in headers] for item in data_list]

                if headers and rows:
                    # Escribir encabezados
                    for col_idx, header in enumerate(headers, start=1):
                        cell = ws.cell(row=row, column=col_idx)
                        cell.value = header
                        cell.font = header_font
                        cell.fill = header_fill
                        cell.alignment = Alignment(horizontal='center', vertical='center')
                        cell.border = border

                    row += 1

                    # Escribir filas de datos
                    for row_data in rows:
                        for col_idx, value in enumerate(row_data, start=1):
                            cell = ws.cell(row=row, column=col_idx)
                            # Manejar valores que pueden ser strings con formato especial
                            cell.value = str(value) if value is not None else ''
                            cell.alignment = Alignment(horizontal='left' if col_idx == 1 else 'center', vertical='center')
                            cell.border = border
                        row += 1

                    # Ajustar ancho de columnas automáticamente para los datos
                    for col_idx in range(1, len(headers) + 1):
                        # Usar get_column_letter para evitar problemas con celdas fusionadas
                        column_letter = get_column_letter(col_idx)
                        max_length = len(str(headers[col_idx-1])) if col_idx <= len(headers) else 10

                        # Calcular ancho máximo basado en contenido
                        for row_data in rows[:100]:  # Revisar primeras 100 filas
                            if col_idx <= len(row_data):
                                cell_value = str(row_data[col_idx-1])
                                max_length = max(max_length, len(cell_value))

                        # Aplicar ancho (máximo 50 caracteres)
                        ws.column_dimensions[column_letter].width = min(max_length + 2, 50)

                    # Si es una predicción ML, agregar el resumen
                    if 'summary' in report_data:
                        summary = report_data['summary']
                        row += 3  # Espacio

                        # Título del resumen
                        ws[f'A{row}'] = 'Resumen de Predicciones'
                        ws[f'A{row}'].font = Font(bold=True, size=12, color='1a73e8')
                        ws.merge_cells(f'A{row}:B{row}')
                        row += 2

                        # Datos del resumen
                        summary_items = [
                            ('Total de días predichos:', str(summary.get('total_days', 'N/A'))),
                            ('Ventas totales predichas:', f"${summary.get('total_predicted_sales', 0):,.2f}"),
                            ('Promedio diario predicho:', f"${summary.get('average_daily_sales', 0):,.2f}"),
                            ('Promedio histórico:', f"${summary.get('historical_average', 0):,.2f}"),
                            ('Tasa de crecimiento:', f"{summary.get('growth_rate_percent', 0):+.2f}%"),
                        ]

                        for label, value in summary_items:
                            ws[f'A{row}'] = label
                            ws[f'A{row}'].font = Font(bold=True)
                            ws[f'A{row}'].fill = PatternFill(start_color='e8f0fe', end_color='e8f0fe', fill_type='solid')

                            ws[f'B{row}'] = value
                            ws[f'B{row}'].fill = PatternFill(start_color='e8f0fe', end_color='e8f0fe', fill_type='solid')

                            row += 1
            else:
                # Mantener anchos originales si no hay datos del reporte
                ws.column_dimensions['A'].width = 25
                ws.column_dimensions['B'].width = 50

            # Guardar en buffer
            buffer = io.BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            
            # Preparar respuesta
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            filename = f'reporte_{voice_command.id}_{voice_command.created_at.strftime("%Y%m%d")}.xlsx'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            logger.info(f"📊 Excel generado exitosamente para comando {voice_command.id}")
            return response
            
        except Exception as e:
            logger.error(f"❌ Error al generar Excel: {e}", exc_info=True)
            return Response({
                'error': f'Error al generar Excel: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
