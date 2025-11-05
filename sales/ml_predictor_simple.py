"""
Sistema de predicción de ventas usando Linear Regression (scikit-learn).
Alternativa más simple y rápida que Prophet.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from decimal import Decimal

from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

from sales.models import Order


class SimpleSalesPredictor:
    """
    Predictor de ventas usando regresión lineal con características polinomiales.
    """
    
    def __init__(self):
        self.model = None
        self.poly_features = None
        self.training_data = None
        self.last_trained = None
        self.metrics = {}
        self.min_date = None
        
    def _prepare_data_from_orders(self, start_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        Prepara los datos de órdenes para el modelo.
        
        Args:
            start_date: Fecha de inicio para filtrar datos (opcional)
            
        Returns:
            DataFrame con datos de ventas
        """
        # Filtrar órdenes completadas
        queryset = Order.objects.filter(status='COMPLETED')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        
        # Agrupar por día usando TruncDate
        daily_sales = queryset.annotate(
            day=TruncDate('created_at')
        ).values('day').annotate(
            total_sales=Sum('total_price'),
            order_count=Count('id')
        ).order_by('day')
        
        # Convertir a DataFrame
        if not daily_sales:
            raise ValueError("No hay datos de ventas para entrenar el modelo")
        
        df = pd.DataFrame(list(daily_sales))
        df['date'] = pd.to_datetime(df['day'])
        # Convertir Decimal a float inmediatamente
        df['sales'] = pd.to_numeric(df['total_sales'], errors='coerce').fillna(0).astype(float)
        
        # Rellenar días faltantes con 0
        df = df.set_index('date').resample('D').agg({'sales': 'sum'}).fillna(0).reset_index()
        
        return df[['date', 'sales']].copy()
    
    def _create_features(self, df: pd.DataFrame) -> tuple:
        """
        Crea características para el modelo.
        
        Args:
            df: DataFrame con columna 'date'
            
        Returns:
            Tuple (X, fechas) donde X son las características
        """
        # Guardar la fecha mínima para referencia
        if self.min_date is None:
            self.min_date = df['date'].min()
        
        # Días desde el inicio
        df['days_since_start'] = (df['date'] - self.min_date).dt.days
        
        # Características temporales
        df['day_of_week'] = df['date'].dt.dayofweek
        df['day_of_month'] = df['date'].dt.day
        df['month'] = df['date'].dt.month
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        
        # Características cíclicas para capturar estacionalidad
        df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
        df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        
        # Seleccionar características
        feature_columns = [
            'days_since_start', 'day_of_week', 'is_weekend',
            'month_sin', 'month_cos', 'day_sin', 'day_cos'
        ]
        
        X = df[feature_columns].values
        
        return X, df['date']
    
    def train(self, start_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Entrena el modelo con datos históricos.
        
        Args:
            start_date: Fecha de inicio para datos de entrenamiento
            
        Returns:
            Dict con métricas de entrenamiento
        """
        print("📊 Preparando datos de entrenamiento...")
        
        # Preparar datos
        self.training_data = self._prepare_data_from_orders(start_date)
        
        if len(self.training_data) < 30:
            raise ValueError(
                f"Se necesitan al menos 30 días de datos. "
                f"Se encontraron {len(self.training_data)} días."
            )
        
        print(f"✓ Datos preparados: {len(self.training_data)} días de ventas")
        print(f"  Rango: {self.training_data['date'].min()} - {self.training_data['date'].max()}")
        print(f"  Ventas totales: ${self.training_data['sales'].sum():,.2f}")
        print(f"  Promedio diario: ${self.training_data['sales'].mean():,.2f}")
        
        # Crear características
        X, _ = self._create_features(self.training_data)
        y = self.training_data['sales'].values.astype(float)
        
        # Crear características polinomiales para capturar tendencias no lineales
        print("\n🤖 Entrenando modelo de regresión...")
        self.poly_features = PolynomialFeatures(degree=2, include_bias=False)
        X_poly = self.poly_features.fit_transform(X)
        
        # Entrenar modelo
        self.model = LinearRegression()
        self.model.fit(X_poly, y)
        
        self.last_trained = timezone.now()
        
        # Calcular métricas
        predictions = self.model.predict(X_poly)
        residuals = y - predictions
        mae = np.mean(np.abs(residuals))
        rmse = np.sqrt(np.mean(residuals ** 2))
        mape = np.mean(np.abs(residuals / (y + 1e-10))) * 100
        r2 = self.model.score(X_poly, y)
        
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
            'mae': float(mae),
            'rmse': float(rmse),
            'mape': float(mape),
            'r2_score': float(r2)
        }
        
        print(f"✓ Modelo entrenado exitosamente")
        print(f"  R² Score: {r2:.4f}")
        print(f"  MAE: ${mae:,.2f}")
        print(f"  RMSE: ${rmse:,.2f}")
        
        return self.metrics
    
    def predict(self, days: int = 30) -> Dict[str, Any]:
        """
        Genera predicciones de ventas futuras.
        
        Args:
            days: Número de días a predecir (default: 30)
            
        Returns:
            Dict con predicciones y métricas
        """
        if self.model is None:
            raise ValueError("El modelo no ha sido entrenado. Llama a train() primero.")
        
        print(f"\n🔮 Generando predicciones para los próximos {days} días...")
        
        # Crear fechas futuras
        last_date = self.training_data['date'].max()
        future_dates = pd.date_range(
            start=last_date + timedelta(days=1),
            periods=days,
            freq='D'
        )
        
        # Crear DataFrame con fechas futuras
        future_df = pd.DataFrame({'date': future_dates})
        
        # Crear características
        X_future, _ = self._create_features(future_df)
        X_future_poly = self.poly_features.transform(X_future)
        
        # Generar predicciones
        predictions = self.model.predict(X_future_poly)
        
        # Asegurar valores no negativos
        predictions = np.maximum(predictions, 0)
        
        # Calcular intervalos de confianza (basado en error estándar de residuos)
        train_predictions = self.model.predict(
            self.poly_features.transform(self._create_features(self.training_data)[0])
        )
        residuals = self.training_data['sales'].values - train_predictions
        std_error = np.std(residuals)
        
        # Intervalo de confianza del 95% (aproximadamente 1.96 * std_error)
        confidence_interval = 1.96 * std_error
        
        # Preparar resultados
        results = []
        for date, pred in zip(future_dates, predictions):
            results.append({
                'date': date.strftime('%Y-%m-%d'),
                'predicted_sales': round(float(pred), 2),
                'lower_bound': round(max(0, float(pred - confidence_interval)), 2),
                'upper_bound': round(float(pred + confidence_interval), 2),
                'confidence': 0.95
            })
        
        # Calcular métricas de predicción
        total_predicted = sum(r['predicted_sales'] for r in results)
        avg_predicted = total_predicted / len(results)
        
        # Comparar con promedio histórico
        historical_avg = float(self.training_data['sales'].mean())
        growth_rate = ((avg_predicted - historical_avg) / historical_avg) * 100 if historical_avg > 0 else 0
        
        result = {
            'predictions': results,
            'summary': {
                'total_days': days,
                'total_predicted_sales': round(total_predicted, 2),
                'average_daily_sales': round(avg_predicted, 2),
                'historical_average': round(historical_avg, 2),
                'growth_rate_percent': round(growth_rate, 2),
                'prediction_start': results[0]['date'],
                'prediction_end': results[-1]['date'],
            },
            'model_info': {
                'last_trained': self.last_trained.isoformat() if self.last_trained else None,
                'training_samples': self.metrics.get('training_samples', 0),
                'r2_score': self.metrics.get('r2_score', 0)
            }
        }
        
        print(f"✓ Predicciones generadas")
        print(f"  Total predicho: ${total_predicted:,.2f}")
        print(f"  Promedio diario: ${avg_predicted:,.2f}")
        print(f"  Crecimiento vs histórico: {growth_rate:+.2f}%")
        
        return result
    
    def get_historical_performance(self) -> Dict[str, Any]:
        """
        Evalúa el rendimiento del modelo en datos históricos.
        
        Returns:
            Dict con métricas de rendimiento
        """
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
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """
        Alias de get_historical_performance para compatibilidad.
        
        Returns:
            Dict con métricas de rendimiento
        """
        perf = self.get_historical_performance()
        return {
            'mae': perf['mae'],
            'rmse': perf['rmse'],
            'mape': perf['mape'],
            'r2_score': perf['r2_score']
        }


def quick_predict(days: int = 30) -> Dict[str, Any]:
    """
    Función helper para entrenar y predecir rápidamente.
    
    Args:
        days: Número de días a predecir
        
    Returns:
        Dict con predicciones
        
    Ejemplo:
        >>> from sales.ml_predictor_simple import quick_predict
        >>> predictions = quick_predict(days=60)
    """
    predictor = SimpleSalesPredictor()
    predictor.train()
    return predictor.predict(days=days)
