from django.apps import AppConfig


class ObrasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "obras"

    def ready(self):
        # Sinais de limpeza do PDF de "Atividade de apoio" (ver signals.py) —
        # acréscimo à Fase 6, 28/09/2026.
        from . import signals  # noqa: F401
