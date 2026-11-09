"""
Cálculos dos relatórios de desempenho por turma e por aluno (multiescola,
etapa 3 — 09/11/2026). Ficam fora das views para os testes conferirem os
números direto.

Regras:
- Os alunos considerados são os que estão hoje na turma, com todo o
  histórico deles (o histórico acompanha o aluno — decisão da cliente).
- Para a média da turma vale a 1ª tentativa de cada aluno em cada quiz
  (mostra o que ele aprendeu com a leitura, antes de repetir o quiz); a
  melhor tentativa e o número de tentativas aparecem ao lado.
- "Acertos por pergunta" também usa as 1as tentativas: mostra em quais
  perguntas a turma teve mais dificuldade.
"""

from collections import OrderedDict, defaultdict

from obras.models import Obra
from quiz.models import RespostaQuiz, ResultadoQuiz

from .models import EntregaAtividade


def _media(valores):
    return round(sum(valores) / len(valores)) if valores else None


def _tentativas_por_aluno_e_obra(alunos, obras=None):
    """{(aluno_id, obra_id): [resultados, da mais antiga para a mais nova]}"""
    resultados = ResultadoQuiz.objects.filter(perfil__in=alunos).order_by("criado_em", "pk")
    if obras is not None:
        resultados = resultados.filter(obra__in=obras)
    tentativas = defaultdict(list)
    for resultado in resultados:
        tentativas[(resultado.perfil_id, resultado.obra_id)].append(resultado)
    return tentativas


def _situacao_quiz(tentativas):
    if not tentativas:
        return None
    return {
        "primeira": tentativas[0],
        "melhor": max(tentativas, key=lambda r: (r.porcentagem, -r.tempo_segundos)),
        "quantidade": len(tentativas),
    }


def obras_do_relatorio():
    return Obra.objects.filter(publicada=True).order_by("ordem", "titulo")


def resumo_da_turma(alunos):
    """Uma linha por obra publicada: quantos fizeram o quiz, média da 1ª tentativa e entregas."""
    alunos = list(alunos)
    total = len(alunos)
    obras = list(obras_do_relatorio())
    tentativas = _tentativas_por_aluno_e_obra(alunos, obras)
    entregas = defaultdict(int)
    for obra_id in EntregaAtividade.objects.filter(
        aluno__in=alunos, situacao=EntregaAtividade.ENTREGUE
    ).values_list("obra_id", flat=True):
        entregas[obra_id] += 1
    linhas = []
    for obra in obras:
        primeiras = [tentativas[(a.pk, obra.pk)][0] for a in alunos if tentativas.get((a.pk, obra.pk))]
        linhas.append({
            "obra": obra,
            "fizeram": len(primeiras),
            "total": total,
            "media_primeira": _media([r.porcentagem for r in primeiras]),
            "entregaram": entregas[obra.pk],
        })
    return linhas


def detalhe_da_obra(alunos, obra):
    """Por aluno: quiz (1ª, melhor, tentativas) e atividade; e acertos por pergunta."""
    alunos = list(alunos)
    tentativas = _tentativas_por_aluno_e_obra(alunos, [obra])
    entregas = {e.aluno_id: e for e in EntregaAtividade.objects.filter(aluno__in=alunos, obra=obra)}
    linhas = [
        {"aluno": a, "quiz": _situacao_quiz(tentativas.get((a.pk, obra.pk), [])), "entrega": entregas.get(a.pk)}
        for a in alunos
    ]
    primeiras = [linha["quiz"]["primeira"] for linha in linhas if linha["quiz"]]

    perguntas = OrderedDict()
    respostas = RespostaQuiz.objects.filter(resultado__in=primeiras).order_by("ordem", "pk")
    for resposta in respostas:
        chave = resposta.pergunta_id or resposta.enunciado
        item = perguntas.setdefault(chave, {"enunciado": resposta.enunciado, "respostas": 0, "certas": 0, "tempos": []})
        item["respostas"] += 1
        item["certas"] += int(resposta.correta)
        item["tempos"].append(resposta.tempo_segundos)
    for item in perguntas.values():
        item["porcentagem"] = round(item["certas"] * 100 / item["respostas"])
        item["tempo_medio"] = _media(item.pop("tempos"))

    return {
        "linhas": linhas,
        "fizeram": len(primeiras),
        "media_primeira": _media([r.porcentagem for r in primeiras]),
        "media_melhor": _media([linha["quiz"]["melhor"].porcentagem for linha in linhas if linha["quiz"]]),
        "perguntas": list(perguntas.values()),
    }


def historico_do_aluno(aluno):
    """Todas as tentativas de quiz e entregas do aluno, de todas as turmas por onde passou."""
    return {
        "resultados": (
            ResultadoQuiz.objects.filter(perfil=aluno)
            .select_related("obra", "turma").prefetch_related("respostas").order_by("-criado_em")
        ),
        "entregas": EntregaAtividade.objects.filter(aluno=aluno).select_related("obra", "turma"),
    }
