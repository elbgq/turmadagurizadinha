"""
Grupos de papel da plataforma multiescola (etapa 1, 09/11/2026), ao lado
dos grupos de equipe que já existiam ("Equipe administrativa" e "Equipe
editorial"). Quem decide o papel continua sendo o Perfil.tipo, definido
pela equipe da plataforma: o grupo acompanha o tipo sozinho (ver
sincronizar_grupo_do_papel, chamado pelo sinal de contas/signals.py), e
serve para dar as permissões das telas da escola (etapa 2) a cada papel.

Os grupos são criados pela migração contas/0009.
"""

from django.contrib.auth.models import Group

GRUPO_ADMIN_ESCOLA = "Admin da escola"
GRUPO_PROFESSOR = "Professor"
GRUPO_ALUNO = "Aluno"

# tipo do Perfil -> nome do grupo
GRUPO_DO_TIPO = {
    "admin_escola": GRUPO_ADMIN_ESCOLA,
    "professor": GRUPO_PROFESSOR,
    "aluno": GRUPO_ALUNO,
}
GRUPOS_DE_PAPEL = tuple(GRUPO_DO_TIPO.values())


def sincronizar_grupo_do_papel(user, tipo):
    """
    Deixa o usuário só no grupo de papel do tipo (ou em nenhum, para o tipo
    "outro"). Não mexe nos outros grupos, como os de equipe.
    """
    if not user.pk:
        return
    nome = GRUPO_DO_TIPO.get(tipo)
    atuais = set(user.groups.filter(name__in=GRUPOS_DE_PAPEL).values_list("name", flat=True))
    if atuais == ({nome} if nome else set()):
        return
    user.groups.remove(*Group.objects.filter(name__in=atuais - {nome}))
    if nome:
        grupo = Group.objects.filter(name=nome).first()
        if grupo:
            user.groups.add(grupo)
