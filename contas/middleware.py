from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

from .escopo import escola_bloqueada

MENSAGEM_ESCOLA_BLOQUEADA = (
    "O acesso da sua escola à Turma da Gurizadinha está suspenso. "
    "Fale com a coordenação da escola."
)


class EscolaLiberadaMiddleware:
    """
    Bloqueio automático por contrato (decisão da cliente de 09/11/2026):
    quem já estava logado quando o contrato da escola venceu (ou a equipe
    desativou a escola) é desconectado no próximo clique e volta para a
    tela de entrar, com o aviso. O login novo é recusado em
    EmailAuthenticationForm.confirm_login_allowed. A equipe da plataforma
    (staff) nunca é bloqueada.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and escola_bloqueada(request.user):
            logout(request)
            messages.error(request, MENSAGEM_ESCOLA_BLOQUEADA)
            return redirect("contas:login")
        return self.get_response(request)
