from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.urls import path

from . import views
from .forms import EmailAuthenticationForm, EmailPasswordResetForm

app_name = "contas"

urlpatterns = [
    path("cadastro/", views.cadastro, name="cadastro"),
    path("tema/", views.tema, name="tema"),
    path(
        "login/",
        login_not_required(
            auth_views.LoginView.as_view(
                template_name="contas/login.html",
                authentication_form=EmailAuthenticationForm,
                redirect_authenticated_user=True,
            )
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="obras:home"),
        name="logout",
    ),
    path(
        "senha/",
        auth_views.PasswordChangeView.as_view(
            template_name="contas/trocar_senha.html",
            success_url="/contas/senha/feito/",
        ),
        name="trocar_senha",
    ),
    path(
        "senha/feito/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="contas/trocar_senha_feito.html",
        ),
        name="trocar_senha_feito",
    ),
    # "Esqueci minha senha" — fica fora do portão de login obrigatório
    # (@login_not_required), igual login/cadastro: é justamente para quem
    # não consegue entrar. O Django nunca revela se o e-mail existe ou não
    # (a tela "enviado" é sempre a mesma), e o link expira sozinho.
    path(
        "senha/esqueci/",
        login_not_required(
            auth_views.PasswordResetView.as_view(
                template_name="contas/senha_esqueci.html",
                email_template_name="contas/email/senha_reset.txt",
                subject_template_name="contas/email/senha_reset_assunto.txt",
                form_class=EmailPasswordResetForm,
                success_url="/contas/senha/esqueci/enviado/",
            )
        ),
        name="senha_esqueci",
    ),
    path(
        "senha/esqueci/enviado/",
        login_not_required(
            auth_views.PasswordResetDoneView.as_view(
                template_name="contas/senha_esqueci_enviado.html",
            )
        ),
        name="senha_esqueci_enviado",
    ),
    path(
        "senha/redefinir/<uidb64>/<token>/",
        login_not_required(
            auth_views.PasswordResetConfirmView.as_view(
                template_name="contas/senha_redefinir.html",
                success_url="/contas/senha/redefinir/feito/",
            )
        ),
        name="senha_redefinir",
    ),
    path(
        "senha/redefinir/feito/",
        login_not_required(
            auth_views.PasswordResetCompleteView.as_view(
                template_name="contas/senha_redefinir_feito.html",
            )
        ),
        name="senha_redefinir_feito",
    ),
]
