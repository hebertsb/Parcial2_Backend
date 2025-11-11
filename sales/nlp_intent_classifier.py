"""
Clasificador NLP ligero para intención de reportes.
Usa TF-IDF + LogisticRegression. Modelo se guarda en ml_models/nlp_intent_model.pkl
"""
from __future__ import annotations

import os
import joblib
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

from django.conf import settings


MODEL_PATH = Path(getattr(settings, 'BASE_DIR', '.')) / 'ml_models' / 'nlp_intent_model.pkl'


def _default_training_data(available_reports: Dict[str, Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    X: List[str] = []
    y: List[str] = []
    for key, info in available_reports.items():
        # Usar keywords como ejemplos base
        for kw in info.get('keywords', []):
            X.append(kw)
            y.append(key)
        # Variaciones simples
        X.append(info['name'].lower())
        y.append(key)
        X.append(info['description'].lower())
        y.append(key)
    # Algunos comodines
    extras = [
        ("reporte de ventas", 'ventas_basico'),
        ("ventas por día", 'ventas_por_fecha'),
        ("ventas por producto", 'ventas_por_producto'),
        ("ventas por cliente", 'ventas_por_cliente'),
        ("clasificacion abc", 'analisis_abc'),
        ("segmentación clientes rfm", 'analisis_rfm'),
        ("comparar periodos", 'comparativo_temporal'),
        ("inventario y stock", 'analisis_inventario'),
        ("predicciones de ventas", 'prediccion_ventas'),
    ]
    for text, label in extras:
        X.append(text)
        y.append(label)
    return X, y


def train_intent_model(available_reports: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    X, y = _default_training_data(available_reports)

    pipe = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1, 2), lowercase=True)),
        ('clf', LogisticRegression(max_iter=200))
    ])

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    pipe.fit(X_tr, y_tr)
    acc = accuracy_score(y_te, pipe.predict(X_te))

    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump({'pipeline': pipe}, MODEL_PATH)

    return {'trained': True, 'samples': len(X), 'accuracy': float(acc), 'model_path': str(MODEL_PATH)}


def is_model_available() -> bool:
    return MODEL_PATH.exists()


def load_model_or_none() -> Optional[Pipeline]:
    if not is_model_available():
        return None
    data = joblib.load(MODEL_PATH)
    return data['pipeline']


def predict_intent_or_none(text: str) -> Optional[Dict[str, Any]]:
    model = load_model_or_none()
    if model is None:
        return None
    proba = model.predict_proba([text])[0]
    classes = list(model.classes_)
    idx = int(proba.argmax())
    return {
        'label': classes[idx],
        'confidence': float(proba[idx])
    }
