from django.apps import apps as apps_reais
from django.contrib.auth.management import create_permissions
from django.db import migrations

NOME_GRUPO = "Equipe editorial"

# Cadastro das músicas do Cancioneiro (19/11/2026) pela Equipe editorial,
# no mesmo padrão de quiz/0003.
CODENAMES = ["add_musica", "change_musica", "delete_musica", "view_musica"]


def conceder_permissoes(apps, schema_editor):
    # As Permission só seriam criadas pelo post_migrate, depois de todas as
    # migrações — força a criação agora (mesmo motivo de obras/0002).
    create_permissions(apps_reais.get_app_config("cancioneiro"), verbosity=0)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupo, _ = Group.objects.get_or_create(name=NOME_GRUPO)
    grupo.permissions.add(
        *Permission.objects.filter(content_type__app_label="cancioneiro", codename__in=CODENAMES)
    )


def remover_permissoes(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    try:
        grupo = Group.objects.get(name=NOME_GRUPO)
    except Group.DoesNotExist:
        return
    grupo.permissions.remove(
        *Permission.objects.filter(content_type__app_label="cancioneiro", codename__in=CODENAMES)
    )


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("obras", "0002_grupo_equipe_editorial"),
        ("cancioneiro", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(conceder_permissoes, remover_permissoes),
    ]
