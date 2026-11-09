from django.apps import apps as apps_reais
from django.contrib.auth.management import create_permissions
from django.db import migrations

NOME_GRUPO = "Equipe administrativa"

# Multiescola (09/11/2026): a equipe da plataforma acompanha os resultados
# do quiz de todas as escolas pelo Admin (filtro por escola e turma). Só
# visualização: o histórico do aluno não é alterado nem apagado por ela.
CODENAMES = ["view_resultadoquiz", "view_respostaquiz"]


def conceder_permissoes(apps, schema_editor):
    create_permissions(apps_reais.get_app_config("quiz"), verbosity=0)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupo, _ = Group.objects.get_or_create(name=NOME_GRUPO)
    grupo.permissions.add(*Permission.objects.filter(content_type__app_label="quiz", codename__in=CODENAMES))


def remover_permissoes(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupo = Group.objects.filter(name=NOME_GRUPO).first()
    if grupo:
        grupo.permissions.remove(
            *Permission.objects.filter(content_type__app_label="quiz", codename__in=CODENAMES)
        )


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0005_resultadoquiz_turma"),
    ]

    operations = [
        migrations.RunPython(conceder_permissoes, remover_permissoes),
    ]
