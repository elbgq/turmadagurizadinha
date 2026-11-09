from django.apps import apps as apps_reais
from django.contrib.auth.management import create_permissions
from django.db import migrations

NOME_GRUPO = "Equipe administrativa"

# A equipe da plataforma consulta as entregas de atividade de todas as
# escolas pelo Admin (09/11/2026). Só visualização: quem lança é o professor.
CODENAMES = ["view_entregaatividade"]


def conceder_permissoes(apps, schema_editor):
    create_permissions(apps_reais.get_app_config("escola"), verbosity=0)
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupo, _ = Group.objects.get_or_create(name=NOME_GRUPO)
    grupo.permissions.add(*Permission.objects.filter(content_type__app_label="escola", codename__in=CODENAMES))


def remover_permissoes(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupo = Group.objects.filter(name=NOME_GRUPO).first()
    if grupo:
        grupo.permissions.remove(
            *Permission.objects.filter(content_type__app_label="escola", codename__in=CODENAMES)
        )


class Migration(migrations.Migration):

    dependencies = [
        ("escola", "0001_entregaatividade"),
    ]

    operations = [
        migrations.RunPython(conceder_permissoes, remover_permissoes),
    ]
