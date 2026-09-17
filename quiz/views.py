from django.shortcuts import render

# Chave de sessão usada para guardar o resultado do quiz entre o momento em
# que o aluno termina de responder e a tela de resultado (ver
# quiz_resultado abaixo). Sem login e sem histórico salvo em banco —
# decisão do projeto: o relatório de desempenho é exibido na hora.
CHAVE_SESSAO_RESULTADO = "quiz_resultado::{slug}"


def quiz_obra(request, obra_slug):
    """
    Fase 7: Módulo de Quiz — temporizador, pontuação e relatório de
    desempenho para o professor.

    TODO (Fase 7): ao final do quiz (última pergunta respondida ou tempo
    esgotado), gravar o resultado na sessão e redirecionar para a tela de
    resultado, por exemplo:

        request.session[CHAVE_SESSAO_RESULTADO.format(slug=obra_slug)] = {
            "pontuacao": pontuacao,
            "total": total_perguntas,
            "tempo_segundos": tempo_gasto,
        }
        return redirect("quiz:resultado", obra_slug=obra_slug)
    """
    return render(request, "quiz/quiz.html", {"obra_slug": obra_slug})


def quiz_resultado(request, obra_slug):
    """
    Relatório de desempenho do quiz: exibido logo após o término das
    respostas, para quem está aplicando o quiz naquele momento — sem
    login de professor e sem histórico salvo (decisão do projeto).
    """
    resultado = request.session.get(CHAVE_SESSAO_RESULTADO.format(slug=obra_slug))

    contexto = {
        "obra_slug": obra_slug,
        "resultado": resultado,
        "tem_resultado": bool(resultado),
    }
    return render(request, "quiz/resultado.html", contexto)
