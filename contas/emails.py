"""
E-mails do app contas ligados à criação de contas pela equipe
administrativa (29/10/2026). Sem servidor SMTP configurado no .env, o
Django só mostra os e-mails no terminal (ver EMAIL_BACKEND em
config/settings.py) — nada chega a ninguém.
"""

import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)


def _assunto(template, contexto):
    # Assunto de e-mail não pode ter quebra de linha (o nome vem do
    # formulário público).
    return " ".join(render_to_string(template, contexto).split())


def enviar_link_criar_senha(request, usuario):
    """
    Manda para a pessoa o link de criar a senha da conta nova — o mesmo
    link (e a mesma tela) do "Esqueceu a senha?". A conta ganha antes uma
    senha aleatória que ninguém conhece: com senha "inutilizável" o
    "Esqueceu a senha?" do Django ignora a conta, e a pessoa ficaria sem
    saída se o link expirasse.
    """
    usuario.set_password(get_random_string(40))
    usuario.save(update_fields=["password"])
    contexto = {
        "user": usuario,
        "link": request.build_absolute_uri(
            reverse(
                "contas:senha_redefinir",
                kwargs={
                    "uidb64": urlsafe_base64_encode(force_bytes(usuario.pk)),
                    "token": default_token_generator.make_token(usuario),
                },
            )
        ),
        "login": request.build_absolute_uri(reverse("contas:login")),
    }
    # Falha no servidor de e-mail não pode derrubar a tela do Admin (a
    # conta já foi criada): devolve False, o Admin avisa a equipe, e o
    # erro fica no log (revisão de 07/11/2026).
    try:
        send_mail(
            _assunto("contas/email/acesso_aprovado_assunto.txt", contexto),
            render_to_string("contas/email/acesso_aprovado.txt", contexto),
            None,
            [usuario.email],
        )
    except Exception:
        logger.exception("Falha ao enviar o link de criar senha para %s", usuario.email)
        return False
    return True


def avisar_equipe_nova_solicitacao(request, solicitacao):
    """Avisa a equipe (EMAIL_EQUIPE_ADMINISTRATIVA no .env) de um pedido novo."""
    if not settings.EMAIL_EQUIPE_ADMINISTRATIVA:
        return
    contexto = {
        "solicitacao": solicitacao,
        "link": request.build_absolute_uri(
            reverse("admin:contas_solicitacaoacesso_change", args=[solicitacao.pk])
        ),
    }
    send_mail(
        _assunto("contas/email/solicitacao_nova_assunto.txt", contexto),
        render_to_string("contas/email/solicitacao_nova.txt", contexto),
        None,
        [settings.EMAIL_EQUIPE_ADMINISTRATIVA],
        fail_silently=True,  # o pedido já está salvo; a equipe também o vê no Admin
    )
