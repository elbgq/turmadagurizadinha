from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from .forms import CadastroForm, TemaForm
from .models import ConfiguracaoSite


def superuser_required(view_func):
    """
    Mesmo espírito do @permission_required("obras....", raise_exception=True)
    usado em obras/views.py, mas para uma ação que não é uma permissão de
    grupo — é restrita ao superusuário mesmo (ver contas/models.py,
    ConfiguracaoSite).
    """

    @wraps(view_func)
    def _wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapper


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


@superuser_required
def tema(request):
    """Tela própria (fora do Admin) para o superusuário trocar o tema de cores do site."""
    config = ConfiguracaoSite.obter()
    if request.method == "POST":
        form = TemaForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Tema atualizado.")
            return redirect("contas:tema")
    else:
        form = TemaForm(instance=config)
    return render(request, "contas/tema.html", {"form": form})
