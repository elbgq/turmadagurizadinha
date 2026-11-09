"""
Isolamento entre escolas (multiescola, etapa 1 — 09/11/2026): o que cada
conta pode ver. Toda tela de gestão da escola (etapa 2) deve buscar os
dados por estas funções — ou pelo IsolamentoPorEscolaMixin —, nunca com
Model.objects.all(), para nenhuma view esquecer o filtro. Fora do escopo
o resultado é 404 (e não 403), para não revelar que o registro existe.

Papéis:
- Equipe da plataforma (staff/superusuário): tudo, de todas as escolas.
- Admin da escola: só os professores e as turmas da própria escola; não
  vê alunos nem resultados de quiz.
- Professor: só as próprias turmas, os alunos delas e os resultados deles
  (com o histórico que o aluno trouxe de turmas anteriores).
- Aluno e demais: só a própria conta.

Conta de escola com o acesso bloqueado (contrato vencido ou escola
desativada) não vê nada.
"""

from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist, ValidationError
from django.http import Http404

from .models import Escola, Perfil, Turma


def eh_equipe_plataforma(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


def perfil_do_usuario(user):
    if not user.is_authenticated:
        return None
    return getattr(user, "perfil", None)


def escola_bloqueada(user):
    """Conta ligada a uma escola sem acesso liberado hoje (a equipe nunca é bloqueada)."""
    if eh_equipe_plataforma(user):
        return False
    perfil = perfil_do_usuario(user)
    return bool(perfil and perfil.escola_id and not perfil.escola.esta_liberada())


def _papel(user):
    """(perfil, tipo) de uma conta de escola liberada, ou (None, None)."""
    perfil = perfil_do_usuario(user)
    if perfil is None or escola_bloqueada(user):
        return None, None
    return perfil, perfil.tipo


def escolas_visiveis(user):
    if eh_equipe_plataforma(user):
        return Escola.objects.all()
    perfil, tipo = _papel(user)
    if perfil and perfil.escola_id and tipo in (Perfil.ADMIN_ESCOLA, Perfil.PROFESSOR):
        return Escola.objects.filter(pk=perfil.escola_id)
    return Escola.objects.none()


def turmas_visiveis(user):
    if eh_equipe_plataforma(user):
        return Turma.objects.all()
    perfil, tipo = _papel(user)
    if tipo == Perfil.ADMIN_ESCOLA:
        return Turma.objects.filter(escola_id=perfil.escola_id)
    if tipo == Perfil.PROFESSOR and perfil.escola_id:
        return Turma.objects.filter(escola_id=perfil.escola_id, professor=perfil)
    return Turma.objects.none()


def professores_visiveis(user):
    """Perfis de professor que a conta pode ver (e, na etapa 2, gerenciar)."""
    base = Perfil.objects.filter(tipo=Perfil.PROFESSOR)
    if eh_equipe_plataforma(user):
        return base
    perfil, tipo = _papel(user)
    if tipo == Perfil.ADMIN_ESCOLA:
        return base.filter(escola_id=perfil.escola_id)
    return Perfil.objects.none()


def alunos_visiveis(user):
    """Perfis de aluno que a conta pode ver: o professor, só os das próprias turmas."""
    base = Perfil.objects.filter(tipo=Perfil.ALUNO)
    if eh_equipe_plataforma(user):
        return base
    perfil, tipo = _papel(user)
    if tipo == Perfil.PROFESSOR and perfil.escola_id:
        return base.filter(turma__in=turmas_visiveis(user))
    if tipo == Perfil.ALUNO:
        return base.filter(pk=perfil.pk)
    return Perfil.objects.none()


def resultados_quiz_visiveis(user):
    """
    Resultados de quiz: o professor vê todo o histórico dos alunos que
    estão hoje nas turmas dele (o histórico acompanha o aluno quando ele
    muda de turma — decisão da cliente de 09/11/2026). O aluno, só os
    próprios. O admin da escola não vê resultados.
    """
    from quiz.models import ResultadoQuiz  # evita importação circular (quiz importa contas)

    if eh_equipe_plataforma(user):
        return ResultadoQuiz.objects.all()
    perfil, tipo = _papel(user)
    if tipo == Perfil.PROFESSOR:
        return ResultadoQuiz.objects.filter(perfil__in=alunos_visiveis(user))
    if perfil is not None and tipo != Perfil.ADMIN_ESCOLA:
        return ResultadoQuiz.objects.filter(perfil=perfil)
    return ResultadoQuiz.objects.none()


ESCOPOS = {
    "escolas": escolas_visiveis,
    "turmas": turmas_visiveis,
    "professores": professores_visiveis,
    "alunos": alunos_visiveis,
    "resultados_quiz": resultados_quiz_visiveis,
}


def do_escopo_ou_404(escopo, user, **filtros):
    """Igual ao get_object_or_404, mas só dentro do que a conta pode ver."""
    try:
        return ESCOPOS[escopo](user).get(**filtros)
    except (ObjectDoesNotExist, MultipleObjectsReturned, ValueError, ValidationError) as erro:
        raise Http404 from erro


class IsolamentoPorEscolaMixin:
    """
    Para as views de classe (ListView, DetailView, UpdateView...) da etapa 2:
    defina `escopo = "turmas"` (ou outra chave de ESCOPOS) e o queryset já
    vem filtrado pela conta logada — um id de outra escola na URL dá 404.
    """

    escopo = None

    def get_queryset(self):
        if self.escopo not in ESCOPOS:
            raise ValueError(f"{self.__class__.__name__}: defina escopo, uma de {sorted(ESCOPOS)}.")
        return ESCOPOS[self.escopo](self.request.user)
