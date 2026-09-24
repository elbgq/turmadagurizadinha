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
        return f"{self.user.get_full_name() or self.user.email} ({self.get_tipo_display()})" # type: ignore


class ConfiguracaoSite(models.Model):
    """
    Configuração única do site (registro "singleton" — pk sempre 1).
    Hoje guarda só o tema de cores ativo; a troca fica numa tela própria
    (ver contas/views.py, restrita a superusuário — fora do Admin), não
    é uma permissão do grupo "Equipe editorial".

    Cada tema é um arquivo CSS em static/css/temas/ que só redefine as
    variáveis de cor (--cor-destaque, --cor-fundo, --cor-card) usadas em
    todo o base.css — a estrutura do site (layout, espaçamento) é a
    mesma nos quatro temas.
    """

    ATUAL = "atual"
    VERDE = "verde"
    AZUL = "azul"
    BORDO = "bordo"
    TEMA_CHOICES = [
        (ATUAL, "Atual (amarelo)"),
        (VERDE, "Verde claro"),
        (AZUL, "Azul claro"),
        (BORDO, "Bordô claro"),
    ]

    tema = models.CharField(max_length=20, choices=TEMA_CHOICES, default=ATUAL)

    class Meta:
        verbose_name = "Configuração do site"
        verbose_name_plural = "Configuração do site"

    def __str__(self):
        return f"Configuração do site (tema: {self.get_tema_display()})"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def obter(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
