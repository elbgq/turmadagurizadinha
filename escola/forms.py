from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from contas.models import LIMITE_ALUNOS_POR_TURMA, ConsentimentoResponsavel, Perfil, Turma

from .models import EntregaAtividade


class ProfessorForm(forms.Form):
    """Cadastro e edição de professor pelo admin da escola (nome e e-mail)."""

    nome = forms.CharField(label="Nome", max_length=150)
    email = forms.EmailField(label="E-mail", help_text="É o login do professor. O link para criar a senha vai para este e-mail.")

    def __init__(self, *args, escola, professor=None, **kwargs):
        self.escola = escola
        self.professor = professor  # User, na edição
        super().__init__(*args, **kwargs)
        if professor is not None:
            self.fields["nome"].initial = professor.first_name
            self.fields["email"].initial = professor.email

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        outros = User.objects.filter(username__iexact=email)
        if self.professor is not None:
            outros = outros.exclude(pk=self.professor.pk)
        if outros.exists():
            raise ValidationError("Já existe uma conta cadastrada com este e-mail.")
        return email

    def clean(self):
        dados = super().clean()
        if self.professor is None:
            # Limite do plano (Perfil.clean), antes de criar a conta.
            try:
                Perfil(tipo=Perfil.PROFESSOR, escola=self.escola).clean()
            except ValidationError as erro:
                for mensagens in erro.message_dict.values():
                    for mensagem in mensagens:
                        self.add_error(None, mensagem)
        return dados


class TurmaForm(forms.ModelForm):
    """
    Turma criada e editada pelo Admin da escola, que designa o professor
    responsável (revisão de 09/11/2026). Na lista de professores entram só
    os ativos da própria escola — e o atual, se a turma já tiver um que
    tenha sido desativado, para o formulário não trocar sem querer.
    """

    class Meta:
        model = Turma
        fields = ["nome", "ano_letivo", "professor", "ativa"]

    def __init__(self, *args, escola, **kwargs):
        self.escola = escola
        super().__init__(*args, **kwargs)
        if self.instance.pk is None:
            del self.fields["ativa"]
            self.instance.escola = escola  # para o Turma.clean conferir a escola do professor
        professores = Perfil.objects.filter(tipo=Perfil.PROFESSOR, escola=escola, user__is_active=True)
        if self.instance.professor_id:
            professores = professores | Perfil.objects.filter(pk=self.instance.professor_id)
        campo = self.fields["professor"]
        campo.queryset = professores.select_related("user").order_by("user__first_name")
        campo.label_from_instance = lambda perfil: perfil.user.first_name or perfil.user.email
        campo.empty_label = "— ainda sem professor(a) —"
        campo.help_text = "Só quem for designado(a) vê a turma e cadastra os alunos dela."

    def clean(self):
        dados = super().clean()
        nome, ano = dados.get("nome"), dados.get("ano_letivo")
        if nome and ano:
            repetida = Turma.objects.filter(escola=self.escola, nome__iexact=nome, ano_letivo=ano)
            if self.instance.pk:
                repetida = repetida.exclude(pk=self.instance.pk)
            if repetida.exists():
                raise ValidationError("A escola já tem uma turma com este nome neste ano letivo.")
        return dados


class AlunoForm(forms.Form):
    nome = forms.CharField(label="Nome do aluno", max_length=150)


class AlunosEmLoteForm(forms.Form):
    nomes = forms.CharField(
        label="Nomes dos alunos",
        widget=forms.Textarea(attrs={"rows": 12}),
        help_text="Um aluno por linha. Pode colar a lista da planilha da escola.",
    )

    def __init__(self, *args, turma, **kwargs):
        self.turma = turma
        super().__init__(*args, **kwargs)

    def clean_nomes(self):
        nomes = [" ".join(linha.split()) for linha in self.cleaned_data["nomes"].splitlines()]
        nomes = [nome[:150] for nome in nomes if nome]
        if not nomes:
            raise ValidationError("Informe ao menos um nome.")
        vagas = LIMITE_ALUNOS_POR_TURMA - self.turma.alunos_ativos().count()
        if len(nomes) > vagas:
            raise ValidationError(
                f"A turma tem {vagas} vaga(s) (limite de {LIMITE_ALUNOS_POR_TURMA} alunos) "
                f"e a lista tem {len(nomes)} nomes."
            )
        return nomes


class EditarAlunoForm(forms.Form):
    """Nome e turma do aluno — o Admin da escola pode movê-lo entre as turmas ativas da escola (13/11/2026)."""

    nome = forms.CharField(label="Nome do aluno", max_length=150)
    turma = forms.ModelChoiceField(label="Turma", queryset=Turma.objects.none())

    def __init__(self, *args, aluno, turmas, **kwargs):
        self.aluno = aluno  # Perfil
        super().__init__(*args, **kwargs)
        self.fields["turma"].queryset = turmas
        self.fields["nome"].initial = aluno.user.first_name
        self.fields["turma"].initial = aluno.turma_id

    def clean(self):
        dados = super().clean()
        turma = dados.get("turma")
        if turma and turma.pk != self.aluno.turma_id:
            self.aluno.turma = turma
            try:
                self.aluno.clean()  # limite de 30 na turma nova
            except ValidationError as erro:
                for mensagens in erro.message_dict.values():
                    for mensagem in mensagens:
                        self.add_error("turma", mensagem)
        return dados


class ConsentimentoForm(forms.ModelForm):
    class Meta:
        model = ConsentimentoResponsavel
        fields = [
            "nome_responsavel", "parentesco", "email_responsavel", "telefone_responsavel",
            "meio", "data_consentimento", "observacoes",
        ]
        widgets = {
            "data_consentimento": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }


class LinhaEntregaForm(forms.Form):
    """Uma linha da tela "Lançar atividade" (um aluno). Situação em branco = sem registro."""

    situacao = forms.ChoiceField(
        label="Situação", required=False,
        choices=[("", "—")] + EntregaAtividade.SITUACAO_CHOICES,
    )
    nota = forms.DecimalField(label="Nota", required=False, min_value=0, max_value=10, max_digits=4, decimal_places=1)
    observacao = forms.CharField(label="Observação", required=False, max_length=300)

    def __init__(self, *args, aluno, **kwargs):
        self.aluno = aluno
        super().__init__(*args, prefix=f"aluno{aluno.pk}", **kwargs)
        self.fields["nota"].widget.attrs.update({"step": "0.5", "class": "escola-nota"})

    def clean(self):
        dados = super().clean()
        if not dados.get("situacao") and (dados.get("nota") is not None or dados.get("observacao")):
            raise ValidationError("Escolha a situação para lançar nota ou observação.")
        if dados.get("situacao") == EntregaAtividade.NAO_ENTREGUE and dados.get("nota") is not None:
            raise ValidationError("Não dá para dar nota a quem não entregou.")
        return dados
