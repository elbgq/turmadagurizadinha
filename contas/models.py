from django.contrib.auth.models import User
from django.db import models


class Perfil(models.Model):
    """
    Dados extras do usuário do Django, ligados 1 para 1 ao model User
    padrão. Login obrigatório em toda a plataforma. Desde 29/10/2026 não
    há autocadastro: as contas são criadas pela equipe administrativa no
    Django Admin (ver contas/admin.py), que também define o "tipo". Por
    isso o tipo agora é confiável — é ele que decide quem vê porcentagem
    e tempos no quiz (ver quiz/views.py).

    O e-mail é o identificador de login: o campo username do User guarda
    o próprio e-mail (ver forms.NovoUsuarioAdminForm).
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
        return f"{self.user.get_full_name() or self.user.email} ({self.get_tipo_display()})" # type: ignore

# ConfiguracaoSite (seletor de tema de 4 cores) foi removido em
# 28/09/2026 — a plataforma passou a usar um único tema fixo, a
# partir do Manual de Marca "Turma da Gurizadinha" (ver static/css/base.css).


class SolicitacaoAcesso(models.Model):
    """
    Pedido de acesso feito pelo formulário público "Solicitar acesso"
    (contas:solicitar_acesso) — o canal entre quem quer usar a plataforma
    e a equipe administrativa, já que não há autocadastro. A equipe
    analisa no Django Admin e, ao aprovar, a conta é criada e a pessoa
    recebe por e-mail o link para criar a senha (ver contas/admin.py).

    Pela LGPD, conta de aluno (criança) é pedida pelo professor ou pela
    escola, não pela própria criança: por isso o tipo do pedido é só
    Professor(a) ou "Escola, responsável ou outro", e os alunos vão como
    lista no campo "alunos", para a equipe criar as contas deles.
    """

    PENDENTE = "pendente"
    APROVADA = "aprovada"
    RECUSADA = "recusada"
    STATUS_CHOICES = [
        (PENDENTE, "Pendente"),
        (APROVADA, "Aprovada"),
        (RECUSADA, "Recusada"),
    ]
    TIPO_CHOICES = [
        (Perfil.PROFESSOR, "Professor(a)"),
        (Perfil.OUTRO, "Escola, responsável ou outro"),
    ]

    nome = models.CharField("Nome", max_length=150)
    email = models.EmailField("E-mail")
    tipo = models.CharField("Você é", max_length=20, choices=TIPO_CHOICES, default=Perfil.PROFESSOR)
    escola_turma = models.CharField("Escola e turma", max_length=200)
    alunos = models.TextField(
        "Alunos para cadastrar",
        blank=True,
        help_text="Opcional. Um aluno por linha, com nome e e-mail.",
    )
    mensagem = models.TextField("Mensagem", blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDENTE)
    criada_em = models.DateTimeField("Recebida em", auto_now_add=True)
    analisada_em = models.DateTimeField("Analisada em", null=True, blank=True)
    analisada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="Analisada por"
    )
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="Conta"
    )

    class Meta:
        verbose_name = "Solicitação de acesso"
        verbose_name_plural = "Solicitações de acesso"
        ordering = ["-criada_em"]

    def __str__(self):
        return f"{self.nome} <{self.email}> ({self.get_status_display()})"  # type: ignore
