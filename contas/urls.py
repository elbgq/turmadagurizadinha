from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.urls import path

from . import views
from .forms import EmailAuthenticationForm

app_name = "contas"

urlpatterns = [
    path("cadastro/", views.cadastro, name="cadastro"),
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
]
