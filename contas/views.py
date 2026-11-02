from django.contrib.auth.decorators import login_not_required
from django.core.cache import cache
from django.shortcuts import redirect, render

from .emails import avisar_equipe_nova_solicitacao
from .forms import SolicitacaoAcessoForm

# Limite de pedidos por IP (proteção simples contra robôs e abuso).
LIMITE_SOLICITACOES = 5
JANELA_SEGUNDOS = 60 * 60


@login_not_required
def solicitar_acesso(request):
    """
    Formulário público "Solicitar acesso" — o canal entre quem quer usar a
    plataforma e a equipe administrativa, já que as contas só são criadas
    por ela no Django Admin (sem autocadastro desde 29/10/2026). O pedido
    fica gravado em SolicitacaoAcesso e a equipe é avisada por e-mail.
    """
    if request.user.is_authenticated:
        return redirect("obras:home")

    if request.method == "POST":
        chave = f"solicitar_acesso:{request.META.get('REMOTE_ADDR', '')}"
        if cache.get(chave, 0) >= LIMITE_SOLICITACOES:
            return render(request, "contas/solicitar_acesso.html", {"form": SolicitacaoAcessoForm(), "limite": True})

        form = SolicitacaoAcessoForm(request.POST)
        if form.is_valid():
            cache.set(chave, cache.get(chave, 0) + 1, JANELA_SEGUNDOS)
            if not form.eh_robo():
                solicitacao = form.save()
                avisar_equipe_nova_solicitacao(request, solicitacao)
            return redirect("contas:solicitar_acesso_enviado")
    else:
        form = SolicitacaoAcessoForm()

    return render(request, "contas/solicitar_acesso.html", {"form": form})


@login_not_required
def solicitar_acesso_enviado(request):
    return render(request, "contas/solicitar_acesso_enviado.html")
