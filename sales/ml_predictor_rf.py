"""
Predictor de ventas usando RandomForestRegressor (scikit-learn).
Comparte el mismo contrato que SimpleSalesPredictor:
 - train(start_date: Optional[datetime]) -> Dict[str, Any] con métricas
 - predict(days: int) -> Dict[str, Any] con predicciones
 - get_historical_performance() -> Dict[str, Any]
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from sklearn.ensemble import RandomForestRegressor

from sales.models import Order


class RandomForestSalesPredictor:
    def __init__(self):
        self.model: Optional[RandomForestRegressor] = None
        self.training_data: Optional[pd.DataFrame] = None
        self.last_trained = None
        self.metrics: Dict[str, Any] = {}
        self.min_date: Optional[pd.Timestamp] = None

    def _prepare_data_from_orders(self, start_date: Optional[datetime] = None) -> pd.DataFrame:
        queryset = Order.objects.filter(status='COMPLETED')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)

        daily_sales = queryset.annotate(
            day=TruncDate('created_at')
        ).values('day').annotate(
            total_sales=Sum('total_price'),
            order_count=Count('id')
        ).order_by('day')

        if not daily_sales:
            raise ValueError("No hay datos de ventas para entrenar el modelo")

        df = pd.DataFrame(list(daily_sales))
        df['date'] = pd.to_datetime(df['day'])
        df['sales'] = pd.to_numeric(df['total_sales'], errors='coerce').fillna(0).astype(float)
        df = df.set_index('date').resample('D').agg({'sales': 'sum'}).fillna(0).reset_index()
        return df[['date', 'sales']].copy()

    def _create_features(self, df: pd.DataFrame) -> tuple:
        if self.min_date is None:
            self.min_date = pd.to_datetime(df['date'].min())

        base = pd.Timestamp(self.min_date) if self.min_date is not None else pd.Timestamp(df['date'].min())
        dates = pd.to_datetime(df['date'])
        df['days_since_start'] = (dates - base).dt.days
        df['day_of_week'] = df['date'].dt.dayofweek
        df['month'] = df['date'].dt.month
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        # Señales cíclicas básicas
        df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
        df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)

        feature_columns = [
            'days_since_start', 'day_of_week', 'is_weekend',
            'month_sin', 'month_cos', 'dow_sin', 'dow_cos'
        ]
        X = df[feature_columns].values
        return X, df['date']

    def train(self, start_date: Optional[datetime] = None) -> Dict[str, Any]:
        self.training_data = self._prepare_data_from_orders(start_date)
        if len(self.training_data) < 30:
            raise ValueError(f"Se necesitan al menos 30 días de datos. Se encontraron {len(self.training_data)} días.")

        X, _ = self._create_features(self.training_data)
        y = self.training_data['sales'].values.astype(float)

        # Modelo RF optimizado para velocidad en este entorno (menos árboles, profundidad limitada)
        # Si luego se requiere mayor precisión se puede subir n_estimators y remover max_depth.
        self.model = RandomForestRegressor(
            n_estimators=80,           # antes 300
            max_depth=14,              # limitar profundidad acelera y reduce overfitting
            random_state=42,
            n_jobs=-1,
            min_samples_leaf=2,
            bootstrap=True
        )
        # Nota: Con pocos árboles la varianza aumenta; el intervalo de confianza puede ser más amplio.
        self.model.fit(X, y)

        self.last_trained = timezone.now()
        preds = self.model.predict(X)
        residuals = y - preds
        mae = float(np.mean(np.abs(residuals)))
        rmse = float(np.sqrt(np.mean(residuals ** 2)))
        mape = float(np.mean(np.abs(residuals / (y + 1e-10))) * 100)
        # R2 manual para evitar dependencia de score con out-of-bag
        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

        self.metrics = {
            'training_samples': len(self.training_data),
            'start_date': self.training_data['date'].min().strftime('%Y-%m-%d'),
            'end_date': self.training_data['date'].max().strftime('%Y-%m-%d'),
            'total_sales': float(self.training_data['sales'].sum()),
            'average_daily_sales': float(self.training_data['sales'].mean()),
            'std_daily_sales': float(self.training_data['sales'].std()),
            'min_daily_sales': float(self.training_data['sales'].min()),
            'max_daily_sales': float(self.training_data['sales'].max()),
            'trained_at': self.last_trained.isoformat(),
            'mae': mae,
            'rmse': rmse,
            'mape': mape,
            'r2_score': float(r2),
        }
        return self.metrics

    def predict(self, days: int = 30) -> Dict[str, Any]:
        if self.model is None or self.training_data is None:
            raise ValueError("El modelo no ha sido entrenado. Llama a train() primero.")

        last_date = self.training_data['date'].max()
        future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=days, freq='D')
        future_df = pd.DataFrame({'date': future_dates})

        X_future, _ = self._create_features(future_df)
        preds = self.model.predict(X_future)
        preds = np.maximum(preds, 0)

        # Estimar intervalo de confianza usando residuales de entrenamiento
        X_train, _ = self._create_features(self.training_data.copy())
        train_preds = self.model.predict(X_train)
        residuals = self.training_data['sales'].values - train_preds
        std_error = np.std(residuals)
        ci = 1.96 * std_error

        results = []
        for date, pred in zip(future_dates, preds):
            results.append({
                'date': date.strftime('%Y-%m-%d'),
                'predicted_sales': round(float(pred), 2),
                'lower_bound': round(max(0.0, float(pred - ci)), 2),
                'upper_bound': round(float(pred + ci), 2),
                'confidence': 0.95,
            })

        total_pred = float(np.sum([r['predicted_sales'] for r in results]))
        avg_pred = total_pred / len(results)
        hist_avg = float(self.training_data['sales'].mean())
        growth = ((avg_pred - hist_avg) / hist_avg) * 100 if hist_avg > 0 else 0.0

        return {
            'predictions': results,
            'summary': {
                'total_days': days,
                'total_predicted_sales': round(total_pred, 2),
                'average_daily_sales': round(avg_pred, 2),
                'historical_average': round(hist_avg, 2),
                'growth_rate_percent': round(growth, 2),
                'prediction_start': results[0]['date'],
                'prediction_end': results[-1]['date'],
            },
            'model_info': {
                'last_trained': self.last_trained.isoformat() if self.last_trained else None,
                'training_samples': self.metrics.get('training_samples', 0),
                'r2_score': self.metrics.get('r2_score', 0),
                'algorithm': 'rf'
            }
        }

    def get_historical_performance(self) -> Dict[str, Any]:
        if self.model is None or self.training_data is None:
            raise ValueError("El modelo no ha sido entrenado.")
        return {
            'mae': round(self.metrics.get('mae', 0), 2),
            'rmse': round(self.metrics.get('rmse', 0), 2),
            'mape': round(self.metrics.get('mape', 0), 2),
            'r2_score': round(self.metrics.get('r2_score', 0), 4),
            'description': {
                'mae': 'Error Absoluto Medio (menor es mejor)',
                'rmse': 'Raíz del Error Cuadrático Medio (menor es mejor)',
                'mape': 'Error Porcentual Absoluto Medio (menor es mejor)',
                'r2_score': 'Coeficiente de Determinación (más cercano a 1 es mejor)'
            }
        }
