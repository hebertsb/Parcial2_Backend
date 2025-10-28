"""
Sistema de predicción de ventas por producto individual.
Permite predecir ventas futuras de productos específicos con múltiples filtros.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict

from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

from sales.models import Order, OrderItem
from products.models import Product, Category


class ProductSalesPredictor:
    """
    Predictor de ventas por producto con filtros avanzados.
    """
    
    def __init__(self):
        self.models = {}  # Diccionario de modelos por producto
        self.poly_features = {}
        self.training_data = {}
        
    def predict_product_sales(
        self,
        product_id: int,
        days: int = 30,
        include_confidence: bool = True
    ) -> Dict[str, Any]:
        """
        Predice ventas futuras de un producto específico.
        
        Args:
            product_id: ID del producto
            days: Días a predecir
            include_confidence: Si incluir intervalos de confianza
            
        Returns:
            Dict con predicciones detalladas
        """
        try:
            product = Product.objects.select_related('category').get(id=product_id)
        except Product.DoesNotExist:
            raise ValueError(f"Producto {product_id} no encontrado")
        
        # Obtener datos históricos del producto
        historical_data = self._get_product_historical_data(product_id)
        
        if len(historical_data) < 7:  # Mínimo 7 días de datos
            return {
                'product_id': product_id,
                'product_name': product.name,
                'error': 'Datos insuficientes para predicción',
                'message': f'Se necesitan al menos 7 días de datos históricos. Se encontraron {len(historical_data)} días.',
                'suggestion': 'El producto es muy nuevo o no tiene suficiente historial de ventas.'
            }
        
        # Entrenar modelo específico para este producto
        model, poly_features, metrics = self._train_product_model(historical_data)
        
        # Generar predicciones
        predictions = self._generate_product_predictions(
            model, poly_features, historical_data, days
        )
        
        # Calcular intervalos de confianza
        if include_confidence:
            predictions = self._add_confidence_intervals(
                predictions, historical_data, model, poly_features
            )
        
        # Análisis de tendencia
        trend_analysis = self._analyze_product_trend(historical_data)
        
        # Calcular métricas útiles
        total_predicted_units = sum(p['predicted_units'] for p in predictions)
        total_predicted_revenue = sum(p['predicted_revenue'] for p in predictions)
        avg_daily_units = total_predicted_units / len(predictions)
        
        # Comparar con histórico
        historical_avg_units = historical_data['units'].mean()
        historical_avg_revenue = historical_data['revenue'].mean()
        
        growth_rate_units = ((avg_daily_units - historical_avg_units) / historical_avg_units * 100) if historical_avg_units > 0 else 0
        
        # Alertas de stock
        current_stock = product.stock
        days_until_stockout = None
        restock_recommendation = None
        
        if avg_daily_units > 0:
            days_until_stockout = int(current_stock / avg_daily_units)
            if days_until_stockout < days:
                # Calcular cuánto necesita para el período
                units_needed = total_predicted_units - current_stock
                restock_recommendation = max(0, int(units_needed * 1.2))  # +20% margen de seguridad
        
        return {
            'product': {
                'id': product.id,
                'name': product.name,
                'category': product.category.name if product.category else None,
                'current_price': float(product.price),
                'current_stock': product.stock
            },
            'predictions': predictions,
            'summary': {
                'prediction_period_days': days,
                'total_predicted_units': round(total_predicted_units, 2),
                'total_predicted_revenue': round(total_predicted_revenue, 2),
                'average_daily_units': round(avg_daily_units, 2),
                'average_daily_revenue': round(total_predicted_revenue / len(predictions), 2),
                'growth_vs_historical': {
                    'units_growth_percent': round(growth_rate_units, 2),
                    'historical_avg_units': round(historical_avg_units, 2),
                    'historical_avg_revenue': round(historical_avg_revenue, 2)
                }
            },
            'trend': trend_analysis,
            'stock_alert': {
                'days_until_stockout': days_until_stockout,
                'restock_recommended': restock_recommendation,
                'alert_level': self._get_alert_level(days_until_stockout, days) if days_until_stockout else 'OK'
            },
            'model_metrics': metrics,
            'generated_at': timezone.now().isoformat()
        }
    
    def predict_category_sales(
        self,
        category_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Predice ventas totales de una categoría.
        
        Args:
            category_id: ID de la categoría
            days: Días a predecir
            
        Returns:
            Dict con predicciones de la categoría
        """
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            raise ValueError(f"Categoría {category_id} no encontrada")
        
        # Obtener todos los productos de la categoría
        products = Product.objects.filter(category_id=category_id)
        
        if not products.exists():
            return {
                'category_id': category_id,
                'category_name': category.name,
                'error': 'No hay productos en esta categoría'
            }
        
        # Predecir cada producto
        category_predictions = []
        total_predicted_units = 0
        total_predicted_revenue = 0
        
        for product in products:
            try:
                pred = self.predict_product_sales(
                    product_id=product.id,
                    days=days,
                    include_confidence=False
                )
                
                if 'error' not in pred:
                    category_predictions.append({
                        'product_id': product.id,
                        'product_name': product.name,
                        'predicted_units': pred['summary']['total_predicted_units'],
                        'predicted_revenue': pred['summary']['total_predicted_revenue'],
                        'current_stock': product.stock
                    })
                    total_predicted_units += pred['summary']['total_predicted_units']
                    total_predicted_revenue += pred['summary']['total_predicted_revenue']
            except Exception:
                continue
        
        # Ordenar por unidades predichas
        category_predictions.sort(key=lambda x: x['predicted_units'], reverse=True)
        
        return {
            'category': {
                'id': category_id,
                'name': category.name,
                'total_products': len(category_predictions)
            },
            'summary': {
                'prediction_period_days': days,
                'total_predicted_units': round(total_predicted_units, 2),
                'total_predicted_revenue': round(total_predicted_revenue, 2)
            },
            'products': category_predictions,
            'top_products': category_predictions[:5],
            'generated_at': timezone.now().isoformat()
        }
    
    def compare_products(
        self,
        product_ids: List[int],
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Compara predicciones de múltiples productos.
        
        Args:
            product_ids: Lista de IDs de productos
            days: Días a predecir
            
        Returns:
            Dict con comparación de productos
        """
        comparisons = []
        
        for product_id in product_ids:
            try:
                pred = self.predict_product_sales(
                    product_id=product_id,
                    days=days,
                    include_confidence=False
                )
                
                if 'error' not in pred:
                    comparisons.append({
                        'product_id': product_id,
                        'product_name': pred['product']['name'],
                        'category': pred['product']['category'],
                        'predicted_units': pred['summary']['total_predicted_units'],
                        'predicted_revenue': pred['summary']['total_predicted_revenue'],
                        'growth_percent': pred['summary']['growth_vs_historical']['units_growth_percent'],
                        'current_stock': pred['product']['current_stock'],
                        'days_until_stockout': pred['stock_alert']['days_until_stockout']
                    })
            except Exception as e:
                comparisons.append({
                    'product_id': product_id,
                    'error': str(e)
                })
        
        # Ordenar por unidades predichas
        valid_comparisons = [c for c in comparisons if 'error' not in c]
        valid_comparisons.sort(key=lambda x: x['predicted_units'], reverse=True)
        
        return {
            'comparison': valid_comparisons,
            'period_days': days,
            'best_performer': valid_comparisons[0] if valid_comparisons else None,
            'generated_at': timezone.now().isoformat()
        }
    
    def get_top_products_forecast(
        self,
        days: int = 30,
        limit: int = 10,
        category_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Obtiene los productos que se predice venderán más.
        
        Args:
            days: Días a predecir
            limit: Número de productos a retornar
            category_id: Filtrar por categoría (opcional)
            
        Returns:
            Ranking de productos con mejores predicciones
        """
        # Obtener productos con ventas recientes
        since_date = timezone.now() - timedelta(days=60)
        
        query = Product.objects.filter(
            order_items__order__status='COMPLETED',
            order_items__order__created_at__gte=since_date,
            stock__gt=0
        )
        
        if category_id:
            query = query.filter(category_id=category_id)
        
        products = query.distinct()[:50]  # Limitar a top 50 para no sobrecargar
        
        rankings = []
        
        for product in products:
            try:
                pred = self.predict_product_sales(
                    product_id=product.id,
                    days=days,
                    include_confidence=False
                )
                
                if 'error' not in pred:
                    rankings.append({
                        'rank': 0,  # Se asignará después
                        'product_id': product.id,
                        'product_name': product.name,
                        'category': pred['product']['category'],
                        # Cambiar nombre: predicted_units → predicted_sales
                        'predicted_sales': pred['summary']['total_predicted_units'],
                        'predicted_revenue': pred['summary']['total_predicted_revenue'],
                        # Agregar campos nuevos
                        'predicted_daily_sales': pred['summary']['average_daily_units'],
                        'growth_rate': pred['summary']['growth_vs_historical']['units_growth_percent'],
                        'days_until_stockout': pred['stock_alert']['days_until_stockout'],
                        'restock_recommendation': pred['stock_alert']['restock_recommended'],
                        # Campos existentes
                        'trend': pred['trend']['trend_direction'],
                        'current_stock': product.stock,
                        # Agregar stock_status
                        'stock_status': pred['stock_alert']['alert_level']
                    })
            except Exception:
                continue
        
        # Ordenar por unidades predichas (usar nueva clave)
        rankings.sort(key=lambda x: x['predicted_sales'], reverse=True)
        
        # Asignar ranks
        for i, item in enumerate(rankings[:limit], 1):
            item['rank'] = i
        
        return {
            'forecast_period_days': days,
            'prediction_days': days,  # Alias para frontend
            'top_products': rankings[:limit],
            'total_analyzed': len(rankings),
            'total_products': len(rankings),  # Alias para frontend
            'category_filter': category_id,
            'generated_at': timezone.now().isoformat()
        }
    
    def _get_product_historical_data(self, product_id: int) -> pd.DataFrame:
        """Obtiene datos históricos de ventas del producto."""
        # Obtener últimos 90 días
        since_date = timezone.now() - timedelta(days=90)
        
        daily_sales = OrderItem.objects.filter(
            product_id=product_id,
            order__status='COMPLETED',
            order__created_at__gte=since_date
        ).annotate(
            day=TruncDate('order__created_at')
        ).values('day').annotate(
            units=Sum('quantity'),
            revenue=Sum(F('price') * F('quantity'))
        ).order_by('day')
        
        if not daily_sales:
            return pd.DataFrame(columns=['date', 'units', 'revenue'])
        
        df = pd.DataFrame(list(daily_sales))
        df['date'] = pd.to_datetime(df['day'])
        df['units'] = pd.to_numeric(df['units'], errors='coerce').fillna(0).astype(float)
        df['revenue'] = pd.to_numeric(df['revenue'], errors='coerce').fillna(0).astype(float)
        
        # Rellenar días faltantes con 0
        df = df.set_index('date').resample('D').agg({
            'units': 'sum',
            'revenue': 'sum'
        }).fillna(0).reset_index()
        
        return df
    
    def _train_product_model(self, df: pd.DataFrame) -> tuple:
        """Entrena modelo para el producto."""
        # Crear características temporales
        df['days_since_start'] = (df['date'] - df['date'].min()).dt.days
        df['day_of_week'] = df['date'].dt.dayofweek
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        
        X = df[['days_since_start', 'day_of_week', 'is_weekend']].values
        y = df['units'].values.astype(float)
        
        # Características polinomiales
        poly = PolynomialFeatures(degree=2, include_bias=False)
        X_poly = poly.fit_transform(X)
        
        # Entrenar modelo
        model = LinearRegression()
        model.fit(X_poly, y)
        
        # Calcular métricas
        predictions = model.predict(X_poly)
        residuals = y - predictions
        mae = np.mean(np.abs(residuals))
        rmse = np.sqrt(np.mean(residuals ** 2))
        r2 = model.score(X_poly, y)
        
        metrics = {
            'mae': float(mae),
            'rmse': float(rmse),
            'r2_score': float(r2),
            'training_days': len(df)
        }
        
        return model, poly, metrics
    
    def _generate_product_predictions(
        self,
        model,
        poly_features,
        historical_data: pd.DataFrame,
        days: int
    ) -> List[Dict[str, Any]]:
        """Genera predicciones futuras."""
        last_date = historical_data['date'].max()
        future_dates = pd.date_range(
            start=last_date + timedelta(days=1),
            periods=days,
            freq='D'
        )
        
        # Obtener precio actual del producto
        avg_price = historical_data['revenue'].sum() / max(historical_data['units'].sum(), 1)
        
        predictions = []
        days_since_start_base = (last_date - historical_data['date'].min()).days
        
        for i, date in enumerate(future_dates, 1):
            days_since_start = days_since_start_base + i
            day_of_week = date.dayofweek
            is_weekend = 1 if day_of_week >= 5 else 0
            
            X = np.array([[days_since_start, day_of_week, is_weekend]])
            X_poly = poly_features.transform(X)
            
            predicted_units = max(0, model.predict(X_poly)[0])
            predicted_revenue = predicted_units * avg_price
            
            predictions.append({
                'date': date.strftime('%Y-%m-%d'),
                'day_of_week': date.strftime('%A'),
                'predicted_units': round(float(predicted_units), 2),
                'predicted_revenue': round(float(predicted_revenue), 2)
            })
        
        return predictions
    
    def _add_confidence_intervals(
        self,
        predictions: List[Dict],
        historical_data: pd.DataFrame,
        model,
        poly_features
    ) -> List[Dict]:
        """Agrega intervalos de confianza a las predicciones."""
        # Calcular error estándar
        X_train = historical_data[['days_since_start', 'day_of_week', 'is_weekend']].values
        X_train_poly = poly_features.transform(X_train)
        y_train = historical_data['units'].values
        
        train_predictions = model.predict(X_train_poly)
        residuals = y_train - train_predictions
        std_error = np.std(residuals)
        
        # Intervalo del 95%
        margin = 1.96 * std_error
        
        for pred in predictions:
            pred['confidence_interval'] = {
                'lower_units': max(0, round(pred['predicted_units'] - margin, 2)),
                'upper_units': round(pred['predicted_units'] + margin, 2)
            }
        
        return predictions
    
    def _analyze_product_trend(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analiza la tendencia del producto."""
        if len(df) < 7:
            return {'trend_direction': 'insufficient_data'}
        
        # Comparar primera y segunda mitad
        mid_point = len(df) // 2
        first_half_avg = df['units'][:mid_point].mean()
        second_half_avg = df['units'][mid_point:].mean()
        
        if second_half_avg > first_half_avg * 1.1:
            direction = 'growing'
        elif second_half_avg < first_half_avg * 0.9:
            direction = 'declining'
        else:
            direction = 'stable'
        
        change_percent = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0
        
        return {
            'trend_direction': direction,
            'change_percent': round(change_percent, 2),
            'first_half_avg': round(first_half_avg, 2),
            'second_half_avg': round(second_half_avg, 2)
        }
    
    def _get_alert_level(self, days_until_stockout: int, prediction_days: int) -> str:
        """Determina el nivel de alerta de stock."""
        if days_until_stockout <= 7:
            return 'CRITICAL'
        elif days_until_stockout <= 14:
            return 'WARNING'
        elif days_until_stockout < prediction_days:
            return 'CAUTION'
        else:
            return 'OK'
    
    def get_multi_period_forecast(
        self,
        periods: List[int],
        limit: int = 5,
        category_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Obtiene predicciones para múltiples períodos en una sola llamada.
        
        Args:
            periods: Lista de períodos a predecir (ej: [7, 14, 30, 60, 90])
            limit: Número de productos por período
            category_id: Filtrar por categoría (opcional)
            
        Returns:
            Dict con forecasts para cada período
        """
        if not periods:
            raise ValueError("Se requiere al menos un período")
        
        if len(periods) > 10:
            raise ValueError("Máximo 10 períodos permitidos")
        
        forecasts = {}
        
        for days in periods:
            if days < 1 or days > 365:
                raise ValueError(f"Período {days} fuera de rango (1-365)")
            
            try:
                forecast = self.get_top_products_forecast(
                    days=days,
                    limit=limit,
                    category_id=category_id
                )
                forecasts[f'{days}d'] = forecast
            except Exception as e:
                forecasts[f'{days}d'] = {
                    'error': str(e),
                    'days': days
                }
        
        return {
            'forecasts': forecasts,
            'periods_requested': periods,
            'products_per_period': limit,
            'category_filter': category_id,
            'generated_at': timezone.now().isoformat()
        }


# Instancia singleton
product_predictor = ProductSalesPredictor()
