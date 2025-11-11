"""
Servicio de integración opcional con OpenAI.
No rompe si no hay OPENAI_API_KEY en el entorno. Devuelve None en ese caso.
"""
from __future__ import annotations

import os
import json
from typing import Optional, Dict, Any

_client = None


def _get_api_key() -> Optional[str]:
    return os.getenv('OPENAI_API_KEY')


def get_openai_client():
    global _client
    if _client is not None:
        return _client
    api_key = _get_api_key()
    if not api_key:
        return None
    try:
        from openai import OpenAI  # type: ignore
        _client = OpenAI(api_key=api_key)
        return _client
    except Exception:
        return None


def analyze_command_with_openai(command: str, allowed_reports: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Usa un modelo de chat para clasificar el comando y extraer intención.
    Devuelve un dict con las mismas claves principales del parser local o None si no disponible.
    """
    client = get_openai_client()
    if client is None:
        return None

    allowed_ids = list(allowed_reports.keys())
    sys_prompt = (
        "Eres un asistente que clasifica pedidos de reportes de ventas. "
        "Debes responder ÚNICAMENTE en JSON válido con estas claves: "
        "{report_type, report_name, report_description, endpoint_type, format, params, supports_ml, confidence}. "
        f"report_type debe ser uno de: {allowed_ids}. "
        "format en {json,pdf,excel}. params puede incluir start_date, end_date (YYYY-MM-DD), "
        "group_by (product|client|category|date), forecast_days. No incluyas texto adicional."
    )

    user_prompt = (
        "Clasifica este comando y devuelve JSON válido. Si no estás seguro, escoge 'ventas_basico'.\n\n"
        f"Comando: {command}"
    )

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = completion.choices[0].message.content
        if not content:
            return None
        # Intentar parsear JSON
        content = content.strip().strip('```').strip()
        if content.lower().startswith('json'):
            content = content[4:].strip()
        data = json.loads(content)
        # Validación mínima
        if 'report_type' not in data or data['report_type'] not in allowed_ids:
            return None
        return data
    except Exception:
        return None


def chat_reply(message: str, system_hint: str = "") -> Optional[str]:
    """
    Respuesta libre del chat, opcional. Devuelve None si OpenAI no está disponible.
    """
    client = get_openai_client()
    if client is None:
        return None
    try:
        messages = []
        if system_hint:
            messages.append({"role": "system", "content": system_hint})
        messages.append({"role": "user", "content": message})
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            messages=messages,
        )
        return resp.choices[0].message.content
    except Exception:
        return None
