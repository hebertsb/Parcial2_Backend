"""
Management command para generar datos de ventas de demostración.
Uso: python manage.py generate_demo_sales
"""
from django.core.management.base import BaseCommand

from sales.ml_data_generator import generate_sales_data


class Command(BaseCommand):
    help = 'Genera datos sintéticos de ventas para demostración del sistema ML'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Elimina las órdenes existentes antes de generar nuevas',
        )

    def handle(self, *args, **options):
        clear_existing = options.get('clear', False)
        
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING('🎲 Generador de Datos de Ventas Demo'))
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write('')
        
        if clear_existing:
            self.stdout.write(self.style.WARNING('⚠️  Modo: Eliminar datos existentes'))
            self.stdout.write('')
            response = input('¿Estás seguro? Esto eliminará TODAS las órdenes existentes. (yes/no): ')
            if response.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Operación cancelada'))
                return
            self.stdout.write('')
        
        try:
            self.stdout.write('🏗️  Generando datos de ventas...')
            self.stdout.write('')
            
            stats = generate_sales_data(clear_existing=clear_existing)
            
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✅ Datos generados exitosamente!'))
            self.stdout.write('')
            self.stdout.write('📊 Estadísticas:')
            self.stdout.write(f'  • Órdenes generadas: {stats["total_orders"]:,}')
            self.stdout.write(f'  • Ingresos totales: ${stats["total_revenue"]:,.2f}')
            self.stdout.write(f'  • Período: {stats["start_date"]} a {stats["end_date"]}')
            self.stdout.write(f'  • Productos usados: {stats["products_count"]}')
            self.stdout.write(f'  • Clientes creados: {stats["customers_count"]}')
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 70))
            self.stdout.write(self.style.SUCCESS('✅ Listo! Ahora puedes entrenar el modelo con:'))
            self.stdout.write(self.style.SUCCESS('   python manage.py retrain_sales_model'))
            self.stdout.write(self.style.SUCCESS('=' * 70))
            
        except Exception as e:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('❌ ERROR: ' + str(e)))
            self.stdout.write('')
            raise
