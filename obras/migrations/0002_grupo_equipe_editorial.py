from django.apps import apps as apps_reais
from django.contrib.auth.management import create_permissions
from django.db import migrations

NOME_GRUPO = "Equipe editorial"

# Permissões de conteúdo (cadastro das obras/atividades) para a equipe da
# cliente — sem acesso a usuários, grupos, permissões ou aos resultados
# do quiz (ResultadoQuiz fica restrito a superusuário/staff técnico).
CODENAMES = [
    "add_obra", "change_obra", "delete_obra", "view_obra",
    "add_questao", "change_questao", "delete_questao", "view_questao",
    "add_alternativa", "change_alternativa", "delete_alternativa", "view_alternativa",
]


def criar_grupo(apps, schema_editor):
    # As Permission "add/change/delete/view_<model>" são criadas por um
    # sinal post_migrate, que só dispara depois que TODAS as migrações
    # deste comando terminam — nesta migração (que roda durante a
    # aplicação das migrações) elas ainda não existem. Força a criação
    # agora, usando o app registry real (StateApps não tem o que
    # create_permissions precisa), antes de montar o grupo.
    create_permissions(apps_reais.get_app_config("obras"), verbosity=0)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    grupo, _ = Group.objects.get_or_create(name=NOME_GRUPO)
    permissoes = Permission.objects.filter(
        content_type__app_label="obras", codename__in=CODENAMES
    )
    grupo.permissions.set(permissoes)


def remover_grupo(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name=NOME_GRUPO).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("obras", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(criar_grupo, remover_grupo),
    ]
