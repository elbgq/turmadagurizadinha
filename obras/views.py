from django.contrib.auth.decorators import permission_required
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    AlternativaFormSet, ObraForm, PaginaATurminhaForm, PaginaQuemSomosForm,
    PersonagemATurminhaFormSet, QuestaoFormSet, TermoGlossarioFormSet,
    ValorQuemSomosFormSet,
)
from .models import Obra, PaginaATurminha, PaginaQuemSomos, Questao


def _filtrar_obras_por_busca(request, queryset):
    """
    Aplica o filtro de busca (texto no título + categoria) a partir dos
    parâmetros de URL (?q=...&categoria=...) — usado tanto por
    obra_lista (gestão) quanto por obra_lista_publica (acréscimo da
    reunião de 01/10/2026, item "campo de busca", confirmado com o
    usuário em 01/10/2026: formulário GET, texto livre + select de
    categoria, compartilhado pelas duas telas).
    """
    q = request.GET.get("q", "").strip()
    categoria = request.GET.get("categoria", "").strip()
    if q:
        queryset = queryset.filter(titulo__icontains=q)
    if categoria:
        queryset = queryset.filter(categoria=categoria)
    contexto_busca = {
        "q": q,
        "categoria_selecionada": categoria,
        "categorias": Obra.Categoria.choices,
        "filtros_ativos": bool(q or categoria),
    }
    return queryset, contexto_busca


def home(request):
    """
    Fase 5: página inicial com os cards das obras (colunas de 4 ou 6),
    cada card com ilustração e um breve texto estilo blog.

    Consulta real a partir da Fase 4; o layout completo (apresentação da
    plataforma, logotipo, grade final) fica para a Fase 5. Quem tem
    permissão de cadastro (obras.add_obra) vê um atalho para a tela de
    gestão de conteúdo (ver obra_lista abaixo).
    """
    obras = Obra.objects.filter(publicada=True)
    return render(request, "obras/home.html", {"obras": obras})


def quem_somos(request):
    """
    Página institucional "Quem somos" — link já disponível no navbar
    (ver templates/partials/navbar.html). Conteúdo (história, missão,
    visão, valores) editável pela equipe editorial desde 29/09/2026
    (ver PaginaQuemSomos/ValorQuemSomos em obras/models.py e
    quem_somos_editar abaixo) — antes disso o texto vinha fixo no
    template, a partir do Manual de Marca.
    """
    pagina, _ = PaginaQuemSomos.objects.get_or_create(pk=1)
    valores = pagina.valores.all()
    return render(request, "obras/quem_somos.html", {"pagina": pagina, "valores": valores})


def a_turminha(request):
    """
    Página institucional "A Turminha" — apresenta os personagens do
    Clube. Conteúdo (introdução, personagens) editável pela equipe
    editorial desde 29/09/2026 (ver PaginaATurminha/PersonagemATurminha
    em obras/models.py e a_turminha_editar abaixo) — antes disso o
    texto vinha fixo no template, a partir da seção "Personagens" do
    Manual de Marca (páginas 13 a 17).
    """
    pagina, _ = PaginaATurminha.objects.get_or_create(pk=1)
    personagens = pagina.personagens.all()
    return render(request, "obras/a_turminha.html", {"pagina": pagina, "personagens": personagens})


def detalhe_obra(request, slug):
    """
    Página da obra — texto completo rolável, categoria, Glossário
    Gauchês em destaque (fora do texto — acréscimo acordado em reunião
    de 01/10/2026) e os links para as páginas próprias de Resumo,
    Atividade e Quiz Interativo (que antes eram seções dentro desta
    mesma página — mudaram para rotas separadas na mesma reunião).
    """
    obra = get_object_or_404(Obra, slug=slug, publicada=True)
    termos_glossario = obra.termos_glossario.all()
    return render(
        request, "obras/detalhe.html",
        {"obra": obra, "termos_glossario": termos_glossario},
    )


def _obra_visivel_ou_404(slug, request):
    """
    Busca a obra pelo slug para as páginas de Resumo/Atividade/Quiz,
    mesma regra de visibilidade do download de PDF (atividade_pdf/
    resumo_pdf, abaixo): publicada, ou quem tem permissão de gestão de
    conteúdo (obras.view_obra) também pode acessar uma obra ainda não
    publicada (para conferir antes de publicar).
    """
    obra = get_object_or_404(Obra, slug=slug)
    if not obra.publicada and not request.user.has_perm("obras.view_obra"):
        raise Http404
    return obra


def obra_resumo(request, slug):
    """
    Página própria de "Resumo" da obra — tópicos para o professor usar
    em sala de aula, em texto, com um PDF opcional para download
    (acréscimo acordado em reunião com a cliente de 01/10/2026).
    """
    obra = _obra_visivel_ou_404(slug, request)
    return render(request, "obras/resumo.html", {"obra": obra})


def obra_atividade(request, slug):
    """
    Página própria de "Atividade" da obra — perguntas cadastradas (sem
    gabarito) e/ou PDF de atividade de apoio para impressão. Antes era
    uma seção dentro de obras/detalhe.html; passou a ter rota e
    template próprios (acréscimo de 01/10/2026).
    """
    obra = _obra_visivel_ou_404(slug, request)
    questoes = obra.questoes.prefetch_related("alternativas")
    return render(request, "obras/atividade.html", {"obra": obra, "questoes": questoes})


def obra_quiz(request, slug):
    """
    Página própria de "Quiz Interativo" da obra — só a porta de entrada
    para a lógica do quiz, que é da Fase 7 (ainda placeholder em
    quiz/views.py). Decisão da cliente em 01/10/2026: este botão não
    tem lógica própria aqui, só os links para quiz:quiz/quiz:resultado.
    """
    obra = _obra_visivel_ou_404(slug, request)
    return render(request, "obras/quiz.html", {"obra": obra})


def atividade_pdf(request, slug):
    """
    Download do PDF de "Atividade de apoio" da obra (acréscimo à Fase 6,
    28/09/2026) — só o arquivo, sem visualização embutida. O
    LoginRequiredMiddleware já exige login para chegar aqui; falta só
    checar se a obra é visível para quem pediu: publicada, ou quem tem
    permissão de gestão de conteúdo (obras.view_obra) também pode baixar
    de uma obra ainda não publicada.
    """
    obra = _obra_visivel_ou_404(slug, request)
    if not obra.atividade_pdf:
        raise Http404
    return FileResponse(
        obra.atividade_pdf.open("rb"),
        as_attachment=True,
        filename=f"{obra.slug}-atividade.pdf",
        content_type="application/pdf",
    )


def resumo_pdf(request, slug):
    """
    Download do PDF de "Resumo para o professor" da obra (acréscimo
    acordado em reunião de 01/10/2026) — mesmo padrão de atividade_pdf
    acima.
    """
    obra = _obra_visivel_ou_404(slug, request)
    if not obra.resumo_pdf:
        raise Http404
    return FileResponse(
        obra.resumo_pdf.open("rb"),
        as_attachment=True,
        filename=f"{obra.slug}-resumo.pdf",
        content_type="application/pdf",
    )


# --------------------------------------------------------------------
# Cadastro de conteúdo fora do Django Admin — telas para a equipe da
# cliente (grupo "Equipe editorial"), reaproveitando as mesmas
# permissões do Admin (obras.add_obra / change_obra / delete_obra /
# view_obra). O Admin continua existindo e funcionando normalmente;
# isto é só um caminho mais simples para quem só cadastra conteúdo.
# --------------------------------------------------------------------


@permission_required("obras.view_obra", raise_exception=True)
def obra_lista(request):
    """
    Lista de todas as obras (publicadas ou não) para gestão de conteúdo.

    Colunas desde 01/10/2026: Título, Publicada, Categoria e Ações — a
    coluna "Ordem" saiu da tabela (decisão da cliente; o campo continua
    no formulário de editar obra, para quem precisar ajustá-lo
    manualmente) e "Categoria" entrou. Ver também obra_lista_publica,
    a versão desta mesma tela para quem não tem permissão de gestão.
    """
    obras, contexto_busca = _filtrar_obras_por_busca(request, Obra.objects.all())
    return render(
        request, "obras/gestao/lista.html",
        {"obras": obras, "mostrar_publicada": True, "mostrar_acoes_gestao": True, **contexto_busca},
    )


def obra_lista_publica(request):
    """
    Lista pública de obras publicadas (acréscimo da reunião de
    01/10/2026, item 4) — qualquer usuário logado pode acessar, sem
    precisar da permissão `obras.view_obra` da Equipe Editorial (o
    login em si já é exigido pelo LoginRequiredMiddleware em todo o
    site, por isso não há decorator de permissão aqui).

    Mesmas colunas de "Gerenciar obras" (Título, Categoria, Ações),
    exceto "Publicada" — redundante aqui, já que só entram obras com
    `publicada=True` — e só a ação "Acessar Obra" (sem Editar/Excluir).
    Reaproveita o mesmo parcial de tabela (`obras/_tabela_obras.html`)
    e de busca (`obras/_busca_obras.html`) de obra_lista, variando só o
    queryset base e os mostrar_* do contexto.
    """
    obras, contexto_busca = _filtrar_obras_por_busca(
        request, Obra.objects.filter(publicada=True)
    )
    return render(
        request, "obras/lista_publica.html",
        {"obras": obras, "mostrar_publicada": False, "mostrar_acoes_gestao": False, **contexto_busca},
    )


@permission_required("obras.add_obra", raise_exception=True)
def obra_nova(request):
    if request.method == "POST":
        form = ObraForm(request.POST, request.FILES)
        if form.is_valid():
            obra = form.save()
            messages.success(request, f'Obra "{obra.titulo}" cadastrada.')
            return redirect("obras:obra_editar", pk=obra.pk)
    else:
        form = ObraForm()
    return render(request, "obras/gestao/obra_form.html", {"form": form, "obra": None})


@permission_required("obras.change_obra", raise_exception=True)
def obra_editar(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    if request.method == "POST":
        form = ObraForm(request.POST, request.FILES, instance=obra)
        formset = QuestaoFormSet(request.POST, instance=obra)
        glossario_formset = TermoGlossarioFormSet(request.POST, instance=obra, prefix="glossario")
        if form.is_valid() and formset.is_valid() and glossario_formset.is_valid():
            form.save()
            formset.save()
            glossario_formset.save()
            messages.success(request, f'Obra "{obra.titulo}" atualizada.')
            return redirect("obras:obra_editar", pk=obra.pk)
    else:
        form = ObraForm(instance=obra)
        formset = QuestaoFormSet(instance=obra)
        glossario_formset = TermoGlossarioFormSet(instance=obra, prefix="glossario")
    return render(
        request, "obras/gestao/obra_form.html",
        {"form": form, "formset": formset, "glossario_formset": glossario_formset, "obra": obra},
    )


@permission_required("obras.delete_obra", raise_exception=True)
def obra_excluir(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    if request.method == "POST":
        titulo = obra.titulo
        obra.delete()
        messages.success(request, f'Obra "{titulo}" excluída.')
        return redirect("obras:obra_lista")
    return render(request, "obras/gestao/obra_confirmar_exclusao.html", {"obra": obra})


@permission_required("obras.change_questao", raise_exception=True)
def questao_alternativas(request, questao_id):
    """Gerencia as alternativas de uma questão específica."""
    questao = get_object_or_404(Questao, pk=questao_id)
    if request.method == "POST":
        formset = AlternativaFormSet(request.POST, instance=questao)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Alternativas salvas.")
            return redirect("obras:obra_editar", pk=questao.obra_id)
    else:
        formset = AlternativaFormSet(instance=questao)
    return render(
        request, "obras/gestao/questao_alternativas.html",
        {"formset": formset, "questao": questao},
    )


# --------------------------------------------------------------------
# Edição do conteúdo institucional ("Quem somos" e "A Turminha"), pela
# equipe editorial — acréscimo de 29/09/2026. Permissões próprias
# (obras.change_paginaquemsomos / obras.change_paginaaturminha),
# concedidas ao grupo "Equipe editorial" pela migration 0007 (ver
# obras/migrations/). Mesmo padrão de get_or_create() usado nas views
# públicas quem_somos/a_turminha acima, já que é conteúdo singleton.
# --------------------------------------------------------------------


@permission_required("obras.change_paginaquemsomos", raise_exception=True)
def quem_somos_editar(request):
    pagina, _ = PaginaQuemSomos.objects.get_or_create(pk=1)
    if request.method == "POST":
        form = PaginaQuemSomosForm(request.POST, request.FILES, instance=pagina)
        formset = ValorQuemSomosFormSet(request.POST, instance=pagina)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Página "Quem somos" atualizada.')
            return redirect("obras:quem_somos_editar")
    else:
        form = PaginaQuemSomosForm(instance=pagina)
        formset = ValorQuemSomosFormSet(instance=pagina)
    return render(
        request, "obras/gestao/pagina_quem_somos_form.html",
        {"form": form, "formset": formset},
    )


@permission_required("obras.change_paginaaturminha", raise_exception=True)
def a_turminha_editar(request):
    pagina, _ = PaginaATurminha.objects.get_or_create(pk=1)
    if request.method == "POST":
        form = PaginaATurminhaForm(request.POST, request.FILES, instance=pagina)
        formset = PersonagemATurminhaFormSet(request.POST, request.FILES, instance=pagina)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Página "A Turminha" atualizada.')
            return redirect("obras:a_turminha_editar")
    else:
        form = PaginaATurminhaForm(instance=pagina)
        formset = PersonagemATurminhaFormSet(instance=pagina)
    return render(
        request, "obras/gestao/pagina_a_turminha_form.html",
        {"form": form, "formset": formset},
    )
