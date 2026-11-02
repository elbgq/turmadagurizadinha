from django.apps import apps as apps_reais
from django.contrib.auth.management import create_permissions
from django.db import migrations

NOME_GRUPO = "Equipe administrativa"

# A equipe administrativa vê os pedidos de "Solicitar acesso" e os aprova
# ou recusa (as ações do Admin exigem "change"). Sem "add" — pedidos só
# chegam pelo site — e sem "delete", para manter o histórico.
CODENAMES = ["view_solicitacaoacesso", "change_solicitacaoacesso"]


def conceder_permissoes(apps, schema_editor):
    # Mesmo motivo de obras/0002: força a criação das Permission agora.
    create_permissions(apps_reais.get_app_config("contas"), verbosity=0)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupo, _ = Group.objects.get_or_create(name=NOME_GRUPO)
    grupo.permissions.add(
        *Permission.objects.filter(content_type__app_label="contas", codename__in=CODENAMES)
    )


def remover_permissoes(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    try:
        grupo = Group.objects.get(name=NOME_GRUPO)
    except Group.DoesNotExist:
        return
    grupo.permissions.remove(
        *Permission.objects.filter(content_type__app_label="contas", codename__in=CODENAMES)
    )


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0006_solicitacaoacesso"),
    ]

    operations = [
        migrations.RunPython(conceder_permissoes, remover_permissoes),
    ]
