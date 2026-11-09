from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

# Multiescola (etapa 1, 09/11/2026 — reunião com a cliente da mesma data):
# a plataforma pode ser contratada por escolas. Tudo fica no mesmo banco, e
# cada conta de escola é "carimbada" com a Escola a que pertence (Perfil.escola).
# O conteúdo (obras e quizzes) é o mesmo para todas as escolas. Quem vê o quê
# fica centralizado em contas/escopo.py.

# Limite de alunos por turma (decisão da cliente de 09/11/2026).
LIMITE_ALUNOS_POR_TURMA = 30


def _hoje():
    return timezone.localdate()


def ano_atual():
    """Padrão do ano letivo da Turma (função, e não lambda, por causa das migrações)."""
    return _hoje().year


class EscolaQuerySet(models.QuerySet):
    def liberadas(self, hoje=None):
        """Escolas com acesso liberado hoje (ver Escola.esta_liberada)."""
        hoje = hoje or _hoje()
        return self.filter(ativa=True).filter(
            models.Q(contrato_inicio__isnull=True) | models.Q(contrato_inicio__lte=hoje),
            models.Q(contrato_fim__isnull=True) | models.Q(contrato_fim__gte=hoje),
        )


class Escola(models.Model):
    """
    Escola que contratou a plataforma. O acesso de todas as contas ligadas
    a ela (admin da escola, professores e alunos) é bloqueado sozinho
    quando o contrato vence — no dia seguinte a `contrato_fim` — ou quando
    a equipe da plataforma desmarca "Ativa" (decisão da cliente de
    09/11/2026: bloqueio automático). Ver contas/middleware.py e
    EmailAuthenticationForm.confirm_login_allowed. Renovar = estender a
    data de fim do contrato no Admin. A cobrança em si fica fora da
    plataforma.
    """

    nome = models.CharField("Nome", max_length=200)
    cnpj = models.CharField("CNPJ", max_length=18, blank=True)
    email_contato = models.EmailField("E-mail de contato", blank=True)
    telefone = models.CharField("Telefone", max_length=30, blank=True)
    limite_professores = models.PositiveIntegerField(
        "Limite de professores",
        default=5,
        help_text="Quantos professores ativos a escola pode ter, conforme o plano contratado. "
        "Professor desativado não conta.",
    )
    ativa = models.BooleanField(
        "Ativa", default=True,
        help_text="Desmarque para bloquear na hora o acesso de todas as contas da escola.",
    )
    contrato_inicio = models.DateField("Início do contrato", null=True, blank=True)
    contrato_fim = models.DateField(
        "Fim do contrato", null=True, blank=True,
        help_text="Depois desta data o acesso da escola é bloqueado automaticamente. "
        "Em branco = sem data de fim.",
    )
    observacoes = models.TextField("Observações", blank=True)
    criada_em = models.DateTimeField("Cadastrada em", auto_now_add=True)

    objects = EscolaQuerySet.as_manager()

    class Meta:
        verbose_name = "Escola"
        verbose_name_plural = "Escolas"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def esta_liberada(self, hoje=None):
        """Ativa e dentro do período do contrato (datas em branco não limitam)."""
        hoje = hoje or _hoje()
        if not self.ativa:
            return False
        if self.contrato_inicio and hoje < self.contrato_inicio:
            return False
        if self.contrato_fim and hoje > self.contrato_fim:
            return False
        return True

    def professores_ativos(self):
        return Perfil.objects.filter(escola=self, tipo=Perfil.PROFESSOR, user__is_active=True)

    def clean(self):
        if self.contrato_inicio and self.contrato_fim and self.contrato_fim < self.contrato_inicio:
            raise ValidationError({"contrato_fim": "O fim do contrato não pode ser antes do início."})
        if self.pk:
            ativos = self.professores_ativos().count()
            if self.limite_professores < ativos:
                raise ValidationError({
                    "limite_professores": f"A escola já tem {ativos} professores ativos. "
                    "Desative alguns antes de reduzir o limite."
                })


class Turma(models.Model):
    """
    Turma de uma escola (ex.: "3º ano B", ano letivo 2027), com o professor
    responsável. No máximo LIMITE_ALUNOS_POR_TURMA alunos ativos — validado
    em Perfil.clean, ao pôr o aluno na turma. Turmas de anos anteriores
    ficam guardadas (desmarque "Ativa"), para o histórico dos relatórios.
    """

    escola = models.ForeignKey(Escola, on_delete=models.PROTECT, related_name="turmas", verbose_name="Escola")
    nome = models.CharField("Nome", max_length=100, help_text='Ex.: "3º ano B".')
    ano_letivo = models.PositiveSmallIntegerField("Ano letivo", default=ano_atual)
    professor = models.ForeignKey(
        "Perfil",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="turmas_lecionadas",
        limit_choices_to={"tipo": "professor"},
        verbose_name="Professor(a) responsável",
    )
    ativa = models.BooleanField("Ativa", default=True)
    criada_em = models.DateTimeField("Cadastrada em", auto_now_add=True)

    class Meta:
        verbose_name = "Turma"
        verbose_name_plural = "Turmas"
        ordering = ["escola__nome", "-ano_letivo", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["escola", "nome", "ano_letivo"], name="turma_unica_por_escola_e_ano"
            ),
        ]

    def __str__(self):
        return f"{self.nome} ({self.ano_letivo}) — {self.escola}"

    def alunos_ativos(self):
        return self.alunos.filter(tipo=Perfil.ALUNO, user__is_active=True)

    def clean(self):
        if self.professor_id and self.escola_id:
            if self.professor.tipo != Perfil.PROFESSOR:
                raise ValidationError({"professor": "Escolha uma conta do tipo Professor(a)."})
            if self.professor.escola_id != self.escola_id:
                raise ValidationError({"professor": "Este professor(a) não é desta escola."})


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
    ADMIN_ESCOLA = "admin_escola"
    OUTRO = "outro"
    TIPO_CHOICES = [
        (PROFESSOR, "Professor(a)"),
        (ALUNO, "Aluno(a)"),
        (ADMIN_ESCOLA, "Administrador(a) da escola"),
        (OUTRO, "Outro"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=OUTRO)
    # Multiescola (09/11/2026). Em branco = conta direta da plataforma (equipe,
    # professores avulsos e as contas criadas antes das escolas existirem).
    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, null=True, blank=True, related_name="perfis", verbose_name="Escola"
    )
    # Só para alunos. Trocar de turma não apaga nada: o histórico do quiz
    # fica ligado ao aluno (ResultadoQuiz.perfil) e vai junto com ele
    # (decisão da cliente de 09/11/2026); ResultadoQuiz.turma guarda em que
    # turma ele estava quando respondeu.
    turma = models.ForeignKey(
        Turma, on_delete=models.SET_NULL, null=True, blank=True, related_name="alunos", verbose_name="Turma"
    )

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfis"
        # Permissões das telas da escola (etapa 2), dadas aos grupos de
        # papel pela migração 0009 — ver contas/papeis.py.
        permissions = [
            ("cadastrar_professores", "Pode cadastrar professores da própria escola"),
            ("cadastrar_alunos", "Pode cadastrar alunos nas próprias turmas"),
            ("ver_desempenho_turma", "Pode ver o desempenho das próprias turmas"),
        ]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} ({self.get_tipo_display()})" # type: ignore

    def _conta_ativa(self):
        # Na tela "Adicionar usuário" ainda não há User: conta como ativa.
        try:
            return self.user.is_active
        except User.DoesNotExist:
            return True

    def clean(self):
        """
        Regras de escola e turma (09/11/2026), checadas por todo formulário
        que salva o Perfil (Admin e, na etapa 2, as telas da escola):
        turma só para aluno e da mesma escola; admin da escola precisa de
        escola; limite de professores da escola e de alunos por turma.
        """
        erros = {}
        if self.turma_id:
            if self.tipo != self.ALUNO:
                erros["turma"] = "Só alunos ficam numa turma."
            elif self.escola_id is None:
                self.escola_id = self.turma.escola_id
            elif self.escola_id != self.turma.escola_id:
                erros["turma"] = "Esta turma é de outra escola."
        if self.tipo == self.ADMIN_ESCOLA and self.escola_id is None:
            erros["escola"] = "Informe a escola deste administrador(a)."
        if self.pk:
            turmas_fora = self.turmas_lecionadas.all()
            if self.tipo == self.PROFESSOR:
                turmas_fora = turmas_fora.exclude(escola_id=self.escola_id)
            nomes = ", ".join(str(t) for t in turmas_fora[:3])
            if nomes:
                erros.setdefault(
                    "tipo" if self.tipo != self.PROFESSOR else "escola",
                    f"Ainda é professor(a) responsável por: {nomes}. Troque o professor dessas turmas antes.",
                )
        if not erros and self._conta_ativa():
            if self.tipo == self.PROFESSOR and self.escola_id:
                outros = self.escola.professores_ativos().exclude(pk=self.pk).count()
                if outros >= self.escola.limite_professores:
                    erros["escola"] = (
                        f"Limite do plano atingido: {self.escola} já tem {outros} professores ativos "
                        f"(limite {self.escola.limite_professores}). Contate a equipe da plataforma."
                    )
            if self.tipo == self.ALUNO and self.turma_id:
                outros = self.turma.alunos_ativos().exclude(pk=self.pk).count()
                if outros >= LIMITE_ALUNOS_POR_TURMA:
                    erros["turma"] = f"A turma já tem {LIMITE_ALUNOS_POR_TURMA} alunos, o limite por turma."
        if erros:
            raise ValidationError(erros)

    def consentimento_valido(self):
        """Termo de consentimento do responsável em vigor (só faz sentido para aluno)."""
        return self.consentimentos.filter(revogado_em__isnull=True).order_by("-data_consentimento").first()

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


# Versão do termo de consentimento em vigor. Ao mudar o texto do termo,
# atualize aqui: os consentimentos ficam registrados com a versão aceita.
VERSAO_TERMO_CONSENTIMENTO = "2026-11"


class ConsentimentoResponsavel(models.Model):
    """
    Registro do consentimento do pai, mãe ou responsável legal para o
    tratamento dos dados do aluno (LGPD, art. 14: dados de criança só com
    consentimento específico de um dos pais ou responsável — decisão da
    cliente de 09/11/2026). Nesta etapa 1 é só o registro: quem consentiu,
    quando, como e em qual versão do termo. A revogação não apaga o
    registro (fica a prova de que existiu e de quando acabou).
    """

    PAPEL = "papel"
    DIGITAL = "digital"
    MEIO_CHOICES = [
        (PAPEL, "Termo em papel assinado (guardado pela escola)"),
        (DIGITAL, "Aceite digital"),
    ]

    aluno = models.ForeignKey(
        Perfil, on_delete=models.CASCADE, related_name="consentimentos",
        limit_choices_to={"tipo": "aluno"}, verbose_name="Aluno(a)",
    )
    nome_responsavel = models.CharField("Nome do responsável", max_length=150)
    parentesco = models.CharField("Parentesco ou vínculo", max_length=60, help_text="Ex.: mãe, pai, avó, tutor(a) legal.")
    email_responsavel = models.EmailField("E-mail do responsável", blank=True)
    telefone_responsavel = models.CharField("Telefone do responsável", max_length=30, blank=True)
    versao_termo = models.CharField("Versão do termo", max_length=20, default=VERSAO_TERMO_CONSENTIMENTO)
    meio = models.CharField("Como foi dado", max_length=20, choices=MEIO_CHOICES, default=PAPEL)
    data_consentimento = models.DateTimeField("Data do consentimento", default=timezone.now)
    registrado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="Registrado por"
    )
    revogado_em = models.DateTimeField(
        "Revogado em", null=True, blank=True,
        help_text="Preencha se o responsável retirou o consentimento.",
    )
    observacoes = models.TextField("Observações", blank=True)

    class Meta:
        verbose_name = "Consentimento do responsável (LGPD)"
        verbose_name_plural = "Consentimentos dos responsáveis (LGPD)"
        ordering = ["-data_consentimento"]

    def __str__(self):
        return f"{self.nome_responsavel} ({self.parentesco}) — {self.aluno}"

    @property
    def vigente(self):
        return self.revogado_em is None

    def clean(self):
        if self.aluno_id and self.aluno.tipo != Perfil.ALUNO:
            raise ValidationError({"aluno": "O consentimento é só para contas de aluno."})
