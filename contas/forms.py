from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import Perfil


class CadastroForm(forms.Form):
    """
    Autocadastro aberto — qualquer pessoa pode criar conta (público em
    geral, aluno ou professor). O e-mail vira o username do User (é o
    identificador de login); o "tipo" é autodeclarado, sem verificação.
    """

    nome = forms.CharField(label="Nome", max_length=150)
    email = forms.EmailField(label="E-mail")
    tipo = forms.ChoiceField(label="Você é", choices=Perfil.TIPO_CHOICES)
    password1 = forms.CharField(label="Senha", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirme a senha", widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(username=email).exists():
            raise ValidationError("Já existe uma conta cadastrada com este e-mail.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "As senhas não coincidem.")
        return cleaned

    def save(self):
        email = self.cleaned_data["email"]
        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=self.cleaned_data["nome"],
            password=self.cleaned_data["password1"],
        )
        Perfil.objects.create(user=user, tipo=self.cleaned_data["tipo"])
        return user


class EmailAuthenticationForm(AuthenticationForm):
    """
    Mesma lógica do AuthenticationForm padrão do Django (o campo
    'username' continua existindo por baixo dos panos), só troca o rótulo
    para "E-mail", já que é isso que a pessoa digita para entrar.
    """

    username = forms.CharField(label="E-mail", widget=forms.EmailInput(attrs={"autofocus": True}))
