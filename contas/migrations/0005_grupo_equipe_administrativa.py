from django.apps import apps as apps_reais
from django.contrib.auth.management import create_permissions
from django.db import migrations

NOME_GRUPO = "Equipe administrativa"

# Criação das contas de alunos e professores pela equipe da Turma da
# Gurizadinha (29/10/2026 — o autocadastro público foi removido). Pode
# criar e editar usuários e o Perfil (tipo), mas não excluir; os campos
# de permissão e as contas de staff ficam protegidos em contas/admin.py.
PERMISSOES = {
    "auth": ["add_user", "change_user", "view_user"],
    "contas": ["add_perfil", "change_perfil", "view_perfil"],
}


def criar_grupo(apps, schema_editor):
    # Mesmo motivo de obras/0002: as Permission só seriam criadas pelo
    # post_migrate, depois de todas as migrações — força a criação agora.
    for app_label in PERMISSOES:
        create_permissions(apps_reais.get_app_config(app_label), verbosity=0)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupo, _ = Group.objects.get_or_create(name=NOME_GRUPO)
    for app_label, codenames in PERMISSOES.items():
        grupo.permissions.add(
            *Permission.objects.filter(content_type__app_label=app_label, codename__in=codenames)
        )


def remover_grupo(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name=NOME_GRUPO).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contas", "0004_criar_perfis_faltantes"),
    ]

    operations = [
        migrations.RunPython(criar_grupo, remover_grupo),
    ]
