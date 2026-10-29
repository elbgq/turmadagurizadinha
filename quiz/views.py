import time

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from contas.models import Perfil
from obras.models import Obra
from obras.views import _obra_visivel_ou_404

from .forms import AlternativaQuizFormSet, PerguntaQuizFormSet
from .models import AlternativaQuiz, PerguntaQuiz, RespostaQuiz, ResultadoQuiz

# Fase 7 — Módulo de Quiz, em 3 etapas (plano aprovado em 29/10/2026):
# 1) modelos e cadastro das perguntas (seção "Cadastro", no fim do
#    arquivo); 2) telas do quiz para o aluno (abaixo: INICIAR, pergunta,
#    CORRETO/ERRADO com explicação, final), inspiradas no National
#    Geographic Kids conforme o documento da cliente de 28/10/2026;
#    3) gravação do ResultadoQuiz/RespostaQuiz, mensagens por faixa de
#    acerto e relatório. Sem limite de tempo (não pressionar a criança),
#    mas o tempo é medido para o professor. Telas renderizadas no
#    servidor, sem JavaScript, como o resto do site.


def _chave_sessao(obra):
    return f"quiz_{obra.pk}"


def _perguntas_do_quiz(obra):
    """
    Perguntas que entram no quiz, na ordem cadastrada: só as completas
    (3 a 5 alternativas, uma correta — PerguntaQuiz.esta_completa), para
    uma pergunta ainda em cadastro não quebrar o quiz de quem está jogando.
    """
    perguntas = obra.perguntas_quiz.prefetch_related("alternativas")
    return [p for p in perguntas if p.esta_completa]


def _tentativa(request, obra):
    """
    Tentativa em andamento, guardada na sessão do navegador: a lista de
    perguntas sorteada no INICIAR (fixa até o fim, mesmo que a equipe
    editorial mexa nas perguntas no meio do caminho), a hora do início,
    a hora em que cada pergunta apareceu e as respostas dadas. Na etapa
    3, o resultado final é gravado em ResultadoQuiz/RespostaQuiz (ver
    quiz_fim).
    """
    return request.session.get(_chave_sessao(obra))


def _proxima_pendente(tentativa):
    """Número (1, 2, 3...) da primeira pergunta ainda sem resposta, ou None."""
    for n, pergunta_id in enumerate(tentativa["perguntas"], start=1):
        if str(pergunta_id) not in tentativa["respostas"]:
            return n
    return None


def _pergunta_n_ou_404(tentativa, n):
    if not 1 <= n <= len(tentativa["perguntas"]):
        raise Http404
    pergunta_id = tentativa["perguntas"][n - 1]
    return get_object_or_404(PerguntaQuiz.objects.prefetch_related("alternativas"), pk=pergunta_id)


def quiz_obra(request, obra_slug):
    """
    INICIAR (POST): começa uma tentativa nova e vai para a pergunta 1 —
    também é o "Jogar de novo" da tela final. A página inicial do quiz
    (tema + botão INICIAR) é a própria porta de entrada da obra,
    obras:obra_quiz; um GET aqui só leva até ela.
    """
    obra = _obra_visivel_ou_404(obra_slug, request)
    if request.method != "POST":
        return redirect("obras:obra_quiz", slug=obra.slug)
    perguntas = _perguntas_do_quiz(obra)
    if not perguntas:
        return redirect("obras:obra_quiz", slug=obra.slug)
    request.session[_chave_sessao(obra)] = {
        "perguntas": [p.pk for p in perguntas],
        "inicio": time.time(),
        "mostrada": {},
        "respostas": {},
    }
    return redirect("quiz:pergunta", obra_slug=obra.slug, n=1)


def quiz_pergunta(request, obra_slug, n):
    """
    Uma pergunta por tela: "n/total", imagem, enunciado e as alternativas
    como botões. Ao clicar (POST), grava a resposta e vai para a tela
    CORRETO/ERRADO. Não dá para pular perguntas nem trocar uma resposta
    já dada (voltar no navegador leva de novo à tela da resposta).
    """
    obra = _obra_visivel_ou_404(obra_slug, request)
    tentativa = _tentativa(request, obra)
    if not tentativa:
        return redirect("obras:obra_quiz", slug=obra.slug)
    pergunta = _pergunta_n_ou_404(tentativa, n)
    chave = str(pergunta.pk)
    if chave in tentativa["respostas"]:
        return redirect("quiz:resposta", obra_slug=obra.slug, n=n)
    pendente = _proxima_pendente(tentativa)
    if n != pendente:
        return redirect("quiz:pergunta", obra_slug=obra.slug, n=pendente)

    if request.method == "POST":
        alternativa = pergunta.alternativas.filter(pk=request.POST.get("alternativa")).first()
        if alternativa:
            mostrada_em = tentativa["mostrada"].get(chave, time.time())
            tentativa["respostas"][chave] = {
                "alternativa": alternativa.pk,
                "correta": alternativa.correta,
                "tempo": max(0, round(time.time() - mostrada_em)),
            }
            request.session.modified = True
            return redirect("quiz:resposta", obra_slug=obra.slug, n=n)
    elif chave not in tentativa["mostrada"]:
        tentativa["mostrada"][chave] = time.time()
        request.session.modified = True

    return render(request, "quiz/pergunta.html", {
        "obra": obra, "pergunta": pergunta, "n": n, "total": len(tentativa["perguntas"]),
    })


def quiz_resposta(request, obra_slug, n):
    """
    Tela depois do clique: CORRETO ou ERRADO, a alternativa certa em
    destaque, a explicação logo abaixo (documento da cliente de
    28/10/2026) e o botão para a próxima pergunta ou para o resultado.
    """
    obra = _obra_visivel_ou_404(obra_slug, request)
    tentativa = _tentativa(request, obra)
    if not tentativa:
        return redirect("obras:obra_quiz", slug=obra.slug)
    pergunta = _pergunta_n_ou_404(tentativa, n)
    resposta = tentativa["respostas"].get(str(pergunta.pk))
    if not resposta:
        return redirect("quiz:pergunta", obra_slug=obra.slug, n=n)
    total = len(tentativa["perguntas"])
    return render(request, "quiz/resposta.html", {
        "obra": obra, "pergunta": pergunta, "n": n, "total": total,
        "acertou": resposta["correta"], "escolhida_id": resposta["alternativa"],
        "ultima": n == total,
    })


def _ve_porcentagem(user):
    """
    Porcentagem e tempos aparecem para quem tem perfil Professor(a) —
    decisão de 29/10/2026 — e para a equipe técnica (staff), que testa
    o quiz. O tipo do perfil é autodeclarado: isto é conforto de tela
    para o professor, não um controle de acesso.
    """
    perfil = getattr(user, "perfil", None)
    return user.is_staff or (perfil is not None and perfil.tipo == Perfil.PROFESSOR)


def _gravar_resultado(request, obra, tentativa):
    """
    Grava a tentativa terminada em ResultadoQuiz + uma RespostaQuiz por
    pergunta, uma vez só: o id fica na sessão, e recarregar a tela final
    não duplica o registro. O tempo total vai do INICIAR até aqui.
    """
    perguntas = PerguntaQuiz.objects.in_bulk(tentativa["perguntas"])
    respostas = tentativa["respostas"]
    with transaction.atomic():
        resultado = ResultadoQuiz.objects.create(
            perfil=request.user.perfil,
            obra=obra,
            pontuacao=sum(1 for r in respostas.values() if r["correta"]),
            total=len(tentativa["perguntas"]),
            tempo_segundos=max(0, round(time.time() - tentativa["inicio"])),
        )
        for ordem, pergunta_id in enumerate(tentativa["perguntas"], start=1):
            resposta = respostas[str(pergunta_id)]
            pergunta = perguntas.get(pergunta_id)
            RespostaQuiz.objects.create(
                resultado=resultado,
                pergunta=pergunta,
                alternativa=AlternativaQuiz.objects.filter(pk=resposta["alternativa"]).first(),
                enunciado=pergunta.enunciado if pergunta else "(pergunta excluída)",
                correta=resposta["correta"],
                tempo_segundos=resposta["tempo"],
                ordem=ordem,
            )
    tentativa["resultado_id"] = resultado.pk
    request.session.modified = True
    return resultado


def quiz_fim(request, obra_slug):
    """
    Tela final: quantas o aluno acertou e a mensagem da faixa de acerto
    (documento da cliente de 28/10/2026). Para o professor, também a
    porcentagem e o tempo, no total e por pergunta. A tentativa é
    gravada no histórico (ResultadoQuiz) na primeira vez que esta tela
    abre.
    """
    obra = _obra_visivel_ou_404(obra_slug, request)
    tentativa = _tentativa(request, obra)
    if not tentativa:
        return redirect("obras:obra_quiz", slug=obra.slug)
    pendente = _proxima_pendente(tentativa)
    if pendente:
        return redirect("quiz:pergunta", obra_slug=obra.slug, n=pendente)
    resultado = ResultadoQuiz.objects.filter(
        pk=tentativa.get("resultado_id"), perfil__user=request.user
    ).first() or _gravar_resultado(request, obra, tentativa)
    return render(request, "quiz/fim.html", {
        "obra": obra, "resultado": resultado,
        "ve_porcentagem": _ve_porcentagem(request.user),
        "respostas": resultado.respostas.all(),
    })


def quiz_resultado(request, obra_slug):
    """
    Relatório de desempenho: o histórico das tentativas da própria conta
    neste quiz, da mais recente para a mais antiga. Acertos para todos;
    porcentagem, tempo e o detalhe por pergunta para o professor. O
    relatório por turma/aluno (contrato da Fase 7) depende do model
    Turma, numa etapa seguinte.
    """
    obra = _obra_visivel_ou_404(obra_slug, request)
    resultados = (
        ResultadoQuiz.objects.filter(obra=obra, perfil__user=request.user)
        .prefetch_related("respostas")
    )
    return render(request, "quiz/resultado.html", {
        "obra": obra, "resultados": resultados,
        "ve_porcentagem": _ve_porcentagem(request.user),
    })


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
