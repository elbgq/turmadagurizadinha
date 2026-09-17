from django.shortcuts import render


def home(request):
    """
    Fase 5: página inicial com os cards das obras (colunas de 4 ou 6),
    cada card com ilustração e um breve texto estilo blog.

    Por enquanto renderiza um template placeholder até o modelo `Obra`
    ser implementado na Fase 4.
    """
    obras = []  # TODO: substituir por Obra.objects.all() após a Fase 4
    return render(request, "obras/home.html", {"obras": obras})


def detalhe_obra(request, slug):
    """
    Fase 5: página da obra — texto completo rolável, quadro de tópicos
    para o professor e acesso às avaliações e ao quiz.
    """
    return render(request, "obras/detalhe.html", {"slug": slug})
