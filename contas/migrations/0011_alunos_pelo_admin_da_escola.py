from django.db import migrations

GRUPO_ADMIN_ESCOLA = "Admin da escola"
GRUPO_PROFESSOR = "Professor"

# Decisão de 13/11/2026 (pedido do Eloi): o cadastro dos alunos passa do
# professor para o Admin da escola — cadastrar (um a um ou em lote),
# editar, mudar de turma, desativar, registrar o termo do responsável e
# gerar senhas/cartões, em todas as turmas da escola. O professor fica
# com view_turma (lista de alunos, termo só leitura, cartões sem senha) e
# ver_desempenho_turma (relatórios e atividade complementar), que continua
# exclusiva dele: o Admin da escola não recebe nenhuma permissão de
# desempenho.
CODENAMES = ["cadastrar_alunos"]
DESCRICAO_NOVA = "Pode cadastrar alunos nas turmas da própria escola"
DESCRICAO_ANTIGA = "Pode cadastrar alunos nas próprias turmas"


def _mover(apps, de, para):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    permissoes = Permission.objects.filter(content_type__app_label="contas", codename__in=CODENAMES)
    origem = Group.objects.filter(name=de).first()
    if origem:
        origem.permissions.remove(*permissoes)
    destino, _ = Group.objects.get_or_create(name=para)
    destino.permissions.add(*permissoes)


def _descrever(apps, descricao):
    # O Django não atualiza sozinho o nome de uma Permission que já existe.
    Permission = apps.get_model("auth", "Permission")
    Permission.objects.filter(content_type__app_label="contas", codename__in=CODENAMES).update(name=descricao)


def alunos_para_o_admin_da_escola(apps, schema_editor):
    _mover(apps, GRUPO_PROFESSOR, GRUPO_ADMIN_ESCOLA)
    _descrever(apps, DESCRICAO_NOVA)


def alunos_de_volta_ao_professor(apps, schema_editor):
    _mover(apps, GRUPO_ADMIN_ESCOLA, GRUPO_PROFESSOR)
    _descrever(apps, DESCRICAO_ANTIGA)


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0010_turmas_pelo_admin_da_escola"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="perfil",
            options={
                "permissions": [
                    ("cadastrar_professores", "Pode cadastrar professores da própria escola"),
                    ("cadastrar_alunos", DESCRICAO_NOVA),
                    ("ver_desempenho_turma", "Pode ver o desempenho das próprias turmas"),
                ],
                "verbose_name": "Perfil",
                "verbose_name_plural": "Perfis",
            },
        ),
        migrations.RunPython(alunos_para_o_admin_da_escola, alunos_de_volta_ao_professor),
    ]
