from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    verbose_name = 'Gaming Lounge API'

    def ready(self):
        import api.signals  # noqa: F401  (registers signal receivers)