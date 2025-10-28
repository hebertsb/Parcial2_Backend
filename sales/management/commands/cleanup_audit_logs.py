# sales/management/commands/cleanup_audit_logs.py
"""
Comando de Django para limpiar logs de auditoría antiguos.

Uso:
    python manage.py cleanup_audit_logs --days=90
    python manage.py cleanup_audit_logs --days=180 --confirm
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from sales.models_audit import AuditLog


class Command(BaseCommand):
    help = 'Elimina registros de auditoría más antiguos que N días'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Número de días a conservar (default: 90)'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirmar la eliminación sin preguntar'
        )

    def handle(self, *args, **options):
        days = options['days']
        confirm = options['confirm']

        if days < 30:
            self.stdout.write(
                self.style.ERROR('Error: No se pueden eliminar logs de menos de 30 días')
            )
            return

        cutoff_date = timezone.now() - timedelta(days=days)

        # Contar cuántos registros se eliminarán
        count_to_delete = AuditLog.objects.filter(timestamp__lt=cutoff_date).count()

        if count_to_delete == 0:
            self.stdout.write(
                self.style.WARNING(f'No hay registros más antiguos que {days} días')
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f'\nSe eliminarán {count_to_delete} registros más antiguos que {days} días'
            )
        )
        self.stdout.write(
            self.style.WARNING(f'Fecha de corte: {cutoff_date.strftime("%Y-%m-%d %H:%M:%S")}')
        )

        # Confirmar con el usuario
        if not confirm:
            confirm_input = input('\n¿Desea continuar? (yes/no): ')
            if confirm_input.lower() not in ['yes', 'y', 'si', 's']:
                self.stdout.write(self.style.WARNING('Operación cancelada'))
                return

        # Eliminar registros
        self.stdout.write('Eliminando registros...')
        deleted_count = AuditLog.objects.filter(timestamp__lt=cutoff_date).delete()[0]

        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Se eliminaron {deleted_count} registros exitosamente')
        )
