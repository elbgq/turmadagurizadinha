from django.shortcuts import render

# Fase 7 (planejado): PerguntaQuiz/AlternativaQuiz e a lógica de
# temporizador, pontuação e navegação entre perguntas. O resultado de
# cada tentativa será gravado em ResultadoQuiz (Fase 4, já implementado
# em quiz/models.py), vinculado ao Perfil da pessoa logada e à Obra —
# login já é obrigatório em toda a plataforma, então isso substitui o
# desenho antigo (resultado só na sessão do navegador, sem histórico).


def quiz_obra(request, obra_slug):
    """
    Fase 7: Módulo de Quiz — temporizador, pontuação e relatório de
    desempenho para o professor.
    """
    return render(request, "quiz/quiz.html", {"obra_slug": obra_slug})


def quiz_resultado(request, obra_slug):
    """
    Relatório de desempenho do quiz. A partir da Fase 7, esta view passa
    a consultar ResultadoQuiz (histórico por conta) em vez da sessão do
    navegador.
    """
    return render(request, "quiz/resultado.html", {"obra_slug": obra_slug})
