from django.apps import apps as apps_reais
from django.contrib.auth.management import create_permissions
from django.db import migrations

# Multiescola (etapa 1, 09/11/2026). Mesmos nomes de contas/papeis.py
# (copiados aqui de propósito: a migração não pode depender de código que
# muda depois).
GRUPO_ADMIN_ESCOLA = "Admin da escola"
GRUPO_PROFESSOR = "Professor"
GRUPO_ALUNO = "Aluno"
EQUIPE_ADMINISTRATIVA = "Equipe administrativa"
GRUPO_DO_TIPO = {"admin_escola": GRUPO_ADMIN_ESCOLA, "professor": GRUPO_PROFESSOR, "aluno": GRUPO_ALUNO}

# Permissões de cada grupo (todas do app contas). Os papéis da escola não
# entram no Django Admin (não são staff): estas permissões servem às telas
# da etapa 2. O aluno não precisa de nenhuma — o grupo só identifica o papel.
PERMISSOES = {
    GRUPO_ADMIN_ESCOLA: ["cadastrar_professores", "view_turma"],
    GRUPO_PROFESSOR: ["cadastrar_alunos", "ver_desempenho_turma", "add_turma", "change_turma", "view_turma"],
    GRUPO_ALUNO: [],
    # A equipe da plataforma cuida das escolas, turmas e consentimentos
    # pelo Admin — sem excluir, como nas outras permissões dela (0005).
    EQUIPE_ADMINISTRATIVA: [
        "add_escola", "change_escola", "view_escola",
        "add_turma", "change_turma", "view_turma",
        "add_consentimentoresponsavel", "change_consentimentoresponsavel", "view_consentimentoresponsavel",
    ],
}


def criar_grupos(apps, schema_editor):
    # Mesmo motivo de obras/0002: força a criação das Permission agora.
    create_permissions(apps_reais.get_app_config("contas"), verbosity=0)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    Perfil = apps.get_model("contas", "Perfil")
    for nome, codenames in PERMISSOES.items():
        grupo, _ = Group.objects.get_or_create(name=nome)
        grupo.permissions.add(*Permission.objects.filter(content_type__app_label="contas", codename__in=codenames))

    # Contas que já existem entram no grupo do tipo que já têm.
    for tipo, nome in GRUPO_DO_TIPO.items():
        grupo = Group.objects.get(name=nome)
        for perfil in Perfil.objects.filter(tipo=tipo).select_related("user"):
            perfil.user.groups.add(grupo)


def remover_grupos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    Group.objects.filter(name__in=GRUPO_DO_TIPO.values()).delete()
    equipe = Group.objects.filter(name=EQUIPE_ADMINISTRATIVA).first()
    if equipe:
        equipe.permissions.remove(
            *Permission.objects.filter(
                content_type__app_label="contas", codename__in=PERMISSOES[EQUIPE_ADMINISTRATIVA]
            )
        )


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0008_escola_turma_consentimento"),
    ]

    operations = [
        migrations.RunPython(criar_grupos, remover_grupos),
    ]
