from django import forms
from django.contrib.auth.forms import AdminUserCreationForm, AuthenticationForm, PasswordResetForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import Perfil, SolicitacaoAcesso


class NovoUsuarioAdminForm(AdminUserCreationForm):
    """
    Tela "Adicionar usuário" do Django Admin — único caminho para criar
    conta desde 29/10/2026 (o autocadastro público foi removido, para
    ninguém se declarar Professor(a) por conta própria). Pede nome, e-mail
    e tipo de uma vez; o e-mail vira o username do User, como sempre foi
    (é o identificador de login). O tipo é gravado no Perfil por
    UsuarioAdmin.save_model (ver admin.py), porque o Perfil só existe
    depois que o User é salvo (sinal de contas/signals.py).
    """

    tipo = forms.ChoiceField(label="Tipo", choices=Perfil.TIPO_CHOICES, initial=Perfil.ALUNO)

    class Meta(AdminUserCreationForm.Meta):
        fields = ("first_name", "email")
        field_classes = {}
        labels = {"first_name": "Nome"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["email"].required = True
        self.fields["first_name"].widget.attrs["autofocus"] = True
        # A opção "sem senha" do Django vira "mandar o link de criar senha"
        # (ver UsuarioAdmin.save_model e contas/emails.py).
        self.fields["usable_password"].label = "Senha"
        self.fields["usable_password"].help_text = ""
        self.fields["usable_password"].choices = [
            ("false", "Enviar por e-mail um link para a pessoa criar a senha"),
            ("true", "Definir a senha agora"),
        ]
        self.fields["usable_password"].initial = "false"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(username__iexact=email).exists():
            raise ValidationError("Já existe uma conta cadastrada com este e-mail.")
        return email

    def _post_clean(self):
        # O username precisa estar no User antes da validação de senha do
        # Django (que compara a senha com os dados da pessoa).
        email = self.cleaned_data.get("email")
        if email:
            self.instance.username = email
        super()._post_clean()


class SolicitacaoAcessoForm(forms.ModelForm):
    """
    Formulário público "Solicitar acesso" (ver SolicitacaoAcesso). O campo
    "site" é uma armadilha para robôs (honeypot): fica escondido na tela,
    então só um robô o preenche — a view finge que deu certo e descarta.
    """

    site = forms.CharField(required=False, label="Deixe este campo em branco")

    class Meta:
        model = SolicitacaoAcesso
        fields = ["nome", "email", "tipo", "escola_turma", "alunos", "mensagem"]
        widgets = {
            "alunos": forms.Textarea(attrs={"rows": 4}),
            "mensagem": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def eh_robo(self):
        return bool(self.cleaned_data.get("site"))


class EmailAuthenticationForm(AuthenticationForm):
    """
    Mesma lógica do AuthenticationForm padrão do Django (o campo
    'username' continua existindo por baixo dos panos), só troca o rótulo
    para "E-mail", já que é isso que a pessoa digita para entrar.
    """

    username = forms.CharField(label="E-mail", widget=forms.EmailInput(attrs={"autofocus": True}))

    def clean_username(self):
        # Maiúsculas e minúsculas não fazem diferença no e-mail (revisão de
        # 07/11/2026): sem isto, "Maria@..." não entraria na conta
        # "maria@...", porque o banco compara o login letra por letra. Usa
        # o login como está gravado; se não achar (ou achar mais de um),
        # segue com o que foi digitado e o Django recusa normalmente.
        digitado = self.cleaned_data["username"].strip()
        contas = list(User.objects.filter(username__iexact=digitado).values_list("username", flat=True)[:2])
        return contas[0] if len(contas) == 1 else digitado


class EmailPasswordResetForm(PasswordResetForm):
    """Mesma lógica do PasswordResetForm padrão, só troca o rótulo do campo para "E-mail"."""

    email = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"autofocus": True}))
