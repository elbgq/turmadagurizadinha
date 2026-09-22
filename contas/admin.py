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


admin.site.unregister(User)
admin.site.register(User, UsuarioAdmin)
