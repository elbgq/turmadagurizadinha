from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MusicaForm
from .models import Musica


def lista(request):
    """
    Aba "Cancioneiro" (reunião de 19/11/2026): cards das músicas
    publicadas, para qualquer usuário logado (o login já é exigido pelo
    LoginRequiredMiddleware). Cada card abre o vídeo no YouTube.
    """
    musicas = Musica.objects.filter(publicada=True)
    return render(request, "cancioneiro/lista.html", {"musicas": musicas})


@permission_required("cancioneiro.view_musica", raise_exception=True)
def gestao_lista(request):
    """Todas as músicas (publicadas ou não), para a Equipe editorial."""
    return render(request, "cancioneiro/gestao/lista.html", {"musicas": Musica.objects.all()})


@permission_required("cancioneiro.add_musica", raise_exception=True)
def musica_nova(request):
    form = MusicaForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        musica = form.save()
        messages.success(request, f'Música "{musica.titulo}" cadastrada.')
        return redirect("cancioneiro:gestao_lista")
    return render(request, "cancioneiro/gestao/musica_form.html", {"form": form})


@permission_required("cancioneiro.change_musica", raise_exception=True)
def musica_editar(request, pk):
    musica = get_object_or_404(Musica, pk=pk)
    form = MusicaForm(request.POST or None, request.FILES or None, instance=musica)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f'Música "{musica.titulo}" salva.')
        return redirect("cancioneiro:gestao_lista")
    return render(request, "cancioneiro/gestao/musica_form.html", {"form": form, "musica": musica})


@permission_required("cancioneiro.delete_musica", raise_exception=True)
def musica_excluir(request, pk):
    musica = get_object_or_404(Musica, pk=pk)
    if request.method == "POST":
        titulo = musica.titulo
        musica.delete()
        messages.success(request, f'Música "{titulo}" excluída.')
        return redirect("cancioneiro:gestao_lista")
    return render(request, "cancioneiro/gestao/musica_confirmar_exclusao.html", {"musica": musica})
