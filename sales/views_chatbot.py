"""
Endpoints de chatbot y entrenamiento NLP.
"""
from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from .intelligent_report_router import IntelligentReportRouter
from .nlp_intent_classifier import train_intent_model, is_model_available
from .nlp_intent_classifier import predict_intent_or_none
from .openai_service import analyze_command_with_openai, chat_reply


@api_view(['POST'])
@permission_classes([IsAdminUser])
def nlp_train_intents(request):
    """Entrena el clasificador NLP ligero basado en los reportes disponibles."""
    try:
        router = IntelligentReportRouter("")
        result = train_intent_model(router.AVAILABLE_REPORTS)
        return Response({'success': True, 'data': result}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def nlp_parse_intent(request):
    """Parsea intención usando el modelo entrenado si existe, con fallback al router tradicional."""
    text = (request.data.get('texto') or request.data.get('comando') or '').strip()
    if not text:
        return Response({'success': False, 'error': 'texto/comando requerido'}, status=status.HTTP_400_BAD_REQUEST)
    # Intento con modelo
    nlp_res = predict_intent_or_none(text)
    router = IntelligentReportRouter(text)
    parsed = router.parse()
    if nlp_res and nlp_res.get('label') == parsed.get('report_type'):
        parsed['confidence'] = max(parsed.get('confidence', 0), nlp_res.get('confidence', 0))
        parsed['nlp_used'] = True
    else:
        parsed['nlp_used'] = False
    parsed['nlp_model_available'] = is_model_available()
    return Response({'success': True, 'data': parsed})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chatbot_interact(request):
    """Interacción básica tipo chatbot para ayudar al usuario con reportes.
    Campos: mensaje (str)
    Respuesta usa OpenAI si disponible, sino heurística local.
    """
    message = (request.data.get('mensaje') or request.data.get('message') or '').strip()
    if not message:
        return Response({'success': False, 'error': 'mensaje/message requerido'}, status=status.HTTP_400_BAD_REQUEST)

    # Intento OpenAI libre
    ai_reply = chat_reply(message, system_hint="Eres asistente de reportes de ventas. Sé conciso.")
    router = IntelligentReportRouter(message)
    parsed = router.parse()

    if ai_reply is None:
        # Fallback básico
        ai_reply = f"Interpretado como: {parsed.get('report_name')} (formato {parsed.get('format')}). Usa /api/sales/reports/ventas/?formato={parsed.get('format')} si aplica."

    return Response({
        'success': True,
        'reply': ai_reply,
        'parsed_report': parsed,
        'openai_used': ai_reply is not None and 'Interpretado como:' not in ai_reply,
    })
