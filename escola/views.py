"""
Área da escola (multiescola, etapa 2 — 09/11/2026): telas no próprio site,
fora do Django Admin (que fica só para a equipe da plataforma).

- Admin da escola: cadastra, edita, desativa e reativa os professores da
  escola, dentro do limite do plano; cria e edita as turmas e designa o
  professor de cada uma (revisão de 09/11/2026). Desde 13/11/2026 também
  cuida dos alunos de todas as turmas da escola: cadastra (um a um ou em
  lote), gera login e senha simples, imprime os cartões de acesso com a
  senha, gera senha nova, edita, move entre turmas, desativa e registra o
  termo do responsável. Não vê desempenho (quiz, relatórios, atividade
  complementar): isso é só do professor.
- Professor: vê só as turmas em que foi designado e a lista de alunos
  delas (com a situação do termo, só leitura), imprime os cartões só com o
  usuário (sem senha) e cuida do desempenho: relatórios da turma e do
  aluno e lançamento da atividade complementar.

Todo registro é buscado pelo escopo da conta logada (contas/escopo.py):
id de outra escola, ou de turma de outro professor, dá 404. Sem a
permissão do papel (grupos de contas/papeis.py), 403.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from contas.emails import enviar_link_criar_senha
from contas.escopo import alunos_visiveis, do_escopo_ou_404, professores_visiveis, turmas_visiveis
from contas.models import LIMITE_ALUNOS_POR_TURMA, Perfil, Turma

from . import relatorios
from .acessos import gerar_login, gerar_senha
from .forms import (
    AlunoForm, AlunosEmLoteForm, ConsentimentoForm, EditarAlunoForm, LinhaEntregaForm, ProfessorForm, TurmaForm,
)
from .models import EntregaAtividade

# Cartões com as senhas recém-geradas ficam na sessão de quem gerou (o
# Admin da escola) até a próxima geração: a senha não pode ser lida de
# volta do banco. Sem cartões na sessão — e sempre para o professor —, a
# tela de cartões imprime o usuário de cada aluno ativo com a senha em
# branco, para preencher à mão (decisão de 13/11/2026).
CHAVE_CARTOES = "escola_cartoes"


def area_da_escola(permissao):
    """
    Só para contas ligadas a uma escola e com a permissão do papel. A
    equipe da plataforma usa o Django Admin (não tem escola no perfil).
    O bloqueio por contrato vencido já é feito pelo EscolaLiberadaMiddleware.
    """

    def decorador(view):
        @wraps(view)
        def envolvida(request, *args, **kwargs):
            perfil = getattr(request.user, "perfil", None)
            if perfil is None or perfil.escola_id is None or not request.user.has_perm(permissao):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return envolvida

    return decorador


def _escola(request):
    return request.user.perfil.escola


def inicio(request):
    """/escola/: leva cada papel para a sua tela principal."""
    perfil = getattr(request.user, "perfil", None)
    if perfil and perfil.escola_id:
        if perfil.tipo == Perfil.ADMIN_ESCOLA:
            return redirect("escola:professores")
        if perfil.tipo == Perfil.PROFESSOR:
            return redirect("escola:turmas")
    raise PermissionDenied


# --------------------------------------------------------------------
# Admin da escola: professores
# --------------------------------------------------------------------


@area_da_escola("contas.cadastrar_professores")
def professores(request):
    escola = _escola(request)
    lista = professores_visiveis(request.user).select_related("user").order_by("-user__is_active", "user__first_name")
    return render(request, "escola/professores.html", {
        "escola": escola,
        "professores": lista,
        "ativos": escola.professores_ativos().count(),
    })


@area_da_escola("contas.cadastrar_professores")
def professor_novo(request):
    escola = _escola(request)
    form = ProfessorForm(request.POST or None, escola=escola)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            usuario = User.objects.create_user(
                username=form.cleaned_data["email"], email=form.cleaned_data["email"],
                first_name=form.cleaned_data["nome"],
            )
            perfil = usuario.perfil
            perfil.tipo, perfil.escola = Perfil.PROFESSOR, escola
            perfil.save()
        if enviar_link_criar_senha(request, usuario):
            messages.success(request, f"Professor(a) cadastrado(a). O link para criar a senha foi enviado para {usuario.email}.")
        else:
            messages.warning(
                request,
                f"Professor(a) cadastrado(a), mas o e-mail para {usuario.email} não pôde ser enviado. "
                "Quando o e-mail voltar a funcionar, a pessoa pode usar \"Esqueceu a senha?\" na tela de entrar.",
            )
        return redirect("escola:professores")
    return render(request, "escola/professor_form.html", {"form": form, "escola": escola})


@area_da_escola("contas.cadastrar_professores")
def professor_editar(request, pk):
    perfil = do_escopo_ou_404("professores", request.user, pk=pk)
    usuario = perfil.user
    form = ProfessorForm(request.POST or None, escola=perfil.escola, professor=usuario)
    if request.method == "POST" and form.is_valid():
        usuario.first_name = form.cleaned_data["nome"]
        usuario.email = usuario.username = form.cleaned_data["email"]
        usuario.save(update_fields=["first_name", "email", "username"])
        messages.success(request, "Dados do professor(a) salvos.")
        return redirect("escola:professores")
    return render(request, "escola/professor_form.html", {"form": form, "escola": perfil.escola, "professor": perfil})


@require_POST
@area_da_escola("contas.cadastrar_professores")
def professor_ativo(request, pk):
    """Desativa (não apaga: as turmas e o histórico ficam) ou reativa, dentro do limite."""
    perfil = do_escopo_ou_404("professores", request.user, pk=pk)
    usuario = perfil.user
    if usuario.is_active:
        usuario.is_active = False
        usuario.save(update_fields=["is_active"])
        messages.success(request, f"{usuario.first_name} foi desativado(a) e não consegue mais entrar.")
    else:
        usuario.is_active = True
        try:
            perfil.clean()
        except ValidationError as erro:
            messages.error(request, " ".join(erro.messages))
        else:
            usuario.save(update_fields=["is_active"])
            messages.success(request, f"{usuario.first_name} foi reativado(a).")
    return redirect("escola:professores")


# --------------------------------------------------------------------
# Turmas: lista e tela da turma para os dois papéis (o professor, só as
# dele); criar/editar e designar o professor só o Admin da escola
# (revisão de 09/11/2026), que também cuida dos alunos (13/11/2026).
# --------------------------------------------------------------------


@area_da_escola("contas.view_turma")
def turmas(request):
    lista = turmas_visiveis(request.user).select_related("professor__user").order_by("-ativa", "-ano_letivo", "nome")
    return render(request, "escola/turmas.html", {
        "escola": _escola(request),
        "turmas": lista,
        "eh_professor": request.user.perfil.tipo == Perfil.PROFESSOR,
        "pode_editar": request.user.has_perm("contas.change_turma"),
        "limite": LIMITE_ALUNOS_POR_TURMA,
    })


@area_da_escola("contas.add_turma")
def turma_nova(request):
    escola = _escola(request)
    form = TurmaForm(request.POST or None, escola=escola)
    if request.method == "POST" and form.is_valid():
        turma = form.save()
        if turma.professor_id:
            messages.success(
                request, f"Turma {turma.nome} criada, com {turma.professor.user.first_name}. Abra a turma para cadastrar os alunos."
            )
        else:
            messages.success(request, f"Turma {turma.nome} criada. Falta designar o professor(a).")
        return redirect("escola:turmas")
    return render(request, "escola/turma_form.html", {"form": form})


@area_da_escola("contas.change_turma")
def turma_editar(request, pk):
    turma = do_escopo_ou_404("turmas", request.user, pk=pk)
    form = TurmaForm(request.POST or None, instance=turma, escola=turma.escola)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Turma salva.")
        return redirect("escola:turmas")
    return render(request, "escola/turma_form.html", {"form": form, "turma": turma})


def _turma_do_professor(request, pk):
    """Só turma em que a conta é o professor designado (desempenho: nunca o admin da escola)."""
    return do_escopo_ou_404("turmas", request.user, pk=pk, professor=request.user.perfil)


def _turma_da_escola(request, pk):
    """Turma do escopo: qualquer uma da escola para o admin; só as próprias para o professor."""
    return do_escopo_ou_404("turmas", request.user, pk=pk)


@area_da_escola("contas.view_turma")
def turma(request, pk):
    turma = _turma_da_escola(request, pk)
    alunos = (
        alunos_visiveis(request.user).filter(turma=turma).select_related("user")
        .prefetch_related("consentimentos").order_by("-user__is_active", "user__first_name")
    )
    return render(request, "escola/turma.html", {
        "turma": turma,
        "alunos": alunos,
        "ativos": turma.alunos_ativos().count(),
        "limite": LIMITE_ALUNOS_POR_TURMA,
        "tem_cartoes": any(c["turma"] == turma.pk for c in request.session.get(CHAVE_CARTOES, [])),
        "eh_professor": request.user.perfil.tipo == Perfil.PROFESSOR,
    })


# --------------------------------------------------------------------
# Alunos: cadastro e acesso pelo Admin da escola (13/11/2026)
# --------------------------------------------------------------------


def _criar_aluno(turma, nome):
    """Cria a conta do aluno (sem e-mail) e devolve os dados do cartão."""
    senha = gerar_senha()
    usuario = User(username=gerar_login(nome, turma), first_name=nome)
    usuario.set_password(senha)
    usuario.save()
    perfil = usuario.perfil
    perfil.tipo, perfil.escola, perfil.turma = Perfil.ALUNO, turma.escola, turma
    perfil.full_clean(exclude=["user"])  # limite de 30 por turma
    perfil.save()
    return _cartao(perfil, senha)


def _cartao(perfil, senha):
    return {"turma": perfil.turma_id, "nome": perfil.user.first_name, "login": perfil.user.username, "senha": senha}


def _guardar_cartoes(request, cartoes):
    request.session[CHAVE_CARTOES] = cartoes


@area_da_escola("contas.cadastrar_alunos")
def aluno_novo(request, pk):
    turma = _turma_da_escola(request, pk)
    form = AlunoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                cartao = _criar_aluno(turma, form.cleaned_data["nome"])
        except ValidationError as erro:
            form.add_error(None, " ".join(erro.messages))
        else:
            _guardar_cartoes(request, [cartao])
            messages.success(request, f"{cartao['nome']} cadastrado(a). Imprima o cartão de acesso.")
            return redirect("escola:cartoes", pk=turma.pk)
    return render(request, "escola/aluno_form.html", {"form": form, "turma": turma})


@area_da_escola("contas.cadastrar_alunos")
def alunos_em_lote(request, pk):
    turma = _turma_da_escola(request, pk)
    form = AlunosEmLoteForm(request.POST or None, turma=turma)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                cartoes = [_criar_aluno(turma, nome) for nome in form.cleaned_data["nomes"]]
        except ValidationError as erro:
            form.add_error(None, " ".join(erro.messages))
        else:
            _guardar_cartoes(request, cartoes)
            messages.success(request, f"{len(cartoes)} alunos cadastrados. Imprima os cartões de acesso.")
            return redirect("escola:cartoes", pk=turma.pk)
    return render(request, "escola/alunos_lote.html", {"form": form, "turma": turma})


@area_da_escola("contas.view_turma")
def cartoes(request, pk):
    """
    Cartões de acesso. Logo depois de gerar senhas (só o Admin da escola),
    com a senha; fora isso — e sempre para o professor —, com o usuário de
    cada aluno ativo e a senha em branco.
    """
    turma = _turma_da_escola(request, pk)
    pode_gerar_senha = request.user.has_perm("contas.cadastrar_alunos")
    com_senha = []
    if pode_gerar_senha:
        com_senha = [c for c in request.session.get(CHAVE_CARTOES, []) if c["turma"] == turma.pk]
    lista = com_senha or [
        _cartao(perfil, None)
        for perfil in alunos_visiveis(request.user).filter(turma=turma, user__is_active=True)
        .select_related("user").order_by("user__first_name")
    ]
    return render(request, "escola/cartoes.html", {
        "turma": turma,
        "cartoes": lista,
        "com_senha": bool(com_senha),
        "pode_gerar_senha": pode_gerar_senha,
        "endereco": request.build_absolute_uri("/"),
    })


@require_POST
@area_da_escola("contas.cadastrar_alunos")
def novas_senhas_turma(request, pk):
    """Senha nova para todos os alunos ativos da turma (para reimprimir os cartões)."""
    turma = _turma_da_escola(request, pk)
    cartoes_novos = []
    with transaction.atomic():
        for perfil in turma.alunos_ativos().select_related("user").order_by("user__first_name"):
            senha = gerar_senha()
            perfil.user.set_password(senha)
            perfil.user.save(update_fields=["password"])
            cartoes_novos.append(_cartao(perfil, senha))
    _guardar_cartoes(request, cartoes_novos)
    messages.success(request, "Senhas novas geradas para a turma. As senhas antigas não valem mais.")
    return redirect("escola:cartoes", pk=turma.pk)


def _aluno_da_escola(request, pk):
    """Aluno do escopo da conta (o admin da escola: qualquer um da escola)."""
    return do_escopo_ou_404("alunos", request.user, pk=pk)


def _aluno_do_professor(request, pk):
    """Só aluno de turma em que a conta é o professor designado (desempenho)."""
    return do_escopo_ou_404("alunos", request.user, pk=pk, turma__professor=request.user.perfil)


@require_POST
@area_da_escola("contas.cadastrar_alunos")
def aluno_nova_senha(request, pk):
    perfil = _aluno_da_escola(request, pk)
    senha = gerar_senha()
    perfil.user.set_password(senha)
    perfil.user.save(update_fields=["password"])
    _guardar_cartoes(request, [_cartao(perfil, senha)])
    messages.success(request, f"Senha nova de {perfil.user.first_name} gerada. A senha antiga não vale mais.")
    return redirect("escola:cartoes", pk=perfil.turma_id)


@area_da_escola("contas.cadastrar_alunos")
def aluno_editar(request, pk):
    perfil = _aluno_da_escola(request, pk)
    turma_atual = perfil.turma
    form = EditarAlunoForm(request.POST or None, aluno=perfil, turmas=turmas_visiveis(request.user).filter(ativa=True))
    if request.method == "POST" and form.is_valid():
        perfil.user.first_name = form.cleaned_data["nome"]
        perfil.user.save(update_fields=["first_name"])
        perfil.turma = form.cleaned_data["turma"]
        perfil.save(update_fields=["turma"])  # o histórico do quiz vai junto (fica no perfil)
        messages.success(request, f"Dados de {perfil.user.first_name} salvos.")
        return redirect("escola:turma", pk=turma_atual.pk)
    return render(request, "escola/aluno_editar.html", {"form": form, "aluno": perfil, "turma": turma_atual})


@require_POST
@area_da_escola("contas.cadastrar_alunos")
def aluno_ativo(request, pk):
    """Desativa (o aluno saiu da turma; o histórico fica) ou reativa, dentro do limite de 30."""
    perfil = _aluno_da_escola(request, pk)
    usuario = perfil.user
    if usuario.is_active:
        usuario.is_active = False
        usuario.save(update_fields=["is_active"])
        messages.success(request, f"{usuario.first_name} foi desativado(a).")
    else:
        usuario.is_active = True
        try:
            perfil.clean()
        except ValidationError as erro:
            messages.error(request, " ".join(erro.messages))
        else:
            usuario.save(update_fields=["is_active"])
            messages.success(request, f"{usuario.first_name} foi reativado(a).")
    return redirect("escola:turma", pk=perfil.turma_id)


@area_da_escola("contas.cadastrar_alunos")
def aluno_consentimento(request, pk):
    """Registro do termo de consentimento do responsável (LGPD), recolhido pela escola."""
    perfil = _aluno_da_escola(request, pk)
    form = ConsentimentoForm(request.POST or None, instance=None)
    if request.method == "POST" and form.is_valid():
        consentimento = form.save(commit=False)
        consentimento.aluno, consentimento.registrado_por = perfil, request.user
        consentimento.save()
        messages.success(request, f"Consentimento do responsável de {perfil.user.first_name} registrado.")
        return redirect("escola:turma", pk=perfil.turma_id)
    return render(request, "escola/consentimento_form.html", {
        "form": form, "aluno": perfil, "consentimentos": perfil.consentimentos.all(),
    })


# --------------------------------------------------------------------
# Etapa 3 (09/11/2026): relatórios por turma e por aluno e lançamento da
# atividade complementar. Cálculos em relatorios.py. Exclusivo do
# professor, nas turmas designadas a ele (regra de 13/11/2026): a
# permissão ver_desempenho_turma é só do grupo Professor e, além dela, a
# turma ou o aluno é buscado só entre os do professor — o admin da escola
# recebe 403 (sem a permissão) e, se um dia a tiver por engano, 404.
# --------------------------------------------------------------------


def _obra_escolhida(request, obras):
    slug = request.GET.get("obra")
    if slug:
        return obras.filter(slug=slug).first()
    return None


@area_da_escola("contas.ver_desempenho_turma")
def turma_relatorio(request, pk):
    turma = _turma_do_professor(request, pk)
    alunos = turma.alunos_ativos().select_related("user").order_by("user__first_name")
    obras = relatorios.obras_do_relatorio()
    obra = _obra_escolhida(request, obras)
    contexto = {"turma": turma, "obras": obras, "obra": obra, "total_alunos": alunos.count()}
    if obra:
        contexto["detalhe"] = relatorios.detalhe_da_obra(alunos, obra)
    else:
        contexto["resumo"] = relatorios.resumo_da_turma(alunos)
    return render(request, "escola/turma_relatorio.html", contexto)


@area_da_escola("contas.ver_desempenho_turma")
def aluno_relatorio(request, pk):
    aluno = _aluno_do_professor(request, pk)
    return render(request, "escola/aluno_relatorio.html", {
        "aluno": aluno, "turma": aluno.turma, **relatorios.historico_do_aluno(aluno),
    })


@area_da_escola("contas.ver_desempenho_turma")
def atividades_lancar(request, pk):
    """
    Lançamento da atividade complementar de uma obra para a turma toda, numa
    tela só: situação (entregou / não entregou), nota opcional e observação
    por aluno. Situação em branco apaga o lançamento que existia.
    """
    turma = _turma_do_professor(request, pk)
    obras = relatorios.obras_do_relatorio()
    obra = _obra_escolhida(request, obras)
    if obra is None:
        return render(request, "escola/atividades_escolher.html", {"turma": turma, "obras": obras})

    alunos = list(turma.alunos_ativos().select_related("user").order_by("user__first_name"))
    existentes = {e.aluno_id: e for e in EntregaAtividade.objects.filter(aluno__in=alunos, obra=obra)}

    def inicial(aluno):
        entrega = existentes.get(aluno.pk)
        if not entrega:
            return {}
        return {"situacao": entrega.situacao, "nota": entrega.nota, "observacao": entrega.observacao}

    dados = request.POST if request.method == "POST" else None
    linhas = [LinhaEntregaForm(dados, aluno=a, initial=inicial(a)) for a in alunos]
    if request.method == "POST" and all(f.is_valid() for f in linhas):
        with transaction.atomic():
            for form in linhas:
                entrega = existentes.get(form.aluno.pk)
                situacao = form.cleaned_data["situacao"]
                if not situacao:
                    if entrega:
                        entrega.delete()
                    continue
                if entrega is None:
                    entrega = EntregaAtividade(aluno=form.aluno, obra=obra, turma=turma)
                if not form.has_changed() and entrega.pk:
                    continue
                entrega.situacao = situacao
                entrega.nota = form.cleaned_data["nota"]
                entrega.observacao = form.cleaned_data["observacao"]
                entrega.registrado_por = request.user
                entrega.save()
        messages.success(request, f"Atividade complementar de \"{obra.titulo}\" salva.")
        return redirect(f"{reverse('escola:turma_relatorio', args=[turma.pk])}?obra={obra.slug}")
    return render(request, "escola/atividades_lancar.html", {"turma": turma, "obra": obra, "linhas": linhas})
