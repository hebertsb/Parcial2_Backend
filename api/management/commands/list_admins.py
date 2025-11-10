from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import models

class Command(BaseCommand):
    help = "Lista usuarios administradores: superusers, staff o con profile.role=ADMIN"

    def handle(self, *args, **options):
        # Como el rol ADMIN lo tenemos en Profile, combinamos superuser/staff con role ADMIN
        from api.models import Profile
        by_role_ids = Profile.objects.filter(role='ADMIN').values_list('user_id', flat=True)
        admins = (
            User.objects.filter(is_active=True)
            .filter(models.Q(is_superuser=True) | models.Q(is_staff=True) | models.Q(id__in=by_role_ids))
            .order_by('id')
        )

        if not admins.exists():
            self.stdout.write(self.style.WARNING('No hay usuarios administradores.'))
            return

        self.stdout.write(self.style.SUCCESS('Admins encontrados:'))
        for u in admins:
            role = getattr(getattr(u, 'profile', None), 'role', 'N/A')
            self.stdout.write(f"- id={u.id} username={u.username} email={u.email} is_staff={u.is_staff} is_superuser={u.is_superuser} role={role}")
        
        self.stdout.write(self.style.NOTICE('Por seguridad, las contraseñas NO pueden mostrarse. Si necesitas actualizar una, usa el comando set_admin_password.'))
