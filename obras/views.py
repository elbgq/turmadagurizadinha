from django.contrib.auth.decorators import permission_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AlternativaFormSet, ObraForm, QuestaoFormSet
from .models import Obra, Questao


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


def detalhe_obra(request, slug):
    """
    Fase 5: página da obra — texto completo rolável, quadro de tópicos
    para o professor, atividades de apoio para impressão (perguntas
    cadastradas na própria obra, sem gabarito — ver obras/models.py) e
    acesso ao quiz.
    """
    obra = get_object_or_404(Obra, slug=slug, publicada=True)
    questoes = obra.questoes.prefetch_related("alternativas")
    return render(request, "obras/detalhe.html", {"obra": obra, "questoes": questoes})


# --------------------------------------------------------------------
# Cadastro de conteúdo fora do Django Admin — telas para a equipe da
# cliente (grupo "Equipe editorial"), reaproveitando as mesmas
# permissões do Admin (obras.add_obra / change_obra / delete_obra /
# view_obra). O Admin continua existindo e funcionando normalmente;
# isto é só um caminho mais simples para quem só cadastra conteúdo.
# --------------------------------------------------------------------


@permission_required("obras.view_obra", raise_exception=True)
def obra_lista(request):
    """Lista de todas as obras (publicadas ou não) para gestão de conteúdo."""
    obras = Obra.objects.all()
    return render(request, "obras/gestao/lista.html", {"obras": obras})


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
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f'Obra "{obra.titulo}" atualizada.')
            return redirect("obras:obra_editar", pk=obra.pk)
    else:
        form = ObraForm(instance=obra)
        formset = QuestaoFormSet(instance=obra)
    return render(
        request, "obras/gestao/obra_form.html",
        {"form": form, "formset": formset, "obra": obra},
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
