"""
Tests unitarios para el sistema de Machine Learning de predicción de ventas.
"""
import os
import json
import shutil
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from sales.models import Order, OrderItem
from products.models import Product, Category
from sales.ml_data_generator import SalesDataGenerator
from sales.ml_predictor_simple import SimpleSalesPredictor
from sales.ml_model_manager import ModelManager


User = get_user_model()


class MLDataGeneratorTests(TransactionTestCase):
    """Tests para el generador de datos de demostración."""
    
    def setUp(self):
        """Configura el ambiente de prueba."""
        self.generator = SalesDataGenerator()
        
        # Limpiar datos previos
        Order.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
    
    def test_create_demo_products(self):
        """Test: Crear productos de demostración."""
        products = self.generator._create_demo_products()
        
        self.assertGreater(len(products), 0)
        self.assertEqual(Product.objects.count(), len(products))
        
        # Verificar que los productos tienen precios válidos
        for product in products:
            self.assertGreater(product.price, 0)
            self.assertIsInstance(product.price, Decimal)
    
    def test_create_demo_customers(self):
        """Test: Crear clientes de demostración."""
        customers = self.generator._create_demo_customers()
        
        self.assertGreater(len(customers), 0)
        self.assertEqual(
            User.objects.filter(is_superuser=False).count(),
            len(customers)
        )
    
    def test_seasonal_multiplier(self):
        """Test: Multiplicador estacional."""
        # Diciembre debería tener multiplicador alto (navidad)
        december_date = datetime(2024, 12, 15)
        dec_multiplier = self.generator._get_seasonal_multiplier(december_date)
        
        # Enero debería tener multiplicador bajo (post-navidad)
        january_date = datetime(2024, 1, 15)
        jan_multiplier = self.generator._get_seasonal_multiplier(january_date)
        
        self.assertGreater(dec_multiplier, jan_multiplier)
    
    def test_generate_sales_data(self):
        """Test: Generar datos de ventas completos."""
        result = self.generator.generate_demo_data(clear_existing=False) # months=3)
        
        self.assertIn('orders_created', result)
        self.assertIn('total_revenue', result)
        self.assertIn('date_range', result)
        
        self.assertGreater(result['orders_created'], 0)
        self.assertGreater(result['total_revenue'], 0)
        
        # Verificar que las órdenes se crearon
        self.assertEqual(Order.objects.count(), result['orders_created'])


class SimpleSalesPredictorTests(TestCase):
    """Tests para el predictor ML simple."""
    
    @classmethod
    def setUpTestData(cls):
        """Configura datos de prueba para todos los tests."""
        # Crear datos de demostración pequeños
        generator = SalesDataGenerator()
        generator.generate_demo_data(clear_existing=False) # months=6)
    
    def setUp(self):
        """Configura cada test."""
        self.predictor = SimpleSalesPredictor()
    
    def test_train_model(self):
        """Test: Entrenar modelo con datos."""
        metrics = self.predictor.train()
        
        self.assertIsNotNone(self.predictor.model)
        self.assertIsNotNone(self.predictor.poly_features)
        self.assertIn('mae', metrics)
        self.assertIn('rmse', metrics)
        self.assertIn('r2_score', metrics)
        
        # Verificar que las métricas son números válidos
        self.assertIsInstance(metrics['mae'], (int, float))
        self.assertIsInstance(metrics['rmse'], (int, float))
        self.assertIsInstance(metrics['r2_score'], (int, float))
    
    def test_predict_without_training_raises_error(self):
        """Test: Predecir sin entrenar lanza error."""
        with self.assertRaises(ValueError):
            self.predictor.predict(days=7)
    
    def test_predict_future_sales(self):
        """Test: Predecir ventas futuras."""
        self.predictor.train()
        
        days = 14
        result = self.predictor.predict(days=days)
        
        self.assertIn('predictions', result)
        self.assertIn('summary', result)
        self.assertIn('model_info', result)
        
        predictions = result['predictions']
        self.assertEqual(len(predictions), days)
        
        # Verificar estructura de cada predicción
        for pred in predictions:
            self.assertIn('date', pred)
            self.assertIn('predicted_sales', pred)
            self.assertIn('lower_bound', pred)
            self.assertIn('upper_bound', pred)
            self.assertIn('confidence', pred)
            
            # Verificar que los valores son positivos
            self.assertGreaterEqual(pred['predicted_sales'], 0)
            self.assertGreaterEqual(pred['lower_bound'], 0)
            self.assertGreater(pred['upper_bound'], pred['predicted_sales'])
    
    def test_get_performance_metrics(self):
        """Test: Obtener métricas de rendimiento."""
        self.predictor.train()
        
        metrics = self.predictor.get_performance_metrics()
        
        self.assertIn('mae', metrics)
        self.assertIn('rmse', metrics)
        self.assertIn('mape', metrics)
        self.assertIn('r2_score', metrics)
        
        # Verificar que MAE <= RMSE (propiedad matemática)
        self.assertLessEqual(metrics['mae'], metrics['rmse'])
    
    def test_get_historical_performance(self):
        """Test: Obtener rendimiento histórico con descripciones."""
        self.predictor.train()
        
        performance = self.predictor.get_historical_performance()
        
        self.assertIn('description', performance)
        self.assertIsInstance(performance['description'], dict)


class ModelManagerTests(TestCase):
    """Tests para el gestor de modelos."""
    
    @classmethod
    def setUpTestData(cls):
        """Configura datos de prueba."""
        generator = SalesDataGenerator()
        generator.generate_demo_data(clear_existing=False) # months=6)
    
    def setUp(self):
        """Configura cada test."""
        self.manager = ModelManager()
        
        # Limpiar modelos previos
        if self.manager.models_dir.exists():
            for file in self.manager.models_dir.glob('sales_model_*.pkl'):
                file.unlink()
            if self.manager.metadata_file.exists():
                self.manager.metadata_file.unlink()
    
    def test_save_and_load_model(self):
        """Test: Guardar y cargar modelo."""
        # Entrenar y guardar
        predictor = SimpleSalesPredictor()
        predictor.train()
        
        version = self.manager.save_model(predictor, notes="Test model")
        
        # Cargar
        loaded_predictor = self.manager.load_model(version)
        
        self.assertIsNotNone(loaded_predictor.model)
        self.assertIsNotNone(loaded_predictor.poly_features)
        
        # Verificar que puede predecir
        predictions = loaded_predictor.predict(days=7)
        self.assertEqual(len(predictions['predictions']), 7)
    
    def test_get_current_model_version(self):
        """Test: Obtener versión del modelo actual."""
        # Sin modelos
        self.assertIsNone(self.manager.current_model_version)
        
        # Crear modelo
        predictor = SimpleSalesPredictor()
        predictor.train()
        version = self.manager.save_model(predictor)
        
        # Verificar versión actual
        self.assertEqual(self.manager.current_model_version, version)
    
    def test_get_models_info(self):
        """Test: Obtener información de modelos."""
        # Sin modelos
        info = self.manager.get_models_info()
        self.assertEqual(len(info['models']), 0)
        self.assertIsNone(info['current_model'])
        
        # Crear modelo
        predictor = SimpleSalesPredictor()
        predictor.train()
        self.manager.save_model(predictor, notes="Test model 1")
        
        # Verificar información
        info = self.manager.get_models_info()
        self.assertEqual(len(info['models']), 1)
        self.assertIsNotNone(info['current_model'])
        self.assertIn('version', info['current_model'])
        self.assertIn('file_size_mb', info['current_model'])
    
    def test_get_or_create_current_model(self):
        """Test: Obtener o crear modelo actual."""
        # Primera llamada: crea modelo
        predictor1 = self.manager.get_or_create_current_model()
        self.assertIsNotNone(predictor1.model)
        
        version1 = self.manager.current_model_version
        
        # Segunda llamada: carga modelo existente
        predictor2 = self.manager.get_or_create_current_model()
        version2 = self.manager.current_model_version
        
        self.assertEqual(version1, version2)
    
    def test_list_models(self):
        """Test: Listar modelos guardados."""
        # Crear varios modelos
        for i in range(3):
            predictor = SimpleSalesPredictor()
            predictor.train()
            self.manager.save_model(predictor, notes=f"Model {i}")
        
        models = self.manager.list_models()
        self.assertEqual(len(models), 3)
        
        # Verificar estructura
        for model_info in models:
            self.assertIn('version', model_info)
            self.assertIn('saved_at', model_info)
            self.assertIn('file_size_mb', model_info)


class MLAPIEndpointsTests(TestCase):
    """Tests para los endpoints de la API ML."""
    
    @classmethod
    def setUpTestData(cls):
        """Configura datos de prueba."""
        # Crear usuario admin
        cls.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='testpass123'
        )
        
        # Crear usuario normal
        cls.normal_user = User.objects.create_user(
            username='user_test',
            email='user@test.com',
            password='testpass123'
        )
        
        # Generar datos de demostración
        generator = SalesDataGenerator()
        generator.generate_demo_data(clear_existing=False) # months=6)
    
    def setUp(self):
        """Configura cada test."""
        self.client = APIClient()
        
        # Limpiar modelos previos
        manager = ModelManager()
        if manager.models_dir.exists():
            for file in manager.models_dir.glob('sales_model_*.pkl'):
                file.unlink()
            if manager.metadata_file.exists():
                manager.metadata_file.unlink()
    
    def test_endpoints_require_admin_authentication(self):
        """Test: Endpoints requieren autenticación de admin."""
        endpoints = [
            '/api/orders/ml/predictions/',
            '/api/orders/ml/dashboard/',
            '/api/orders/ml/performance/',
            '/api/orders/ml/models/',
        ]
        
        for endpoint in endpoints:
            # Sin autenticación
            response = self.client.get(endpoint)
            self.assertIn(response.status_code, [401, 403])
            
            # Con usuario normal
            self.client.force_authenticate(user=self.normal_user)
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 403)
            
            self.client.force_authenticate(user=None)
    
    def test_train_model_endpoint(self):
        """Test: Endpoint de entrenamiento de modelo."""
        self.client.force_authenticate(user=self.admin_user)
        
        response = self.client.post('/api/orders/ml/train/', {
            'notes': 'Test training'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('success', response.data)
        self.assertIn('data', response.data)
        
        data = response.data['data']
        self.assertIn('model_version', data)
        self.assertIn('metrics', data)
    
    def test_predictions_endpoint(self):
        """Test: Endpoint de predicciones."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Primero entrenar modelo
        self.client.post('/api/orders/ml/train/')
        
        # Obtener predicciones
        response = self.client.get('/api/orders/ml/predictions/?days=14')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.data)
        
        data = response.data['data']
        self.assertIn('predictions', data)
        self.assertIn('summary', data)
        self.assertEqual(len(data['predictions']), 14)
    
    def test_predictions_default_days(self):
        """Test: Predicciones con días por defecto."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Entrenar modelo
        self.client.post('/api/orders/ml/train/')
        
        # Sin especificar días (default 30)
        response = self.client.get('/api/orders/ml/predictions/')
        
        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        self.assertEqual(len(data['predictions']), 30)
    
    def test_performance_endpoint(self):
        """Test: Endpoint de métricas de rendimiento."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Entrenar modelo
        self.client.post('/api/orders/ml/train/')
        
        # Obtener métricas
        response = self.client.get('/api/orders/ml/performance/')
        
        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        
        self.assertIn('mae', data)
        self.assertIn('rmse', data)
        self.assertIn('mape', data)
        self.assertIn('r2_score', data)
    
    def test_models_list_endpoint(self):
        """Test: Endpoint de lista de modelos."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Entrenar algunos modelos
        self.client.post('/api/orders/ml/train/', {'notes': 'Model 1'})
        self.client.post('/api/orders/ml/train/', {'notes': 'Model 2'})
        
        # Listar modelos
        response = self.client.get('/api/orders/ml/models/')
        
        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        
        self.assertIn('models', data)
        self.assertIn('current_model', data)
        self.assertGreaterEqual(len(data['models']), 2)
    
    def test_dashboard_endpoint(self):
        """Test: Endpoint del dashboard ML."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Entrenar modelo
        self.client.post('/api/orders/ml/train/')
        
        # Obtener dashboard
        response = self.client.get('/api/orders/ml/dashboard/')
        
        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        
        self.assertIn('current_model', data)
        self.assertIn('predictions_30_days', data)
        self.assertIn('performance_metrics', data)
        self.assertIn('training_data_info', data)
    
    def test_generate_demo_data_endpoint(self):
        """Test: Endpoint de generación de datos de demostración."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Limpiar datos previos
        Order.objects.all().delete()
        
        response = self.client.post('/api/orders/ml/generate-demo-data/', {
            'months': 3,
            'clear_existing': True
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        
        self.assertIn('orders_created', data)
        self.assertIn('total_revenue', data)
        self.assertGreater(data['orders_created'], 0)
    
    def test_forecast_components_endpoint(self):
        """Test: Endpoint de componentes del forecast."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Entrenar modelo
        self.client.post('/api/orders/ml/train/')
        
        # Obtener componentes
        response = self.client.get('/api/orders/ml/forecast-components/')
        
        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        
        self.assertIn('model_type', data)
        self.assertIn('features', data)
    
    def test_invalid_days_parameter(self):
        """Test: Parámetro days inválido."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Entrenar modelo
        self.client.post('/api/orders/ml/train/')
        
        # Días negativos
        response = self.client.get('/api/orders/ml/predictions/?days=-5')
        self.assertEqual(response.status_code, 400)
        
        # Días demasiado grandes
        response = self.client.get('/api/orders/ml/predictions/?days=500')
        self.assertEqual(response.status_code, 400)
    
    def test_predictions_without_model_trains_automatically(self):
        """Test: Predicciones sin modelo entrena automáticamente."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Pedir predicciones sin entrenar primero
        response = self.client.get('/api/orders/ml/predictions/?days=7')
        
        # Debería entrenar automáticamente
        self.assertEqual(response.status_code, 200)
        self.assertIn('predictions', response.data['data'])


class MLIntegrationTests(TransactionTestCase):
    """Tests de integración del sistema ML completo."""
    
    def setUp(self):
        """Configura el ambiente de prueba."""
        # Crear admin
        self.admin = User.objects.create_superuser(
            username='admin_integration',
            email='admin@integration.com',
            password='pass123'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        
        # Limpiar datos
        Order.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        
        # Limpiar modelos
        manager = ModelManager()
        if manager.models_dir.exists():
            for file in manager.models_dir.glob('sales_model_*.pkl'):
                file.unlink()
            if manager.metadata_file.exists():
                manager.metadata_file.unlink()
    
    def test_complete_ml_workflow(self):
        """Test: Flujo completo de trabajo ML."""
        # 1. Generar datos de demostración
        response = self.client.post('/api/orders/ml/generate-demo-data/', {
            'months': 6,
            'clear_existing': True
        })
        self.assertEqual(response.status_code, 200)
        orders_created = response.data['data']['orders_created']
        self.assertGreater(orders_created, 0)
        
        # 2. Entrenar modelo
        response = self.client.post('/api/orders/ml/train/', {
            'notes': 'Integration test model'
        })
        self.assertEqual(response.status_code, 200)
        model_version = response.data['data']['model_version']
        self.assertIsNotNone(model_version)
        
        # 3. Obtener predicciones
        response = self.client.get('/api/orders/ml/predictions/?days=30')
        self.assertEqual(response.status_code, 200)
        predictions = response.data['data']['predictions']
        self.assertEqual(len(predictions), 30)
        
        # 4. Verificar métricas
        response = self.client.get('/api/orders/ml/performance/')
        self.assertEqual(response.status_code, 200)
        metrics = response.data['data']
        self.assertIn('mae', metrics)
        
        # 5. Ver dashboard
        response = self.client.get('/api/orders/ml/dashboard/')
        self.assertEqual(response.status_code, 200)
        dashboard = response.data['data']
        self.assertEqual(dashboard['current_model']['version'], model_version)
        
        # 6. Listar modelos
        response = self.client.get('/api/orders/ml/models/')
        self.assertEqual(response.status_code, 200)
        models = response.data['data']['models']
        self.assertGreaterEqual(len(models), 1)
    
    def test_retrain_workflow(self):
        """Test: Flujo de re-entrenamiento."""
        # Generar datos y entrenar
        self.client.post('/api/orders/ml/generate-demo-data/', {'months': 6})
        response1 = self.client.post('/api/orders/ml/train/')
        version1 = response1.data['data']['model_version']
        
        # Re-entrenar
        response2 = self.client.post('/api/orders/ml/train/', {
            'notes': 'Retrained model'
        })
        version2 = response2.data['data']['model_version']
        
        # Versiones diferentes
        self.assertNotEqual(version1, version2)
        
        # El modelo actual es el nuevo
        manager = ModelManager()
        self.assertEqual(manager.current_model_version, version2)
        
        # Ambos modelos existen
        models = manager.list_models()
        self.assertEqual(len(models), 2)


class MLPerformanceTests(TestCase):
    """Tests de rendimiento del sistema ML."""
    
    @classmethod
    def setUpTestData(cls):
        """Configura datos de prueba."""
        generator = SalesDataGenerator()
        generator.generate_demo_data(clear_existing=False) # months=12)  # Un año de datos
    
    def test_training_time(self):
        """Test: Tiempo de entrenamiento razonable."""
        import time
        
        predictor = SimpleSalesPredictor()
        
        start_time = time.time()
        predictor.train()
        training_time = time.time() - start_time
        
        # Debería entrenar en menos de 10 segundos
        self.assertLess(training_time, 10)
    
    def test_prediction_time(self):
        """Test: Tiempo de predicción rápido."""
        import time
        
        predictor = SimpleSalesPredictor()
        predictor.train()
        
        start_time = time.time()
        predictor.predict(days=365)  # Un año de predicciones
        prediction_time = time.time() - start_time
        
        # Debería predecir en menos de 1 segundo
        self.assertLess(prediction_time, 1)
    
    def test_model_file_size(self):
        """Test: Tamaño de archivo del modelo razonable."""
        predictor = SimpleSalesPredictor()
        predictor.train()
        
        manager = ModelManager()
        version = manager.save_model(predictor)
        
        # Obtener tamaño del archivo
        model_path = manager.models_dir / f'sales_model_{version}.pkl'
        file_size_mb = model_path.stat().st_size / (1024 * 1024)
        
        # Debería ser menor a 1 MB
        self.assertLess(file_size_mb, 1.0)
