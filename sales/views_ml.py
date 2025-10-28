"""
Views para el sistema de predicción de ventas con Machine Learning.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from sales.ml_predictor_simple import SimpleSalesPredictor
from sales.ml_model_manager import model_manager, get_predictor
from sales.ml_data_generator import generate_sales_data
from sales.ml_auto_retrain import should_retrain_model, auto_retrain_if_needed, get_retrain_status


@api_view(['POST'])
@permission_classes([IsAdminUser])
def generate_demo_sales_data(request):
    """
    Genera datos sintéticos de ventas para demostración.
    
    POST /api/orders/ml/generate-demo-data/
    
    Body (opcional):
    {
        "clear_existing": true  // Elimina datos existentes antes de generar
    }
    
    Returns:
        Estadísticas de generación de datos
    """
    try:
        clear_existing = request.data.get('clear_existing', False)
        
        stats = generate_sales_data(clear_existing=clear_existing)
        
        return Response({
            'success': True,
            'message': 'Datos de demostración generados exitosamente',
            'data': stats
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def train_model(request):
    """
    Entrena un nuevo modelo de predicción de ventas.
    
    POST /api/orders/ml/train/
    
    Body (opcional):
    {
        "notes": "Descripción del entrenamiento",
        "version": "v1.0"  // Opcional
    }
    
    Returns:
        Información del modelo entrenado
    """
    try:
        notes = request.data.get('notes', 'Entrenamiento manual desde API')
        version = request.data.get('version', None)
        
        # Entrenar modelo
        predictor = SimpleSalesPredictor()
        metrics = predictor.train()
        
        # Guardar modelo
        model_info = model_manager.save_model(
            predictor, 
            version=version,
            notes=notes
        )
        
        return Response({
            'success': True,
            'message': 'Modelo entrenado y guardado exitosamente',
            'model_info': model_info,
            'metrics': metrics
        }, status=status.HTTP_201_CREATED)
        
    except ValueError as e:
        return Response({
            'success': False,
            'error': str(e),
            'hint': 'Asegúrate de tener al menos 30 días de datos de ventas. '
                   'Usa /api/orders/ml/generate-demo-data/ para generar datos de prueba.'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_predictions(request):
    """
    Obtiene predicciones de ventas futuras.
    
    GET /api/orders/ml/predictions/
    
    Query params:
    - days: Número de días a predecir (default: 30, max: 365)
    
    Returns:
        Predicciones de ventas con intervalos de confianza
    """
    try:
        # Obtener parámetros
        days = int(request.query_params.get('days', 30))
        
        # Validar
        if days < 1 or days > 365:
            return Response({
                'success': False,
                'error': 'El parámetro "days" debe estar entre 1 y 365'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener predictor
        predictor = get_predictor()
        
        # Generar predicciones
        predictions = predictor.predict(days=days)
        
        return Response({
            'success': True,
            'data': predictions
        })
        
    except ValueError as e:
        return Response({
            'success': False,
            'error': str(e),
            'hint': 'Entrena un modelo primero usando /api/orders/ml/train/'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_forecast_components(request):
    """
    Obtiene información del modelo de predicción.
    
    GET /api/orders/ml/forecast-components/
    
    Returns:
        Información del modelo y características
    """
    try:
        predictor = get_predictor()
        
        components = {
            'model_type': 'Linear Regression with Polynomial Features',
            'features': [
                'Días desde inicio',
                'Día de la semana',
                'Fin de semana (sí/no)',
                'Estacionalidad mensual (seno/coseno)',
                'Estacionalidad semanal (seno/coseno)'
            ],
            'metrics': predictor.metrics,
            'training_period': {
                'start': predictor.metrics.get('start_date'),
                'end': predictor.metrics.get('end_date'),
                'days': predictor.metrics.get('training_samples')
            }
        }
        
        return Response({
            'success': True,
            'data': components
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_model_performance(request):
    """
    Obtiene métricas de rendimiento del modelo actual.
    
    GET /api/orders/ml/performance/
    
    Returns:
        Métricas de error del modelo
    """
    try:
        predictor = get_predictor()
        performance = predictor.get_historical_performance()
        
        return Response({
            'success': True,
            'data': performance
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_models(request):
    """
    Lista todos los modelos guardados.
    
    GET /api/orders/ml/models/
    
    Returns:
        Lista de modelos con su información
    """
    try:
        models = model_manager.list_models()
        current_model = model_manager.get_current_model_info()
        
        return Response({
            'success': True,
            'data': {
                'models': models,
                'current_model': current_model
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def set_current_model(request):
    """
    Establece qué modelo usar como actual.
    
    POST /api/orders/ml/models/set-current/
    
    Body:
    {
        "version": "20241020_153045"
    }
    
    Returns:
        Información del modelo establecido
    """
    try:
        version = request.data.get('version')
        
        if not version:
            return Response({
                'success': False,
                'error': 'Se requiere el parámetro "version"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        model_info = model_manager.set_current_model(version)
        
        return Response({
            'success': True,
            'message': f'Modelo {version} establecido como actual',
            'data': model_info
        })
        
    except ValueError as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_model(request, version):
    """
    Elimina un modelo guardado.
    
    DELETE /api/orders/ml/models/{version}/
    
    Returns:
        Confirmación de eliminación
    """
    try:
        model_manager.delete_model(version)
        
        return Response({
            'success': True,
            'message': f'Modelo {version} eliminado exitosamente'
        })
        
    except ValueError as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def check_retrain_status(request):
    """
    Verifica si el modelo necesita ser reentrenado.

    GET /api/orders/ml/retrain/status/

    Returns:
        Estado del sistema de reentrenamiento automático
    """
    try:
        status = get_retrain_status()

        return Response({
            'success': True,
            'data': status
        })

    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def auto_retrain(request):
    """
    Reentrena el modelo automáticamente si es necesario.

    POST /api/orders/ml/retrain/auto/

    Body (opcional):
    {
        "force": false  // Forzar reentrenamiento
    }

    Returns:
        Resultado del reentrenamiento
    """
    try:
        force = request.data.get('force', False)

        result = auto_retrain_if_needed(force=force)

        if result['retrained']:
            return Response({
                'success': True,
                'message': 'Modelo reentrenado exitosamente',
                'data': result
            }, status=status.HTTP_201_CREATED)
        elif result['error']:
            return Response({
                'success': False,
                'error': result['error']
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({
                'success': True,
                'message': 'No fue necesario reentrenar',
                'data': result
            })

    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def ml_dashboard(request):
    """
    Dashboard completo del sistema ML.
    
    GET /api/orders/ml/dashboard/
    
    Returns:
        Resumen completo: modelo actual, predicciones, performance
    """
    try:
        # Obtener modelo actual
        current_model = model_manager.get_current_model_info()
        
        if current_model is None:
            return Response({
                'success': False,
                'error': 'No hay modelo entrenado',
                'hint': 'Entrena un modelo usando /api/orders/ml/train/'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Obtener predictor
        predictor = get_predictor()
        
        # Generar predicciones a 30 días
        predictions = predictor.predict(days=30)
        
        # Obtener performance
        performance = predictor.get_historical_performance()
        
        # Resumen
        dashboard = {
            'current_model': current_model,
            'predictions_30_days': {
                'total_predicted': predictions['summary']['total_predicted_sales'],
                'average_daily': predictions['summary']['average_daily_sales'],
                'growth_rate': predictions['summary']['growth_rate_percent']
            },
            'performance': performance,
            'last_updated': current_model['saved_at']
        }
        
        return Response({
            'success': True,
            'data': dashboard
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
