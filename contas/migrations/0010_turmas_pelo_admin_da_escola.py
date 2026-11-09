from django.db import migrations

GRUPO_ADMIN_ESCOLA = "Admin da escola"
GRUPO_PROFESSOR = "Professor"

# Decisão de 09/11/2026 (revisão da multiescola): quem cria e edita as
# turmas, e designa o professor de cada uma, é o Admin da escola. O
# professor continua vendo as próprias turmas e cuidando dos alunos delas
# (cadastro, cartões de acesso, relatórios e atividade complementar).
CODENAMES = ["add_turma", "change_turma"]


def _mover(apps, de, para):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    permissoes = Permission.objects.filter(content_type__app_label="contas", codename__in=CODENAMES)
    origem = Group.objects.filter(name=de).first()
    if origem:
        origem.permissions.remove(*permissoes)
    destino, _ = Group.objects.get_or_create(name=para)
    destino.permissions.add(*permissoes)


def turmas_para_o_admin_da_escola(apps, schema_editor):
    _mover(apps, GRUPO_PROFESSOR, GRUPO_ADMIN_ESCOLA)


def turmas_de_volta_ao_professor(apps, schema_editor):
    _mover(apps, GRUPO_ADMIN_ESCOLA, GRUPO_PROFESSOR)


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0009_grupos_de_papel"),
    ]

    operations = [
        migrations.RunPython(turmas_para_o_admin_da_escola, turmas_de_volta_ao_professor),
    ]
