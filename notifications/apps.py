from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    verbose_name = 'Notificaciones Push'

    def ready(self):
        # Import signals when app is ready
        import notifications.signals
