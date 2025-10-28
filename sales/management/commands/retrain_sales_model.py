"""
Management command para re-entrenar el modelo de predicción de ventas.
Uso: python manage.py retrain_sales_model
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from sales.ml_predictor_simple import SimpleSalesPredictor
from sales.ml_model_manager import model_manager


class Command(BaseCommand):
    help = 'Re-entrena el modelo de predicción de ventas con los datos más recientes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model-version',
            type=str,
            help='Versión personalizada para el modelo (opcional)',
        )
        parser.add_argument(
            '--notes',
            type=str,
            default='Re-entrenamiento automático',
            help='Notas sobre este entrenamiento',
        )
        parser.add_argument(
            '--min-days',
            type=int,
            default=30,
            help='Número mínimo de días de datos requeridos (default: 30)',
        )

    def handle(self, *args, **options):
        version = options.get('model_version')
        notes = options.get('notes')
        min_days = options.get('min_days')
        
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING('🤖 Iniciando re-entrenamiento del modelo de predicción de ventas'))
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write('')
        
        try:
            # Crear predictor
            predictor = SimpleSalesPredictor()
            
            # Entrenar
            self.stdout.write('📊 Entrenando modelo...')
            metrics = predictor.train()
            
            # Verificar que hay suficientes datos
            if metrics['training_samples'] < min_days:
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ ERROR: Solo hay {metrics["training_samples"]} días de datos. '
                        f'Se requieren al menos {min_days} días.'
                    )
                )
                return
            
            # Mostrar métricas
            self.stdout.write(self.style.SUCCESS('✓ Modelo entrenado exitosamente'))
            self.stdout.write('')
            self.stdout.write('📈 Métricas de entrenamiento:')
            self.stdout.write(f'  • Muestras: {metrics["training_samples"]} días')
            self.stdout.write(f'  • Período: {metrics["start_date"]} a {metrics["end_date"]}')
            self.stdout.write(f'  • Ventas totales: ${metrics["total_sales"]:,.2f}')
            self.stdout.write(f'  • Promedio diario: ${metrics["average_daily_sales"]:,.2f}')
            self.stdout.write(f'  • Desviación estándar: ${metrics["std_daily_sales"]:,.2f}')
            self.stdout.write('')
            
            # Guardar modelo
            self.stdout.write('💾 Guardando modelo...')
            model_info = model_manager.save_model(
                predictor,
                version=version,
                notes=notes
            )
            
            self.stdout.write(self.style.SUCCESS('✓ Modelo guardado exitosamente'))
            self.stdout.write(f'  • Versión: {model_info["version"]}')
            self.stdout.write(f'  • Tamaño: {model_info["file_size_mb"]} MB')
            self.stdout.write(f'  • Guardado en: {model_info["saved_at"]}')
            self.stdout.write('')
            
            # Generar predicciones de prueba
            self.stdout.write('🔮 Generando predicciones de prueba (30 días)...')
            predictions = predictor.predict(days=30)
            
            self.stdout.write(self.style.SUCCESS('✓ Predicciones generadas'))
            self.stdout.write(f'  • Total predicho: ${predictions["summary"]["total_predicted_sales"]:,.2f}')
            self.stdout.write(f'  • Promedio diario: ${predictions["summary"]["average_daily_sales"]:,.2f}')
            self.stdout.write(f'  • Crecimiento vs histórico: {predictions["summary"]["growth_rate_percent"]:+.2f}%')
            self.stdout.write('')
            
            # Performance
            self.stdout.write('📊 Evaluando rendimiento del modelo...')
            performance = predictor.get_historical_performance()
            
            self.stdout.write(self.style.SUCCESS('✓ Métricas de rendimiento'))
            self.stdout.write(f'  • MAE (Error Absoluto Medio): ${performance["mae"]:,.2f}')
            self.stdout.write(f'  • RMSE (Raíz del Error Cuadrático Medio): ${performance["rmse"]:,.2f}')
            self.stdout.write(f'  • MAPE (Error Porcentual Absoluto Medio): {performance["mape"]:.2f}%')
            self.stdout.write('')
            
            self.stdout.write(self.style.SUCCESS('=' * 70))
            self.stdout.write(self.style.SUCCESS('✅ Re-entrenamiento completado exitosamente'))
            self.stdout.write(self.style.SUCCESS('=' * 70))
            
        except ValueError as e:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('❌ ERROR: ' + str(e)))
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('💡 Sugerencia:'))
            self.stdout.write('   Genera datos de demostración con:')
            self.stdout.write('   python manage.py generate_demo_sales')
            self.stdout.write('')
            
        except Exception as e:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('❌ ERROR INESPERADO: ' + str(e)))
            self.stdout.write('')
            raise
