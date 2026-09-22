from django.contrib.auth.models import User
from django.db import models


class Perfil(models.Model):
    """
    Dados extras do usuário do Django, ligados 1 para 1 ao model User
    padrão. Login obrigatório em toda a plataforma, com autocadastro
    aberto (ver contas/views.py); o "tipo" é autodeclarado no cadastro,
    sem verificação — serve para eventuais ajustes de UI no futuro (ex.:
    mensagens diferentes para professor), não é um controle de permissão.

    O e-mail é o identificador de login: o campo username do User guarda
    o próprio e-mail (ver forms.CadastroForm).
    """

    PROFESSOR = "professor"
    ALUNO = "aluno"
    OUTRO = "outro"
    TIPO_CHOICES = [
        (PROFESSOR, "Professor(a)"),
        (ALUNO, "Aluno(a)"),
        (OUTRO, "Outro"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=OUTRO)

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfis"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} ({self.get_tipo_display()})"
