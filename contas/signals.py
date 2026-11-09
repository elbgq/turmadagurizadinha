"""
Garante que todo User tenha um Perfil — inclusive os criados por
`createsuperuser` ou direto no Django Admin, que antes ficavam sem Perfil
e não conseguiam gravar ResultadoQuiz (FK obrigatória para Perfil).
Registrado em ContasConfig.ready() (ver apps.py).

Usuários que já existiam sem Perfil são corrigidos pela migração
0004_criar_perfis_faltantes.

Desde 09/11/2026 (multiescola), salvar o Perfil também põe a conta no
grupo do papel (Admin da escola, Professor ou Aluno) — ver contas/papeis.py.
"""

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Perfil
from .papeis import sincronizar_grupo_do_papel


@receiver(post_save, sender=User)
def criar_perfil_do_usuario(sender, instance, created, raw=False, **kwargs):
    """Cria o Perfil (tipo "outro") ao criar um User novo."""
    if created and not raw:
        Perfil.objects.get_or_create(user=instance)


@receiver(post_save, sender=Perfil)
def grupo_acompanha_o_tipo(sender, instance, raw=False, **kwargs):
    """O grupo de papel segue o tipo do Perfil (a fonte confiável do papel)."""
    if not raw:
        sincronizar_grupo_do_papel(instance.user, instance.tipo)
