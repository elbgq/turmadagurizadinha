from django.shortcuts import render


def avaliacao_obra(request, obra_slug):
    """
    Fase 6: Módulo de Avaliações — questões sobre a obra, em versão
    impressa e versão interativa. O relatório de desempenho (app
    "relatorios") é exclusivo do quiz, então este app não precisa gravar
    nada na sessão.
    """
    return render(request, "avaliacoes/avaliacao.html", {"obra_slug": obra_slug})
