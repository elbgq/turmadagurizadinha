from django.apps import apps as apps_reais
from django.contrib.auth.management import create_permissions
from django.db import migrations

NOME_GRUPO = "Equipe editorial"

# Cadastro das perguntas do quiz (Fase 7) pela equipe da cliente — mesmo
# grupo de obras/0002. ResultadoQuiz/RespostaQuiz continuam fora do grupo
# (restritos a superusuário/staff técnico).
CODENAMES = [
    "add_perguntaquiz", "change_perguntaquiz", "delete_perguntaquiz", "view_perguntaquiz",
    "add_alternativaquiz", "change_alternativaquiz", "delete_alternativaquiz", "view_alternativaquiz",
]


def conceder_permissoes(apps, schema_editor):
    # Mesmo motivo de obras/0002: as Permission só seriam criadas pelo
    # post_migrate, depois de todas as migrações — força a criação agora.
    create_permissions(apps_reais.get_app_config("quiz"), verbosity=0)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupo, _ = Group.objects.get_or_create(name=NOME_GRUPO)
    grupo.permissions.add(
        *Permission.objects.filter(content_type__app_label="quiz", codename__in=CODENAMES)
    )


def remover_permissoes(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    try:
        grupo = Group.objects.get(name=NOME_GRUPO)
    except Group.DoesNotExist:
        return
    grupo.permissions.remove(
        *Permission.objects.filter(content_type__app_label="quiz", codename__in=CODENAMES)
    )


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("obras", "0002_grupo_equipe_editorial"),
        ("quiz", "0002_perguntaquiz_alternativaquiz_respostaquiz"),
    ]

    operations = [
        migrations.RunPython(conceder_permissoes, remover_permissoes),
    ]
