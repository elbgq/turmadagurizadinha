from datetime import timedelta

from django.contrib import admin
from django.contrib.admin.utils import unquote
from django.contrib.auth.admin import UserAdmin
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .emails import enviar_link_criar_senha
from .forms import NovoUsuarioAdminForm
from .models import LIMITE_ALUNOS_POR_TURMA, ConsentimentoResponsavel, Escola, Perfil, SolicitacaoAcesso, Turma
from .papeis import sincronizar_grupo_do_papel


AVISO_EMAIL_FALHOU = (
    "Não foi possível enviar o e-mail com o link de criar senha para {emails}. "
    "A conta foi criada; quando o e-mail voltar a funcionar, a pessoa pode usar "
    "\"Esqueceu a senha?\" na tela de entrar."
)


class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name_plural = "Perfil"
    fields = ("tipo", "escola", "turma")


class UsuarioAdmin(UserAdmin):
    """
    Reaproveita o UserAdmin padrão do Django (gerencia login, senha e
    permissões) só acrescentando o Perfil (tipo: professor/aluno/outro)
    como inline — evita duplicar tela de cadastro de usuário no Admin.

    Desde 29/10/2026 é aqui que nascem todas as contas (não há mais
    autocadastro): o superusuário e o grupo "Equipe administrativa" (ver
    migração 0005) criam alunos e professores. Quem não é superusuário
    não vê nem altera os campos de permissão (staff, superusuário, grupos,
    permissões) — assim a equipe administrativa cria contas sem conseguir
    dar a si mesma (ou a outros) mais acesso ao Admin. Nas contas de staff
    ela só altera o tipo; nas de superusuário, nada.
    """

    inlines = (PerfilInline,)
    add_form = NovoUsuarioAdminForm
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "first_name", "email", "tipo", "escola", "turma",
                    "usable_password", "password1", "password2",
                ),
            },
        ),
    )
    list_display = ("username", "first_name", "tipo", "escola", "turma", "is_active", "is_staff")
    list_filter = ("perfil__tipo", "perfil__escola", "is_active", "is_staff", "is_superuser", "groups")
    list_select_related = ("perfil__escola", "perfil__turma")

    @admin.display(description="Tipo", ordering="perfil__tipo")
    def tipo(self, obj):
        perfil = getattr(obj, "perfil", None)
        return perfil.get_tipo_display() if perfil else "—"

    @admin.display(description="Escola", ordering="perfil__escola__nome")
    def escola(self, obj):
        perfil = getattr(obj, "perfil", None)
        return perfil.escola if perfil and perfil.escola else "—"

    @admin.display(description="Turma", ordering="perfil__turma__nome")
    def turma(self, obj):
        perfil = getattr(obj, "perfil", None)
        return perfil.turma.nome if perfil and perfil.turma else "—"

    def get_inline_instances(self, request, obj=None):
        # Na tela "Adicionar usuário" o Perfil ainda não aparece: ele é
        # criado pelo sinal de contas/signals.py ao salvar, e o inline aqui
        # tentaria criar um segundo. O tipo vem do campo "Tipo" do
        # NovoUsuarioAdminForm (gravado em save_model); depois de salvar,
        # o Admin abre a tela de edição, onde o tipo pode ser ajustado.
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change and "tipo" in form.cleaned_data:
            obj.perfil.tipo = form.cleaned_data["tipo"]
            obj.perfil.escola = form.cleaned_data.get("escola")
            obj.perfil.turma = form.cleaned_data.get("turma")
            obj.perfil.save()
            if not form.cleaned_data.get("set_usable_password", True):
                if not enviar_link_criar_senha(request, obj):
                    self.message_user(request, AVISO_EMAIL_FALHOU.format(emails=obj.email), messages.WARNING)

    def save_related(self, request, form, formsets, change):
        # O campo "Grupos" (só do superusuário) é salvo antes do Perfil e
        # poderia tirar a conta do grupo do papel: o tipo manda (contas/papeis.py).
        super().save_related(request, form, formsets, change)
        perfil = Perfil.objects.filter(user=form.instance).first()
        if perfil:
            sincronizar_grupo_do_papel(form.instance, perfil.tipo)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is None or request.user.is_superuser:
            return fieldsets
        # Equipe administrativa: da seção "Permissões" fica só "Ativo"
        # (para bloquear o acesso de alguém sem apagar a conta).
        return tuple(
            (nome, {**opcoes, "fields": ("is_active",)})
            if "is_superuser" in opcoes.get("fields", ())
            else (nome, opcoes)
            for nome, opcoes in fieldsets
        )

    def _conta_de_staff_protegida(self, request, obj):
        return obj is not None and not request.user.is_superuser and obj.is_staff

    def get_readonly_fields(self, request, obj=None):
        # Conta de staff (ex.: colegas da equipe): quem não é superusuário
        # só pode ajustar o tipo, no Perfil (inline) — os dados da conta
        # ficam só para leitura (pedido do Eloi em 29/10/2026).
        if self._conta_de_staff_protegida(request, obj):
            return [campo for _, opcoes in self.get_fieldsets(request, obj) for campo in opcoes["fields"]]
        return super().get_readonly_fields(request, obj)

    def has_change_permission(self, request, obj=None):
        # Contas de superusuário ficam só com o superusuário — nem o tipo
        # a equipe altera nelas.
        if obj is not None and not request.user.is_superuser and obj.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def user_change_password(self, request, id, form_url=""):
        # A troca de senha de contas de staff fica só com o superusuário
        # (o Django só checaria has_change_permission, que agora libera
        # contas de staff para ajustar o tipo).
        usuario = self.get_object(request, unquote(id))
        if self._conta_de_staff_protegida(request, usuario):
            raise PermissionDenied
        return super().user_change_password(request, id, form_url)


admin.site.unregister(User)
admin.site.register(User, UsuarioAdmin)


@admin.register(SolicitacaoAcesso)
class SolicitacaoAcessoAdmin(admin.ModelAdmin):
    """
    Pedidos do formulário público "Solicitar acesso" (ver contas/views.py).
    Os dados do pedido não são editáveis: a equipe só aprova (cria a conta
    e manda o link de criar senha) ou recusa, pelas ações da lista.
    Os alunos listados no pedido são cadastrados à mão, em Usuários.
    """

    list_display = ("nome", "email", "tipo", "escola_turma", "status", "criada_em")
    list_filter = ("status", "tipo")
    search_fields = ("nome", "email", "escola_turma")
    readonly_fields = (
        "nome", "email", "tipo", "escola_turma", "alunos", "mensagem",
        "status", "criada_em", "analisada_em", "analisada_por", "usuario",
    )
    actions = ("aprovar_e_criar_conta", "recusar")

    def has_add_permission(self, request):
        return False  # pedidos só chegam pelo site

    def _marcar(self, request, solicitacao, status, usuario=None):
        solicitacao.status = status
        solicitacao.analisada_em = timezone.now()
        solicitacao.analisada_por = request.user
        solicitacao.usuario = usuario
        solicitacao.save()

    @admin.action(description="Aprovar e criar conta (envia o link de criar senha)", permissions=["change"])
    def aprovar_e_criar_conta(self, request, queryset):
        if not request.user.has_perm("auth.add_user"):
            self.message_user(request, "Você não tem permissão para criar contas.", messages.ERROR)
            return
        criadas, ja_existiam, sem_email = [], [], []
        for solicitacao in queryset.filter(status=SolicitacaoAcesso.PENDENTE):
            existente = User.objects.filter(username__iexact=solicitacao.email).first()
            if existente:
                # Não mexe na conta que já existe (nem no tipo): só registra.
                self._marcar(request, solicitacao, SolicitacaoAcesso.APROVADA, existente)
                ja_existiam.append(solicitacao.email)
                continue
            with transaction.atomic():
                usuario = User.objects.create_user(
                    username=solicitacao.email, email=solicitacao.email, first_name=solicitacao.nome
                )
                usuario.perfil.tipo = solicitacao.tipo
                usuario.perfil.save()
                self._marcar(request, solicitacao, SolicitacaoAcesso.APROVADA, usuario)
            if enviar_link_criar_senha(request, usuario):
                criadas.append(solicitacao.email)
            else:
                sem_email.append(solicitacao.email)
        if criadas:
            self.message_user(request, f"Contas criadas e link de senha enviado: {', '.join(criadas)}.")
        if sem_email:
            self.message_user(request, AVISO_EMAIL_FALHOU.format(emails=", ".join(sem_email)), messages.WARNING)
        if ja_existiam:
            self.message_user(
                request,
                f"Já havia conta com este e-mail (nada foi alterado): {', '.join(ja_existiam)}.",
                messages.WARNING,
            )
        if not criadas and not ja_existiam and not sem_email:
            self.message_user(request, "Nenhum pedido pendente selecionado.", messages.WARNING)

    @admin.action(description="Recusar", permissions=["change"])
    def recusar(self, request, queryset):
        total = 0
        for solicitacao in queryset.filter(status=SolicitacaoAcesso.PENDENTE):
            self._marcar(request, solicitacao, SolicitacaoAcesso.RECUSADA)
            total += 1
        self.message_user(request, f"{total} pedido(s) recusado(s).")


# --------------------------------------------------------------------
# Multiescola (etapa 1, 09/11/2026): escolas, turmas e consentimentos
# (LGPD), geridos pela equipe da plataforma — superusuário e grupo
# "Equipe administrativa" (permissões na migração 0009), que veem todas
# as escolas, com filtro por escola. O admin da escola e o professor não
# usam o Django Admin: as telas deles são da etapa 2.
# --------------------------------------------------------------------


class SituacaoContratoFilter(admin.SimpleListFilter):
    title = "situação do acesso"
    parameter_name = "situacao"

    def lookups(self, request, model_admin):
        return [
            ("liberada", "Liberada"),
            ("vence_30", "Vence em até 30 dias"),
            ("bloqueada", "Bloqueada (vencida ou desativada)"),
        ]

    def queryset(self, request, queryset):
        hoje = timezone.localdate()
        liberadas = Escola.objects.liberadas(hoje)
        if self.value() == "liberada":
            return queryset.filter(pk__in=liberadas)
        if self.value() == "vence_30":
            return queryset.filter(
                pk__in=liberadas, contrato_fim__lte=hoje + timedelta(days=30)
            )
        if self.value() == "bloqueada":
            return queryset.exclude(pk__in=liberadas)
        return queryset


class TurmaInline(admin.TabularInline):
    model = Turma
    extra = 0
    fields = ("nome", "ano_letivo", "professor", "ativa")
    show_change_link = True

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Só os professores desta escola na lista.
        if db_field.name == "professor":
            escola_id = request.resolver_match.kwargs.get("object_id")
            kwargs["queryset"] = Perfil.objects.filter(tipo=Perfil.PROFESSOR, escola_id=escola_id or None)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Escola)
class EscolaAdmin(admin.ModelAdmin):
    list_display = ("nome", "situacao", "contrato_fim", "professores", "turmas_ativas")
    list_filter = (SituacaoContratoFilter, "ativa")
    search_fields = ("nome", "cnpj", "email_contato")
    fieldsets = (
        (None, {"fields": ("nome", "cnpj", "email_contato", "telefone")}),
        ("Contrato", {"fields": ("ativa", "contrato_inicio", "contrato_fim", "limite_professores")}),
        (None, {"fields": ("observacoes",)}),
    )
    inlines = (TurmaInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _professores=Count(
                "perfis", filter=Q(perfis__tipo=Perfil.PROFESSOR, perfis__user__is_active=True), distinct=True
            ),
            _turmas=Count("turmas", filter=Q(turmas__ativa=True), distinct=True),
        )

    @admin.display(description="Acesso")
    def situacao(self, obj):
        if obj.esta_liberada():
            return "Liberado"
        return "Bloqueado"

    @admin.display(description="Professores ativos / limite", ordering="_professores")
    def professores(self, obj):
        return f"{obj._professores} / {obj.limite_professores}"

    @admin.display(description="Turmas ativas", ordering="_turmas")
    def turmas_ativas(self, obj):
        return obj._turmas


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ("nome", "escola", "ano_letivo", "professor", "alunos", "ativa")
    list_filter = ("escola", "ano_letivo", "ativa")
    search_fields = ("nome", "escola__nome")
    list_select_related = ("escola", "professor__user")
    autocomplete_fields = ("escola",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _alunos=Count("alunos", filter=Q(alunos__tipo=Perfil.ALUNO, alunos__user__is_active=True))
        )

    @admin.display(description=f"Alunos ativos (máx. {LIMITE_ALUNOS_POR_TURMA})", ordering="_alunos")
    def alunos(self, obj):
        return obj._alunos

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "professor":
            kwargs["queryset"] = Perfil.objects.filter(tipo=Perfil.PROFESSOR, escola__isnull=False).select_related(
                "user", "escola"
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    """
    Não aparece no menu do Admin (o Perfil é editado dentro de Usuários):
    existe só para a busca de aluno na tela de consentimento.
    """

    search_fields = ("user__first_name", "user__last_name", "user__username", "user__email")

    def get_model_perms(self, request):
        return {}

    def get_search_results(self, request, queryset, search_term):
        queryset, duplicadas = super().get_search_results(request, queryset, search_term)
        if request.GET.get("model_name") == "consentimentoresponsavel":
            queryset = queryset.filter(tipo=Perfil.ALUNO)
        return queryset, duplicadas


@admin.register(ConsentimentoResponsavel)
class ConsentimentoResponsavelAdmin(admin.ModelAdmin):
    list_display = ("aluno", "escola", "nome_responsavel", "parentesco", "versao_termo", "data_consentimento", "vigente")
    list_filter = ("aluno__escola", "versao_termo", "meio", ("revogado_em", admin.EmptyFieldListFilter))
    search_fields = ("aluno__user__first_name", "aluno__user__username", "nome_responsavel", "email_responsavel")
    list_select_related = ("aluno__user", "aluno__escola")
    autocomplete_fields = ("aluno",)
    readonly_fields = ("registrado_por",)

    @admin.display(description="Escola", ordering="aluno__escola__nome")
    def escola(self, obj):
        return obj.aluno.escola or "—"

    @admin.display(description="Vigente", boolean=True)
    def vigente(self, obj):
        return obj.vigente

    def save_model(self, request, obj, form, change):
        if not change:
            obj.registrado_por = request.user
        super().save_model(request, obj, form, change)
