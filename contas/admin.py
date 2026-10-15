from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Perfil


class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name_plural = "Perfil"


class UsuarioAdmin(UserAdmin):
    """
    Reaproveita o UserAdmin padrão do Django (gerencia login, senha e
    permissões) só acrescentando o Perfil (tipo: professor/aluno/outro)
    como inline — evita duplicar tela de cadastro de usuário no Admin.
    """

    inlines = (PerfilInline,)

    def get_inline_instances(self, request, obj=None):
        # Na tela "Adicionar usuário" o Perfil ainda não aparece: ele é
        # criado pelo sinal de contas/signals.py ao salvar, e o inline aqui
        # tentaria criar um segundo. Depois de salvar, o Admin abre a tela
        # de edição, onde o tipo do Perfil pode ser ajustado.
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)


admin.site.unregister(User)
admin.site.register(User, UsuarioAdmin)
