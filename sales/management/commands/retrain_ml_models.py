"""
Comando de Django para reentrenar modelos ML.

Uso:
    python manage.py retrain_ml_models
    python manage.py retrain_ml_models --force
    python manage.py retrain_ml_models --check-only
"""

from django.core.management.base import BaseCommand
from sales.ml_auto_retrain import auto_retrain_if_needed, should_retrain_model, cleanup_old_models


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
            help='Solo verificar si es necesario reentrenar (no reentrena)',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Limpiar modelos antiguos después de reentrenar',
        )

    def handle(self, *args, **options):
        if options['check_only']:
            # Solo verificar
            self._check_only()
        else:
            # Reentrenar
            self._retrain(force=options['force'], cleanup=options['cleanup'])

    def _check_only(self):
        """Verifica si es necesario reentrenar sin hacerlo."""
        check = should_retrain_model()

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("  VERIFICACIÓN DE ESTADO DEL MODELO ML")
        self.stdout.write("=" * 80 + "\n")

        if check['should_retrain']:
            urgency_colors = {
                'critical': self.style.ERROR,
                'high': self.style.WARNING,
                'medium': self.style.WARNING,
                'low': self.style.NOTICE
            }
            color_fn = urgency_colors.get(check['urgency'], self.style.WARNING)

            self.stdout.write(color_fn(f"[!] SE RECOMIENDA REENTRENAR EL MODELO"))
            self.stdout.write(f"   Urgencia: {check['urgency'].upper()}\n")

            self.stdout.write("   Razones:")
            for reason in check['reasons']:
                self.stdout.write(f"   - {reason}")

            self.stdout.write(f"\n   Días desde último entrenamiento: {check['days_since_training']}")
            self.stdout.write(f"   Nuevas órdenes desde entrenamiento: {check['new_orders_since_training']}\n")

            self.stdout.write(self.style.NOTICE("\n[INFO] Para reentrenar, ejecuta:"))
            self.stdout.write("   python manage.py retrain_ml_models\n")

        else:
            self.stdout.write(self.style.SUCCESS("[OK] EL MODELO ESTA ACTUALIZADO\n"))
            self.stdout.write("   No es necesario reentrenar en este momento.\n")

        # Mostrar métricas
        self.stdout.write("[METRICAS] Del modelo actual:")
        metrics = check['metrics']
        self.stdout.write(f"   - Version: {metrics.get('model_version', 'N/A')}")
        self.stdout.write(f"   - Entrenado: {metrics.get('trained_at', 'N/A')}")
        self.stdout.write(f"   - R2 Score: {metrics.get('r2_score', 0):.4f}")
        self.stdout.write(f"   - Muestras de entrenamiento: {metrics.get('training_samples', 0)}")
        self.stdout.write(f"   - Ordenes totales: {metrics.get('current_orders', 0)}")
        self.stdout.write(f"   - Ordenes al entrenar: {metrics.get('orders_at_training', 0)}")
        self.stdout.write(f"   - Nuevas ordenes: {metrics.get('new_orders_since_training', 0)}\n")

        self.stdout.write("=" * 80 + "\n")

    def _retrain(self, force=False, cleanup=False):
        """Reentrena el modelo."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("  REENTRENAMIENTO DE MODELO ML")
        self.stdout.write("=" * 80 + "\n")

        if force:
            self.stdout.write(self.style.WARNING("⚡ Modo FORZADO: Reentrenando sin verificar condiciones\n"))

        # Ejecutar reentrenamiento
        result = auto_retrain_if_needed(force=force)

        if result['retrained']:
            self.stdout.write(self.style.SUCCESS("✅ MODELO REENTRENADO EXITOSAMENTE\n"))

            # Mostrar razones
            if 'reasons' in result:
                self.stdout.write("📋 Razones del reentrenamiento:")
                for reason in result['reasons']:
                    self.stdout.write(f"   • {reason}")
                self.stdout.write("")

            # Mostrar información del nuevo modelo
            model_info = result['model_info']
            metrics = result['metrics']

            self.stdout.write("📊 Información del nuevo modelo:")
            self.stdout.write(f"   • Versión: {model_info['version']}")
            self.stdout.write(f"   • Entrenado: {model_info['saved_at']}")
            self.stdout.write(f"   • R² Score: {metrics['r2_score']:.4f}")
            self.stdout.write(f"   • MAE: ${metrics['mae']:,.2f}")
            self.stdout.write(f"   • RMSE: ${metrics['rmse']:,.2f}")
            self.stdout.write(f"   • MAPE: {metrics['mape']:.2f}%")
            self.stdout.write(f"   • Días de entrenamiento: {metrics['training_samples']}")
            self.stdout.write(f"   • Total de ventas: ${metrics['total_sales']:,.2f}")
            self.stdout.write(f"   • Promedio diario: ${metrics['average_daily_sales']:,.2f}\n")

            # Cleanup opcional
            if cleanup:
                self.stdout.write("🗑️ Limpiando modelos antiguos...")
                cleanup_result = cleanup_old_models(keep_last_n=5)
                self.stdout.write(f"   • Modelos eliminados: {cleanup_result['deleted']}")
                self.stdout.write(f"   • Modelos mantenidos: {cleanup_result['kept']}\n")

            self.stdout.write(self.style.SUCCESS("🎉 PROCESO COMPLETADO\n"))

            # Sugerencias
            self.stdout.write("💡 Próximos pasos:")
            self.stdout.write("   1. Las predicciones ya usan el nuevo modelo automáticamente")
            self.stdout.write("   2. Limpia el caché si es necesario:")
            self.stdout.write("      POST /api/orders/predictions/clear-cache/")
            self.stdout.write("   3. Verifica las nuevas predicciones en el dashboard\n")

        elif result['error']:
            self.stdout.write(self.style.ERROR(f"❌ ERROR DURANTE EL REENTRENAMIENTO\n"))
            self.stdout.write(f"   {result['error']}\n")
            self.stdout.write(self.style.WARNING("💡 Posibles soluciones:"))
            self.stdout.write("   • Verifica que haya al menos 30 días de datos de ventas")
            self.stdout.write("   • Revisa los logs para más detalles")
            self.stdout.write("   • Contacta al equipo de desarrollo si el error persiste\n")

        else:
            self.stdout.write(self.style.NOTICE(f"⚠️ NO SE REENTRENÓ EL MODELO\n"))
            self.stdout.write(f"   Razón: {result['reason']}\n")

            if 'check_info' in result:
                check = result['check_info']
                self.stdout.write("📊 Estado actual:")
                self.stdout.write(f"   • Días desde entrenamiento: {check.get('days_since_training', 0)}")
                self.stdout.write(f"   • Nuevas órdenes: {check.get('new_orders_since_training', 0)}")
                self.stdout.write(f"   • R² Score: {check['metrics'].get('r2_score', 0):.4f}\n")

            self.stdout.write(self.style.NOTICE("💡 Para forzar reentrenamiento:"))
            self.stdout.write("   python manage.py retrain_ml_models --force\n")

        self.stdout.write("=" * 80 + "\n")
