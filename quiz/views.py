from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render

from obras.models import Obra

from .forms import AlternativaQuizFormSet, PerguntaQuizFormSet
from .models import PerguntaQuiz

# Fase 7 — Módulo de Quiz, em 3 etapas (plano aprovado em 29/10/2026):
# 1) modelos e cadastro das perguntas (este arquivo, seção "Cadastro");
# 2) telas do quiz para o aluno (início, pergunta, CORRETO/ERRADO com
#    explicação, final); 3) gravação do ResultadoQuiz/RespostaQuiz,
#    mensagens por faixa de acerto e relatório. Sem limite de tempo.


def quiz_obra(request, obra_slug):
    """
    Fase 7, etapa 2 (a fazer): telas do quiz para o aluno.
    """
    return render(request, "quiz/quiz.html", {"obra_slug": obra_slug})


def quiz_resultado(request, obra_slug):
    """
    Relatório de desempenho do quiz. A partir da Fase 7 (etapa 3), esta
    view passa a consultar ResultadoQuiz (histórico por conta).
    """
    return render(request, "quiz/resultado.html", {"obra_slug": obra_slug})


# --------------------------------------------------------------------
# Cadastro das perguntas do quiz pela equipe editorial (Fase 7, etapa
# 1) — mesmo padrão de obras_editar/questao_alternativas em
# obras/views.py: perguntas num formset da obra, alternativas de cada
# pergunta em tela própria, depois de salvar. Permissões
# quiz.*_perguntaquiz / *_alternativaquiz, concedidas ao grupo "Equipe
# editorial" pela migration quiz/0003.
# --------------------------------------------------------------------


@permission_required("quiz.change_perguntaquiz", raise_exception=True)
def perguntas_editar(request, obra_pk):
    obra = get_object_or_404(Obra, pk=obra_pk)
    if request.method == "POST":
        formset = PerguntaQuizFormSet(request.POST, request.FILES, instance=obra)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Perguntas do quiz salvas.")
            return redirect("quiz:perguntas_editar", obra_pk=obra.pk)
    else:
        formset = PerguntaQuizFormSet(instance=obra)
    return render(request, "quiz/gestao/perguntas_form.html", {"formset": formset, "obra": obra})


@permission_required("quiz.change_alternativaquiz", raise_exception=True)
def pergunta_alternativas(request, pergunta_pk):
    pergunta = get_object_or_404(PerguntaQuiz, pk=pergunta_pk)
    if request.method == "POST":
        formset = AlternativaQuizFormSet(request.POST, instance=pergunta)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Alternativas salvas.")
            return redirect("quiz:perguntas_editar", obra_pk=pergunta.obra_id)
    else:
        formset = AlternativaQuizFormSet(instance=pergunta)
    return render(
        request, "quiz/gestao/pergunta_alternativas.html",
        {"formset": formset, "pergunta": pergunta},
    )
