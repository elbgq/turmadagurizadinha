"""
Garante que todo User tenha um Perfil — inclusive os criados por
`createsuperuser` ou direto no Django Admin, que antes ficavam sem Perfil
e não conseguiam gravar ResultadoQuiz (FK obrigatória para Perfil).
Registrado em ContasConfig.ready() (ver apps.py).

Usuários que já existiam sem Perfil são corrigidos pela migração
0004_criar_perfis_faltantes.
"""

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Perfil


@receiver(post_save, sender=User)
def criar_perfil_do_usuario(sender, instance, created, raw=False, **kwargs):
    """Cria o Perfil (tipo "outro") ao criar um User novo."""
    if created and not raw:
        Perfil.objects.get_or_create(user=instance)
