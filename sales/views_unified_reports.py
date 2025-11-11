"""
Endpoints de API para reportes avanzados con IA y gráficas interactivas.
Moneda única: Bs. Sin departamentos/ USD.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from django.utils import timezone

from typing import Dict, Any

from .intelligent_report_router import parse_intelligent_command, IntelligentReportRouter
from .openai_service import analyze_command_with_openai
from .reports_core import (
    obtener_metricas_y_series,
    construir_datos_ventas,
    construir_datos_clientes,
    construir_datos_productos,
)
from .export_utils import exportar_reporte_pdf, exportar_reporte_excel, exportar_reporte_docx


def _build_report_dict(title: str, headers, rows, totals, subtitle: str = '') -> Dict[str, Any]:
    return {
        'title': title,
        'subtitle': subtitle,
        'headers': headers,
        'rows': rows,
        'totals': totals,
        'metadata': {'currency': 'Bs', 'generated_at': timezone.now().strftime('%Y-%m-%d %H:%M:%S')},
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def procesar_comando_ia(request):
    """
    POST /api/sales/reports/ia/procesar/

    Procesa comandos de voz/texto en lenguaje natural con fallback local.
    Acepta alias: comando | prompt | texto
    """
    try:
        comando_raw = (
            request.data.get('comando') or request.data.get('prompt') or request.data.get('texto') or ''
        )
        comando = comando_raw.strip()
        if not comando:
            return Response({
                'success': False,
                'error': 'El campo "comando" (o alias "prompt"/"texto") es requerido'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Intento con OpenAI primero (si hay API key)
        parsed_ai = analyze_command_with_openai(comando, IntelligentReportRouter.AVAILABLE_REPORTS)
        if parsed_ai:
            parsed = parsed_ai
            using_ai = True
        else:
            parsed = parse_intelligent_command(comando)
            using_ai = False

        resultado = {
            'success': True,
            'interpretacion': parsed.get('report_description'),
            'accion': 'generar_reporte',
            'tipo_reporte': parsed.get('report_type'),
            'formato': parsed.get('format', 'json'),
            'filtros': {
                'fecha_inicio': parsed['params'].get('start_date'),
                'fecha_fin': parsed['params'].get('end_date'),
                'moneda': 'Bs'
            },
            'respuesta_texto': f"Generaré {parsed.get('report_name')} en {parsed.get('format')}",
            'confianza': parsed.get('confidence', 0),
            'usando_ia': using_ai,
            'ia_disponible': using_ai,
            'comando_original': comando
        }

        return Response(resultado, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'success': False,
            'error': 'Error al procesar el comando',
            'detalle': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def obtener_datos_graficas(request):
    """
    POST /api/sales/reports/graficas/

    Retorna datos agregados para gráficas interactivas del dashboard.
    Filtros opcionales: fecha_inicio, fecha_fin
    """
    try:
        filtros = request.data or {}
        data = obtener_metricas_y_series(filtros)
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'success': False,
            'error': 'Error al obtener datos de gráficas',
            'detalle': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generar_reporte_ventas(request):
    """
    GET /api/sales/reports/ventas/?formato=pdf|excel|docx&fecha_inicio=YYYY-MM-DD&fecha_fin=YYYY-MM-DD
    """
    try:
        formato = (request.GET.get('formato') or 'pdf').lower()
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')
        filtros = {'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin}

        headers, rows, totals = construir_datos_ventas(filtros)
        report = _build_report_dict('Reporte de Ventas', headers, rows, totals)

        if formato == 'pdf':
            buffer = exportar_reporte_pdf(report)
            resp = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            resp['Content-Disposition'] = f'attachment; filename="reporte_ventas_{timezone.now().strftime("%Y%m%d")}.pdf"'
            return resp
        elif formato == 'excel':
            buffer = exportar_reporte_excel(report)
            resp = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            resp['Content-Disposition'] = f'attachment; filename="reporte_ventas_{timezone.now().strftime("%Y%m%d")}.xlsx"'
            return resp
        elif formato == 'docx' or formato == 'word':
            buffer = exportar_reporte_docx(report)
            resp = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            resp['Content-Disposition'] = f'attachment; filename="reporte_ventas_{timezone.now().strftime("%Y%m%d")}.docx"'
            return resp
        else:
            return Response({'success': False, 'error': 'Formato no soportado'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'success': False, 'error': 'Error al generar reporte', 'detalle': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generar_reporte_clientes(request):
    """
    GET /api/sales/reports/clientes/?formato=pdf|excel|docx&fecha_inicio=YYYY-MM-DD&fecha_fin=YYYY-MM-DD
    """
    try:
        formato = (request.GET.get('formato') or 'pdf').lower()
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')
        filtros = {'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin}

        headers, rows, totals = construir_datos_clientes(filtros)
        report = _build_report_dict('Reporte de Clientes', headers, rows, totals)

        if formato == 'pdf':
            buffer = exportar_reporte_pdf(report)
            resp = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            resp['Content-Disposition'] = f'attachment; filename="reporte_clientes_{timezone.now().strftime("%Y%m%d")}.pdf"'
            return resp
        elif formato == 'excel':
            buffer = exportar_reporte_excel(report)
            resp = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            resp['Content-Disposition'] = f'attachment; filename="reporte_clientes_{timezone.now().strftime("%Y%m%d")}.xlsx"'
            return resp
        elif formato == 'docx' or formato == 'word':
            buffer = exportar_reporte_docx(report)
            resp = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            resp['Content-Disposition'] = f'attachment; filename="reporte_clientes_{timezone.now().strftime("%Y%m%d")}.docx"'
            return resp
        else:
            return Response({'success': False, 'error': 'Formato no soportado'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'success': False, 'error': 'Error al generar reporte', 'detalle': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generar_reporte_productos(request):
    """
    GET /api/sales/reports/productos/?formato=pdf|excel|docx&fecha_inicio=YYYY-MM-DD&fecha_fin=YYYY-MM-DD
    """
    try:
        formato = (request.GET.get('formato') or 'pdf').lower()
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')
        filtros = {'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin}

        headers, rows, totals = construir_datos_productos(filtros)
        report = _build_report_dict('Reporte de Productos', headers, rows, totals)

        if formato == 'pdf':
            buffer = exportar_reporte_pdf(report)
            resp = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            resp['Content-Disposition'] = f'attachment; filename="reporte_productos_{timezone.now().strftime("%Y%m%d")}.pdf"'
            return resp
        elif formato == 'excel':
            buffer = exportar_reporte_excel(report)
            resp = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            resp['Content-Disposition'] = f'attachment; filename="reporte_productos_{timezone.now().strftime("%Y%m%d")}.xlsx"'
            return resp
        elif formato == 'docx' or formato == 'word':
            buffer = exportar_reporte_docx(report)
            resp = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            resp['Content-Disposition'] = f'attachment; filename="reporte_productos_{timezone.now().strftime("%Y%m%d")}.docx"'
            return resp
        else:
            return Response({'success': False, 'error': 'Formato no soportado'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'success': False, 'error': 'Error al generar reporte', 'detalle': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

