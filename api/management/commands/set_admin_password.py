from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Actualiza la contraseña de un usuario admin (por username o email). No muestra contraseñas antiguas."

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Username del admin')
        parser.add_argument('--email', type=str, help='Email del admin')
        parser.add_argument('--password', type=str, required=True, help='Nueva contraseña')

    def handle(self, *args, **options):
        username = options.get('username')
        email = options.get('email')
        password = options['password']

        if not username and not email:
            raise CommandError('Debes especificar --username o --email')

        try:
            if username:
                user = User.objects.get(username=username)
            else:
                user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError('Usuario no encontrado')

        # Verificamos que sea admin (superuser/staff o rol ADMIN)
        role = getattr(getattr(user, 'profile', None), 'role', None)
        is_admin = user.is_superuser or user.is_staff or role == 'ADMIN'
        if not is_admin:
            raise CommandError('El usuario no es administrador')

        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f'Contraseña actualizada para {user.username}.'))
        self.stdout.write('IMPORTANTE: La contraseña no se puede recuperar en texto plano, solo reasignar.')
