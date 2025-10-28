# api/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    # Ajustamos los roles a los que necesitas
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        CLIENT = 'CLIENT', 'Cliente' # Cambiamos EDITOR y VIEWER por CLIENT

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # El rol por defecto para nuevos usuarios será 'CLIENT'
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.CLIENT)

    def __str__(self):
        return f'{self.user.username} - {self.role}'

# Esta función crea un Perfil automáticamente cada vez que se crea un Usuario
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Si es un superusuario, le asignamos el rol de ADMIN
        role = Profile.Role.ADMIN if instance.is_superuser else Profile.Role.CLIENT
        Profile.objects.create(user=instance, role=role)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Nos aseguramos de que el perfil exista antes de intentar guardarlo
    if hasattr(instance, 'profile'):
        instance.profile.save()