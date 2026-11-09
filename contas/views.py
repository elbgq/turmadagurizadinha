from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.core.cache import cache
from django.shortcuts import redirect, render

from .emails import avisar_equipe_nova_solicitacao
from .forms import SolicitacaoAcessoForm

# Limite de pedidos por IP (proteção simples contra robôs e abuso).
LIMITE_SOLICITACOES = 5
JANELA_SEGUNDOS = 60 * 60


def ip_do_visitante(request):
    """
    IP de quem fez o pedido. Atrás do Nginx (produção), o REMOTE_ADDR de
    todo mundo é o do próprio Nginx (127.0.0.1) — o IP real vem no
    cabeçalho X-Forwarded-For, que cada proxy completa no fim. Só são
    confiáveis as últimas PROXIES_CONFIAVEIS posições (o começo da lista
    pode ter sido inventado pelo visitante), por isso o IP é lido de trás
    para frente. Sem proxy (PROXIES_CONFIAVEIS=0), vale o REMOTE_ADDR.
    """
    proxies = settings.PROXIES_CONFIAVEIS
    if proxies > 0:
        ips = [ip.strip() for ip in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if ip.strip()]
        if len(ips) >= proxies:
            return ips[-proxies]
    return request.META.get("REMOTE_ADDR", "")


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
        chave = f"solicitar_acesso:{ip_do_visitante(request)}"
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
