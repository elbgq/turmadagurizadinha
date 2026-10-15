from django.apps import AppConfig


class ContasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "contas"

    def ready(self):
        # Sinal que cria o Perfil de todo User novo (ver signals.py) —
        # correção da sessão de higiene, 14/10/2026.
        from . import signals  # noqa: F401
