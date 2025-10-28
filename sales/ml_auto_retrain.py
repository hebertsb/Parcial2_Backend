"""
Sistema de Reentrenamiento Automático de Modelos ML.

Estrategias:
1. Reentrenamiento programado (cada X días)
2. Reentrenamiento por umbral (cada X ventas nuevas)
3. Verificación de calidad del modelo

Uso:
    # Opción 1: Comando manual
    python manage.py retrain_ml_models

    # Opción 2: Cronjob/Task programado
    # En settings.py agregar a CELERY_BEAT_SCHEDULE

    # Opción 3: Llamar desde código
    from sales.ml_auto_retrain import auto_retrain_if_needed
    auto_retrain_if_needed()
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count

from sales.models import Order
from sales.ml_predictor_simple import SimpleSalesPredictor
from sales.ml_model_manager import model_manager


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

class RetrainConfig:
    """Configuración del sistema de reentrenamiento."""

    # Reentrenamiento programado
    AUTO_RETRAIN_ENABLED = True
    RETRAIN_INTERVAL_DAYS = 7  # Reentrenar cada 7 días

    # Reentrenamiento por umbral
    RETRAIN_ON_NEW_ORDERS_THRESHOLD = 100  # Reentrenar cada 100 órdenes nuevas

    # Calidad del modelo
    MIN_R2_SCORE = 0.15  # Si R² < 0.15, forzar reentrenamiento
    MIN_TRAINING_DAYS = 30  # Mínimo de días de datos

    # Hora preferida para reentrenamiento (si se usa scheduler)
    PREFERRED_RETRAIN_HOUR = 3  # 3 AM

    # Cache keys
    CACHE_LAST_RETRAIN_CHECK = 'ml_last_retrain_check'
    CACHE_ORDERS_COUNT_AT_TRAINING = 'ml_orders_count_at_training'


# ============================================================================
# VERIFICACIÓN DE NECESIDAD DE REENTRENAMIENTO
# ============================================================================

def should_retrain_model() -> Dict[str, Any]:
    """
    Verifica si el modelo necesita ser reentrenado.

    Returns:
        Dict con:
        - should_retrain (bool): Si debe reentrenar
        - reasons (list): Razones por las que debe reentrenar
        - metrics (dict): Métricas actuales
    """
    reasons = []
    should_retrain = False

    # Obtener información del modelo actual
    current_model = model_manager.get_current_model_info()

    if current_model is None:
        return {
            'should_retrain': True,
            'reasons': ['No hay modelo entrenado'],
            'metrics': {},
            'urgency': 'critical'
        }

    metrics = {
        'model_version': current_model['version'],
        'trained_at': current_model['saved_at'],
        'r2_score': current_model['metrics'].get('r2_score', 0),
        'training_samples': current_model['metrics'].get('training_samples', 0)
    }

    # 1. Verificar tiempo desde último entrenamiento
    saved_at_str = current_model['saved_at']
    if isinstance(saved_at_str, str):
        # Manejar diferentes formatos de fecha
        if saved_at_str.endswith('Z'):
            trained_at = datetime.fromisoformat(saved_at_str.replace('Z', '+00:00'))
        elif '+' in saved_at_str or saved_at_str.count('-') > 2:
            trained_at = datetime.fromisoformat(saved_at_str)
        else:
            # Sin zona horaria, asumir UTC
            trained_at = timezone.make_aware(datetime.fromisoformat(saved_at_str))
    else:
        # Ya es un objeto datetime
        trained_at = saved_at_str if timezone.is_aware(saved_at_str) else timezone.make_aware(saved_at_str)

    days_since_training = (timezone.now() - trained_at).days

    if days_since_training >= RetrainConfig.RETRAIN_INTERVAL_DAYS:
        reasons.append(f'Han pasado {days_since_training} días desde el último entrenamiento')
        should_retrain = True

    # 2. Verificar nuevas órdenes desde entrenamiento
    orders_at_training = cache.get(RetrainConfig.CACHE_ORDERS_COUNT_AT_TRAINING, 0)
    current_orders_count = Order.objects.filter(status='COMPLETED').count()
    new_orders_count = current_orders_count - orders_at_training

    metrics['orders_at_training'] = orders_at_training
    metrics['current_orders'] = current_orders_count
    metrics['new_orders_since_training'] = new_orders_count

    if new_orders_count >= RetrainConfig.RETRAIN_ON_NEW_ORDERS_THRESHOLD:
        reasons.append(f'{new_orders_count} nuevas órdenes desde último entrenamiento')
        should_retrain = True

    # 3. Verificar calidad del modelo
    r2_score = current_model['metrics'].get('r2_score', 0)
    if r2_score < RetrainConfig.MIN_R2_SCORE:
        reasons.append(f'R² Score bajo ({r2_score:.4f} < {RetrainConfig.MIN_R2_SCORE})')
        should_retrain = True

    # 4. Verificar si hay suficientes datos nuevos
    recent_orders = Order.objects.filter(
        status='COMPLETED',
        created_at__gte=trained_at
    ).count()

    metrics['recent_orders'] = recent_orders

    # Determinar urgencia
    urgency = 'low'
    if not should_retrain:
        urgency = 'none'
    elif r2_score < RetrainConfig.MIN_R2_SCORE:
        urgency = 'high'
    elif new_orders_count >= RetrainConfig.RETRAIN_ON_NEW_ORDERS_THRESHOLD * 2:
        urgency = 'high'
    elif days_since_training >= RetrainConfig.RETRAIN_INTERVAL_DAYS * 2:
        urgency = 'medium'

    return {
        'should_retrain': should_retrain,
        'reasons': reasons,
        'metrics': metrics,
        'urgency': urgency,
        'days_since_training': days_since_training,
        'new_orders_since_training': new_orders_count
    }


# ============================================================================
# REENTRENAMIENTO AUTOMÁTICO
# ============================================================================

def auto_retrain_if_needed(force: bool = False) -> Dict[str, Any]:
    """
    Reentrena el modelo automáticamente si es necesario.

    Args:
        force: Forzar reentrenamiento sin verificar condiciones

    Returns:
        Dict con resultado del reentrenamiento
    """
    result = {
        'retrained': False,
        'reason': None,
        'model_info': None,
        'metrics': None,
        'error': None
    }

    if not force:
        # Verificar si debe reentrenar
        check_result = should_retrain_model()

        if not check_result['should_retrain']:
            result['reason'] = 'No es necesario reentrenar'
            result['check_info'] = check_result
            return result

        result['reasons'] = check_result['reasons']
        result['urgency'] = check_result['urgency']
    else:
        result['reasons'] = ['Reentrenamiento forzado manualmente']
        result['urgency'] = 'manual'

    # Realizar reentrenamiento
    try:
        print("🔄 Iniciando reentrenamiento automático del modelo ML...")
        print(f"   Razones: {', '.join(result['reasons'])}")

        # Crear y entrenar nuevo modelo
        predictor = SimpleSalesPredictor()
        metrics = predictor.train()

        # Guardar modelo
        current_orders = Order.objects.filter(status='COMPLETED').count()
        model_info = model_manager.save_model(
            predictor,
            notes=f"Reentrenamiento automático. Razones: {', '.join(result['reasons'])}",
            version=None  # Auto-genera versión con timestamp
        )

        # Guardar contador de órdenes
        cache.set(RetrainConfig.CACHE_ORDERS_COUNT_AT_TRAINING, current_orders, None)

        # Actualizar resultado
        result['retrained'] = True
        result['model_info'] = model_info
        result['metrics'] = metrics
        result['orders_at_training'] = current_orders

        print("✅ Reentrenamiento completado exitosamente")
        print(f"   Nueva versión: {model_info['version']}")
        print(f"   R² Score: {metrics['r2_score']:.4f}")
        print(f"   Órdenes usadas: {current_orders}")

    except Exception as e:
        result['error'] = str(e)
        print(f"❌ Error durante reentrenamiento: {str(e)}")

    return result


# ============================================================================
# TAREAS PROGRAMADAS (Para usar con Celery/APScheduler)
# ============================================================================

def scheduled_retrain_task():
    """
    Tarea para ejecutar en un scheduler (Celery, APScheduler, cron).

    Ejemplo con Celery:
        from celery import shared_task

        @shared_task
        def retrain_ml_model_task():
            from sales.ml_auto_retrain import scheduled_retrain_task
            return scheduled_retrain_task()
    """
    # Solo reentrenar si está habilitado
    if not RetrainConfig.AUTO_RETRAIN_ENABLED:
        return {'status': 'disabled', 'message': 'Auto-retrain is disabled'}

    # Verificar si es hora apropiada (si se ejecuta frecuentemente)
    current_hour = timezone.now().hour
    if current_hour != RetrainConfig.PREFERRED_RETRAIN_HOUR:
        return {
            'status': 'skipped',
            'message': f'Not the preferred hour (current: {current_hour}, preferred: {RetrainConfig.PREFERRED_RETRAIN_HOUR})'
        }

    # Ejecutar reentrenamiento si es necesario
    result = auto_retrain_if_needed()

    return result


# ============================================================================
# COMANDO DE GESTIÓN (Django Management Command)
# ============================================================================

def create_management_command():
    """
    Crea un comando de Django para reentrenar manualmente.

    Uso:
        python manage.py retrain_ml_models
        python manage.py retrain_ml_models --force
        python manage.py retrain_ml_models --check-only
    """
    # Este código debe ir en: sales/management/commands/retrain_ml_models.py
    command_code = '''
from django.core.management.base import BaseCommand
from sales.ml_auto_retrain import auto_retrain_if_needed, should_retrain_model


class Command(BaseCommand):
    help = 'Reentrena los modelos ML de predicción de ventas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar reentrenamiento sin verificar condiciones',
        )
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Solo verificar si es necesario reentrenar',
        )

    def handle(self, *args, **options):
        if options['check_only']:
            # Solo verificar
            check = should_retrain_model()
            self.stdout.write("\\n=== VERIFICACIÓN DE REENTRENAMIENTO ===\\n")

            if check['should_retrain']:
                self.stdout.write(self.style.WARNING(f"⚠️ Se recomienda reentrenar el modelo"))
                self.stdout.write(f"   Urgencia: {check['urgency']}\\n")
                self.stdout.write("   Razones:")
                for reason in check['reasons']:
                    self.stdout.write(f"   - {reason}")
            else:
                self.stdout.write(self.style.SUCCESS("✅ El modelo está actualizado"))

            self.stdout.write("\\n   Métricas actuales:")
            for key, value in check['metrics'].items():
                self.stdout.write(f"   - {key}: {value}")

        else:
            # Reentrenar
            self.stdout.write("\\n🔄 Iniciando reentrenamiento...\\n")
            result = auto_retrain_if_needed(force=options['force'])

            if result['retrained']:
                self.stdout.write(self.style.SUCCESS("\\n✅ Modelo reentrenado exitosamente\\n"))
                self.stdout.write(f"   Versión: {result['model_info']['version']}")
                self.stdout.write(f"   R² Score: {result['metrics']['r2_score']:.4f}")
                self.stdout.write(f"   MAE: ${result['metrics']['mae']:,.2f}")
                self.stdout.write(f"   Órdenes: {result['orders_at_training']}\\n")
            elif result['error']:
                self.stdout.write(self.style.ERROR(f"\\n❌ Error: {result['error']}\\n"))
            else:
                self.stdout.write(self.style.WARNING(f"\\n⚠️ No se reentrenó: {result['reason']}\\n"))
'''
    return command_code


# ============================================================================
# ENDPOINT PARA MONITOREO
# ============================================================================

def get_retrain_status() -> Dict[str, Any]:
    """
    Obtiene el estado del sistema de reentrenamiento.

    Returns:
        Dict con información de estado
    """
    check = should_retrain_model()
    current_model = model_manager.get_current_model_info()

    return {
        'auto_retrain_enabled': RetrainConfig.AUTO_RETRAIN_ENABLED,
        'retrain_interval_days': RetrainConfig.RETRAIN_INTERVAL_DAYS,
        'retrain_threshold_orders': RetrainConfig.RETRAIN_ON_NEW_ORDERS_THRESHOLD,
        'current_model': {
            'version': current_model['version'] if current_model else None,
            'trained_at': current_model['saved_at'] if current_model else None,
            'r2_score': current_model['metrics'].get('r2_score', 0) if current_model else 0
        },
        'should_retrain': check['should_retrain'],
        'reasons': check['reasons'],
        'urgency': check['urgency'],
        'metrics': check['metrics']
    }


# ============================================================================
# UTILIDADES
# ============================================================================

def notify_retrain_needed(urgency: str, reasons: list):
    """
    Notifica que se necesita reentrenamiento (opcional).
    Implementar según tu sistema de notificaciones.

    Args:
        urgency: Nivel de urgencia (critical, high, medium, low)
        reasons: Lista de razones
    """
    # TODO: Implementar notificaciones
    # Ejemplos:
    # - Enviar email al admin
    # - Crear notificación en el sistema
    # - Log en archivo especial
    # - Webhook a Slack/Discord

    print(f"📢 NOTIFICACIÓN: Se necesita reentrenamiento ({urgency})")
    print(f"   Razones: {', '.join(reasons)}")


def cleanup_old_models(keep_last_n: int = 5):
    """
    Limpia modelos antiguos, manteniendo solo los últimos N.

    Args:
        keep_last_n: Número de modelos a mantener
    """
    models = model_manager.list_models()

    if len(models) <= keep_last_n:
        return {'deleted': 0, 'kept': len(models)}

    # Ordenar por fecha (más reciente primero)
    models_sorted = sorted(models, key=lambda x: x['saved_at'], reverse=True)

    # Eliminar modelos antiguos
    deleted_count = 0
    for model in models_sorted[keep_last_n:]:
        try:
            model_manager.delete_model(model['version'])
            deleted_count += 1
            print(f"🗑️ Modelo antiguo eliminado: {model['version']}")
        except Exception as e:
            print(f"❌ Error eliminando modelo {model['version']}: {str(e)}")

    return {'deleted': deleted_count, 'kept': keep_last_n}
