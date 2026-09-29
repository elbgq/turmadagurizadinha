from django.contrib.auth import login
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import redirect, render

from .forms import CadastroForm


@login_not_required
def cadastro(request):
    """
    Autocadastro aberto — a única rota, junto com o login, que fica fora
    do portão de login obrigatório (ver LoginRequiredMiddleware em
    config/settings.py). Ao cadastrar, a pessoa já entra logada.
    """
    if request.user.is_authenticated:
        return redirect("obras:home")

    if request.method == "POST":
        form = CadastroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            return redirect("obras:home")
    else:
        form = CadastroForm()

    return render(request, "contas/cadastro.html", {"form": form})
