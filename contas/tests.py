import importlib
import re
from io import StringIO
from unittest import mock

from django.apps import apps
from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from .models import Perfil, SolicitacaoAcesso
from .views import ip_do_visitante

# O nome do arquivo de migração começa com número, então não dá para usar
# "from .migrations.0004_... import ...".
migracao_0004 = importlib.import_module("contas.migrations.0004_criar_perfis_faltantes")


class PerfilAutomaticoTests(TestCase):
    """Todo User ganha um Perfil, venha de onde vier (ver contas/signals.py)."""

    def test_create_user_cria_perfil_outro(self):
        usuario = User.objects.create_user("alguem@exemplo.com", password="senha-teste-123")
        self.assertEqual(usuario.perfil.tipo, Perfil.OUTRO)

    def test_createsuperuser_cria_perfil(self):
        call_command(
            "createsuperuser",
            username="admin@exemplo.com",
            email="admin@exemplo.com",
            interactive=False,
            stdout=StringIO(),
        )
        usuario = User.objects.get(username="admin@exemplo.com")
        self.assertTrue(Perfil.objects.filter(user=usuario).exists())

    def test_salvar_usuario_existente_nao_duplica_perfil(self):
        usuario = User.objects.create_user("alguem@exemplo.com", password="senha-teste-123")
        usuario.first_name = "Novo nome"
        usuario.save()
        self.assertEqual(Perfil.objects.filter(user=usuario).count(), 1)


class SemAutocadastroTests(TestCase):
    """O autocadastro público foi removido em 29/10/2026."""

    def test_rota_de_cadastro_nao_existe(self):
        with self.assertRaises(NoReverseMatch):
            reverse("contas:cadastro")
        self.assertEqual(self.client.get("/contas/cadastro/").status_code, 404)

    def test_login_nao_oferece_cadastro(self):
        resposta = self.client.get(reverse("contas:login"))
        self.assertNotContains(resposta, "Cadastre-se")
        self.assertContains(resposta, reverse("contas:solicitar_acesso"))


DADOS_NOVO_USUARIO = {
    "first_name": "Professora Ana",
    "email": "Ana@Exemplo.com",
    "tipo": Perfil.PROFESSOR,
    "usable_password": "true",
    "password1": "senha-forte-987",
    "password2": "senha-forte-987",
}


class AdminUsuarioTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", password="senha-teste-123")
        self.client.force_login(self.admin)

    def test_adicionar_usuario_grava_email_como_login_e_tipo(self):
        resposta = self.client.post(reverse("admin:auth_user_add"), DADOS_NOVO_USUARIO)
        self.assertEqual(resposta.status_code, 302)
        usuario = User.objects.get(username="ana@exemplo.com")
        self.assertEqual(usuario.email, "ana@exemplo.com")
        self.assertEqual(usuario.first_name, "Professora Ana")
        self.assertTrue(usuario.check_password("senha-forte-987"))
        self.assertEqual(Perfil.objects.filter(user=usuario).count(), 1)
        self.assertEqual(usuario.perfil.tipo, Perfil.PROFESSOR)

    def test_tipo_padrao_e_aluno(self):
        resposta = self.client.get(reverse("admin:auth_user_add"))
        self.assertContains(resposta, '<option value="aluno" selected>')

    def test_email_repetido_e_recusado(self):
        User.objects.create_user("ana@exemplo.com", password="senha-teste-123")
        resposta = self.client.post(reverse("admin:auth_user_add"), DADOS_NOVO_USUARIO)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Já existe uma conta cadastrada com este e-mail.")

    def test_tela_de_edicao_mostra_o_perfil(self):
        resposta = self.client.get(reverse("admin:auth_user_change", args=[self.admin.pk]))
        self.assertContains(resposta, "perfil-0-tipo")


class EquipeAdministrativaTests(TestCase):
    """Grupo da migração 0005: cria contas sem conseguir ampliar acessos."""

    def setUp(self):
        self.equipe = User.objects.create_user("equipe@exemplo.com", password="senha-teste-123", is_staff=True)
        self.equipe.groups.add(Group.objects.get(name="Equipe administrativa"))
        self.client.force_login(self.equipe)
        self.aluno = User.objects.create_user("aluno@exemplo.com", password="senha-teste-123")

    def test_cria_conta_com_tipo(self):
        resposta = self.client.post(reverse("admin:auth_user_add"), DADOS_NOVO_USUARIO)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(User.objects.get(username="ana@exemplo.com").perfil.tipo, Perfil.PROFESSOR)

    def test_edicao_nao_mostra_campos_de_permissao(self):
        resposta = self.client.get(reverse("admin:auth_user_change", args=[self.aluno.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'name="is_active"')
        self.assertContains(resposta, "perfil-0-tipo")
        for campo in ("is_staff", "is_superuser", "groups", "user_permissions"):
            self.assertNotContains(resposta, f'name="{campo}"')

    def test_nao_consegue_se_tornar_staff_pelo_post(self):
        url = reverse("admin:auth_user_change", args=[self.aluno.pk])
        dados = {
            "username": "aluno@exemplo.com",
            "is_active": "on",
            "is_staff": "on",
            "is_superuser": "on",
            "date_joined_0": "2026-10-29",
            "date_joined_1": "10:00:00",
            "perfil-TOTAL_FORMS": "1",
            "perfil-INITIAL_FORMS": "1",
            "perfil-MIN_NUM_FORMS": "0",
            "perfil-MAX_NUM_FORMS": "1",
            "perfil-0-id": self.aluno.perfil.pk,
            "perfil-0-user": self.aluno.pk,
            "perfil-0-tipo": Perfil.PROFESSOR,
        }
        resposta = self.client.post(url, dados)
        self.assertEqual(resposta.status_code, 302)
        self.aluno.refresh_from_db()
        self.assertFalse(self.aluno.is_staff)
        self.assertFalse(self.aluno.is_superuser)
        self.assertEqual(self.aluno.perfil.tipo, Perfil.PROFESSOR)

    def test_altera_so_o_tipo_de_conta_de_staff(self):
        colega = User.objects.create_user("colega@exemplo.com", password="senha-teste-123", is_staff=True)
        url = reverse("admin:auth_user_change", args=[colega.pk])
        resposta = self.client.get(url)
        self.assertContains(resposta, 'name="perfil-0-tipo"')
        self.assertNotContains(resposta, 'name="username"')
        dados = {
            "username": "invasor",
            "perfil-TOTAL_FORMS": "1",
            "perfil-INITIAL_FORMS": "1",
            "perfil-MIN_NUM_FORMS": "0",
            "perfil-MAX_NUM_FORMS": "1",
            "perfil-0-id": colega.perfil.pk,
            "perfil-0-user": colega.pk,
            "perfil-0-tipo": Perfil.PROFESSOR,
        }
        self.assertEqual(self.client.post(url, dados).status_code, 302)
        colega.refresh_from_db()
        self.assertEqual(colega.username, "colega@exemplo.com")
        self.assertEqual(colega.perfil.tipo, Perfil.PROFESSOR)

    def test_nao_troca_senha_de_conta_de_staff(self):
        colega = User.objects.create_user("colega@exemplo.com", password="senha-teste-123", is_staff=True)
        resposta = self.client.post(
            reverse("admin:auth_user_password_change", args=[colega.pk]),
            {"usable_password": "true", "password1": "senha-nova-987", "password2": "senha-nova-987"},
        )
        self.assertEqual(resposta.status_code, 403)
        colega.refresh_from_db()
        self.assertTrue(colega.check_password("senha-teste-123"))

    def test_nao_altera_conta_de_superusuario(self):
        admin = User.objects.create_superuser("admin", password="senha-teste-123")
        resposta = self.client.post(reverse("admin:auth_user_change", args=[admin.pk]), {"username": "outro"})
        self.assertEqual(resposta.status_code, 403)
        resposta = self.client.post(
            reverse("admin:auth_user_password_change", args=[admin.pk]),
            {"usable_password": "true", "password1": "senha-nova-987", "password2": "senha-nova-987"},
        )
        self.assertEqual(resposta.status_code, 403)
        admin.refresh_from_db()
        self.assertTrue(admin.check_password("senha-teste-123"))

    def test_cria_conta_mandando_link_de_senha(self):
        dados = {**DADOS_NOVO_USUARIO, "usable_password": "false", "password1": "", "password2": ""}
        resposta = self.client.post(reverse("admin:auth_user_add"), dados)
        self.assertEqual(resposta.status_code, 302)
        usuario = User.objects.get(username="ana@exemplo.com")
        # Senha aleatória (e utilizável), para o "Esqueceu a senha?" funcionar depois.
        self.assertTrue(usuario.has_usable_password())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@exemplo.com"])
        self.assertIn("/contas/senha/redefinir/", mail.outbox[0].body)

    def test_nao_exclui_usuarios(self):
        resposta = self.client.post(reverse("admin:auth_user_delete", args=[self.aluno.pk]), {"post": "yes"})
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.aluno.pk).exists())


class MigracaoPerfisFaltantesTests(TestCase):
    def test_cria_perfil_so_para_quem_nao_tem(self):
        sem_perfil = User.objects.create_user("antigo", password="senha-teste-123")
        sem_perfil.perfil.delete()
        com_perfil = User.objects.create_user("professora", password="senha-teste-123")
        com_perfil.perfil.tipo = Perfil.PROFESSOR
        com_perfil.perfil.save()

        migracao_0004.criar_perfis_faltantes(apps, None)

        self.assertEqual(Perfil.objects.get(user=sem_perfil).tipo, Perfil.OUTRO)
        self.assertEqual(Perfil.objects.get(user=com_perfil).tipo, Perfil.PROFESSOR)


DADOS_SOLICITACAO = {
    "nome": "Professora Bia",
    "email": "Bia@Escola.com",
    "tipo": Perfil.PROFESSOR,
    "escola_turma": "EMEF Sepé Tiaraju, 3º ano B",
    "alunos": "João - joao@escola.com",
    "mensagem": "",
    "site": "",
}


class SolicitarAcessoTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_pagina_abre_sem_login(self):
        resposta = self.client.get(reverse("contas:solicitar_acesso"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Enviar pedido")

    def test_pedido_e_gravado(self):
        resposta = self.client.post(reverse("contas:solicitar_acesso"), DADOS_SOLICITACAO)
        self.assertRedirects(resposta, reverse("contas:solicitar_acesso_enviado"))
        solicitacao = SolicitacaoAcesso.objects.get()
        self.assertEqual(solicitacao.email, "bia@escola.com")
        self.assertEqual(solicitacao.status, SolicitacaoAcesso.PENDENTE)
        self.assertFalse(User.objects.filter(username="bia@escola.com").exists())

    def test_tipo_aluno_nao_e_aceito(self):
        resposta = self.client.post(reverse("contas:solicitar_acesso"), {**DADOS_SOLICITACAO, "tipo": Perfil.ALUNO})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(SolicitacaoAcesso.objects.exists())

    def test_robo_nao_grava(self):
        resposta = self.client.post(reverse("contas:solicitar_acesso"), {**DADOS_SOLICITACAO, "site": "http://spam"})
        self.assertRedirects(resposta, reverse("contas:solicitar_acesso_enviado"))
        self.assertFalse(SolicitacaoAcesso.objects.exists())

    def test_limite_de_pedidos_por_ip(self):
        for _ in range(5):
            self.client.post(reverse("contas:solicitar_acesso"), DADOS_SOLICITACAO)
        resposta = self.client.post(reverse("contas:solicitar_acesso"), DADOS_SOLICITACAO)
        self.assertContains(resposta, "muitos pedidos")
        self.assertEqual(SolicitacaoAcesso.objects.count(), 5)

    @override_settings(EMAIL_EQUIPE_ADMINISTRATIVA="equipe@turma.com")
    def test_equipe_e_avisada(self):
        self.client.post(reverse("contas:solicitar_acesso"), {**DADOS_SOLICITACAO, "nome": "Bia\nCc: x@y.com"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["equipe@turma.com"])
        self.assertIn("João - joao@escola.com", mail.outbox[0].body)
        self.assertNotIn("\n", mail.outbox[0].subject)

    def test_sem_email_da_equipe_nao_avisa(self):
        self.client.post(reverse("contas:solicitar_acesso"), DADOS_SOLICITACAO)
        self.assertEqual(len(mail.outbox), 0)

    def test_logado_vai_para_home(self):
        self.client.force_login(User.objects.create_user("alguem@exemplo.com", password="senha-teste-123"))
        resposta = self.client.get(reverse("contas:solicitar_acesso"))
        self.assertRedirects(resposta, reverse("obras:home"), fetch_redirect_response=False)


class AnaliseSolicitacaoTests(TestCase):
    """Ações "Aprovar e criar conta" e "Recusar", pela Equipe administrativa."""

    def setUp(self):
        equipe = User.objects.create_user("equipe@exemplo.com", password="senha-teste-123", is_staff=True)
        equipe.groups.add(Group.objects.get(name="Equipe administrativa"))
        self.client.force_login(equipe)
        self.equipe = equipe
        self.solicitacao = SolicitacaoAcesso.objects.create(
            nome="Professora Bia", email="bia@escola.com", tipo=Perfil.PROFESSOR, escola_turma="EMEF, 3º B"
        )

    def _acao(self, acao):
        return self.client.post(
            reverse("admin:contas_solicitacaoacesso_changelist"),
            {"action": acao, "_selected_action": [self.solicitacao.pk]},
        )

    def test_lista_de_pedidos_abre(self):
        resposta = self.client.get(reverse("admin:contas_solicitacaoacesso_changelist"))
        self.assertContains(resposta, "Professora Bia")

    def test_aprovar_cria_conta_e_manda_link_que_funciona(self):
        self.assertEqual(self._acao("aprovar_e_criar_conta").status_code, 302)
        usuario = User.objects.get(username="bia@escola.com")
        self.assertEqual(usuario.perfil.tipo, Perfil.PROFESSOR)
        self.assertEqual(usuario.first_name, "Professora Bia")
        self.solicitacao.refresh_from_db()
        self.assertEqual(self.solicitacao.status, SolicitacaoAcesso.APROVADA)
        self.assertEqual(self.solicitacao.usuario, usuario)
        self.assertEqual(self.solicitacao.analisada_por, self.equipe)

        self.assertEqual(mail.outbox[0].to, ["bia@escola.com"])
        link = re.search(r"http://testserver(/contas/senha/redefinir/\S+)", mail.outbox[0].body).group(1)
        self.client.logout()
        resposta = self.client.get(link, follow=True)
        nova = {"new_password1": "minha-senha-forte-1", "new_password2": "minha-senha-forte-1"}
        self.client.post(resposta.redirect_chain[-1][0], nova)
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("minha-senha-forte-1"))

    def test_aprovar_com_conta_existente_nao_altera_a_conta(self):
        existente = User.objects.create_user("bia@escola.com", password="senha-teste-123")
        self._acao("aprovar_e_criar_conta")
        existente.refresh_from_db()
        self.assertEqual(existente.perfil.tipo, Perfil.OUTRO)
        self.assertTrue(existente.check_password("senha-teste-123"))
        self.solicitacao.refresh_from_db()
        self.assertEqual(self.solicitacao.usuario, existente)
        self.assertEqual(len(mail.outbox), 0)

    def test_recusar(self):
        self._acao("recusar")
        self.solicitacao.refresh_from_db()
        self.assertEqual(self.solicitacao.status, SolicitacaoAcesso.RECUSADA)
        self.assertFalse(User.objects.filter(username="bia@escola.com").exists())

    def test_pedido_ja_analisado_nao_e_aprovado_de_novo(self):
        self._acao("recusar")
        self._acao("aprovar_e_criar_conta")
        self.assertFalse(User.objects.filter(username="bia@escola.com").exists())


# --------------------------------------------------------------------
# Revisão de 07/11/2026 (antes da publicação)
# --------------------------------------------------------------------


class IpDoVisitanteTests(TestCase):
    """Atrás do Nginx, o IP real vem do X-Forwarded-For (item 3 da revisão)."""

    def _pedido(self, **meta):
        return RequestFactory().post("/", REMOTE_ADDR="127.0.0.1", **meta)

    @override_settings(PROXIES_CONFIAVEIS=0)
    def test_sem_proxy_usa_remote_addr(self):
        pedido = self._pedido(HTTP_X_FORWARDED_FOR="200.1.1.1")
        self.assertEqual(ip_do_visitante(pedido), "127.0.0.1")

    @override_settings(PROXIES_CONFIAVEIS=1)
    def test_com_nginx_usa_o_ip_que_o_nginx_acrescentou(self):
        # O começo da lista pode ser inventado pelo visitante; vale o último.
        pedido = self._pedido(HTTP_X_FORWARDED_FOR="1.2.3.4, 200.1.1.1")
        self.assertEqual(ip_do_visitante(pedido), "200.1.1.1")

    @override_settings(PROXIES_CONFIAVEIS=2)
    def test_com_cloudflare_e_nginx_usa_o_penultimo(self):
        pedido = self._pedido(HTTP_X_FORWARDED_FOR="1.2.3.4, 200.1.1.1, 172.68.0.1")
        self.assertEqual(ip_do_visitante(pedido), "200.1.1.1")

    @override_settings(PROXIES_CONFIAVEIS=1)
    def test_sem_cabecalho_volta_ao_remote_addr(self):
        self.assertEqual(ip_do_visitante(self._pedido()), "127.0.0.1")


@override_settings(PROXIES_CONFIAVEIS=1)
class LimitePorIpAtrasDoProxyTests(TestCase):
    def setUp(self):
        cache.clear()

    def _pedir(self, ip):
        return self.client.post(
            reverse("contas:solicitar_acesso"), DADOS_SOLICITACAO,
            REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR=ip,
        )

    def test_limite_e_separado_para_cada_visitante(self):
        for _ in range(5):
            self._pedir("200.1.1.1")
        self.assertContains(self._pedir("200.1.1.1"), "muitos pedidos")
        # Outra pessoa, também chegando pelo Nginx (127.0.0.1), não é barrada.
        resposta = self._pedir("200.2.2.2")
        self.assertRedirects(resposta, reverse("contas:solicitar_acesso_enviado"))
        self.assertEqual(SolicitacaoAcesso.objects.count(), 6)


class LoginSemDiferenciarMaiusculasTests(TestCase):
    """Item 4 da revisão: "Maria@..." entra na conta "maria@..."."""

    def _entrar(self, login):
        self.client.post(reverse("contas:login"), {"username": login, "password": "senha-teste-123"})
        return "_auth_user_id" in self.client.session

    def test_email_com_maiusculas_entra(self):
        User.objects.create_user("maria@escola.com", password="senha-teste-123")
        self.assertTrue(self._entrar("Maria@Escola.COM "))

    def test_login_gravado_com_maiusculas_continua_entrando(self):
        # Ex.: superusuário criado pelo createsuperuser com "Eloi".
        User.objects.create_user("Eloi", password="senha-teste-123")
        self.assertTrue(self._entrar("eloi"))
        self.client.logout()
        self.assertTrue(self._entrar("Eloi"))

    def test_senha_errada_continua_recusada(self):
        User.objects.create_user("maria@escola.com", password="senha-teste-123")
        resposta = self.client.post(reverse("contas:login"), {"username": "MARIA@escola.com", "password": "errada"})
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


@mock.patch("contas.emails.send_mail", side_effect=OSError("SMTP fora do ar"))
class FalhaNoEnvioDeEmailTests(TestCase):
    """Item 5 da revisão: SMTP fora do ar não derruba o Admin (sem erro 500)."""

    def setUp(self):
        equipe = User.objects.create_user("equipe@exemplo.com", password="senha-teste-123", is_staff=True)
        equipe.groups.add(Group.objects.get(name="Equipe administrativa"))
        self.client.force_login(equipe)

    def test_adicionar_usuario_avisa_e_mantem_a_conta(self, _send_mail):
        dados = {**DADOS_NOVO_USUARIO, "usable_password": "false", "password1": "", "password2": ""}
        with self.assertLogs("contas.emails", "ERROR"):
            resposta = self.client.post(reverse("admin:auth_user_add"), dados, follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(User.objects.filter(username="ana@exemplo.com").exists())
        self.assertContains(resposta, "Não foi possível enviar o e-mail")

    def test_aprovar_em_lote_segue_mesmo_com_falha(self, _send_mail):
        pedidos = [
            SolicitacaoAcesso.objects.create(nome=n, email=f"{n}@escola.com", escola_turma="EMEF")
            for n in ("bia", "caio")
        ]
        with self.assertLogs("contas.emails", "ERROR"):
            resposta = self.client.post(
                reverse("admin:contas_solicitacaoacesso_changelist"),
                {"action": "aprovar_e_criar_conta", "_selected_action": [p.pk for p in pedidos]},
                follow=True,
            )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(SolicitacaoAcesso.objects.filter(status=SolicitacaoAcesso.APROVADA).count(), 2)
        self.assertTrue(User.objects.filter(username="caio@escola.com").exists())
        self.assertContains(resposta, "Não foi possível enviar o e-mail")


# --------------------------------------------------------------------
# Multiescola, etapa 1 (09/11/2026): escolas, turmas, papéis, limites,
# bloqueio automático por contrato, isolamento entre escolas e
# consentimento LGPD.
# --------------------------------------------------------------------

from datetime import date, timedelta  # noqa: E402

from django.core.exceptions import ValidationError  # noqa: E402
from django.urls import include, path  # noqa: E402
from django.utils import timezone  # noqa: E402
from django.views.generic import DetailView  # noqa: E402

from .escopo import (  # noqa: E402
    IsolamentoPorEscolaMixin, alunos_visiveis, do_escopo_ou_404, escola_bloqueada,
    professores_visiveis, resultados_quiz_visiveis, turmas_visiveis,
)
from .middleware import MENSAGEM_ESCOLA_BLOQUEADA  # noqa: E402
from .models import LIMITE_ALUNOS_POR_TURMA, ConsentimentoResponsavel, Escola, Turma  # noqa: E402
from .papeis import GRUPO_ADMIN_ESCOLA, GRUPO_ALUNO, GRUPO_PROFESSOR  # noqa: E402


def criar_conta(login, tipo, escola=None, turma=None, ativa=True, senha=None):
    """Conta rápida para os testes (sem senha, a não ser que o teste vá logar pela tela)."""
    usuario = User.objects.create(username=login, email=login, first_name=login.split("@")[0], is_active=ativa)
    if senha:
        usuario.set_password(senha)
        usuario.save()
    perfil = usuario.perfil
    perfil.tipo, perfil.escola, perfil.turma = tipo, escola, turma
    perfil.save()
    return usuario


class DetalheTurmaTesteView(IsolamentoPorEscolaMixin, DetailView):
    """View de teste: mostra a turma só se ela estiver no escopo da conta."""

    escopo = "turmas"

    def render_to_response(self, context, **kwargs):
        from django.http import HttpResponse

        return HttpResponse(self.object.nome)


def detalhe_aluno_teste(request, pk):
    from django.http import HttpResponse

    return HttpResponse(do_escopo_ou_404("alunos", request.user, pk=pk).user.username)


def detalhe_professor_teste(request, pk):
    from django.http import HttpResponse

    return HttpResponse(do_escopo_ou_404("professores", request.user, pk=pk).user.username)


def detalhe_resultado_teste(request, pk):
    from django.http import HttpResponse

    return HttpResponse(str(do_escopo_ou_404("resultados_quiz", request.user, pk=pk).pontuacao))


# URLs só destes testes (as telas de verdade são da etapa 2), mais as do
# site, que a página 404 usa no menu.
urlpatterns = [
    path("", include("config.urls")),
    path("teste/turma/<int:pk>/", DetalheTurmaTesteView.as_view()),
    path("teste/aluno/<int:pk>/", detalhe_aluno_teste),
    path("teste/professor/<int:pk>/", detalhe_professor_teste),
    path("teste/resultado/<int:pk>/", detalhe_resultado_teste),
]


class DuasEscolasMixin:
    """Escola A e escola B, cada uma com admin, professor, turma e aluno."""

    def setUp(self):
        super().setUp()
        self.escola_a = Escola.objects.create(nome="Escola A", limite_professores=3)
        self.escola_b = Escola.objects.create(nome="Escola B", limite_professores=3)
        self.admin_a = criar_conta("admin@a.com", Perfil.ADMIN_ESCOLA, self.escola_a)
        self.admin_b = criar_conta("admin@b.com", Perfil.ADMIN_ESCOLA, self.escola_b)
        self.prof_a = criar_conta("prof@a.com", Perfil.PROFESSOR, self.escola_a)
        self.prof_a2 = criar_conta("prof2@a.com", Perfil.PROFESSOR, self.escola_a)
        self.prof_b = criar_conta("prof@b.com", Perfil.PROFESSOR, self.escola_b)
        self.turma_a = Turma.objects.create(escola=self.escola_a, nome="3º A", professor=self.prof_a.perfil)
        self.turma_a2 = Turma.objects.create(escola=self.escola_a, nome="4º A", professor=self.prof_a2.perfil)
        self.turma_b = Turma.objects.create(escola=self.escola_b, nome="3º B", professor=self.prof_b.perfil)
        self.aluno_a = criar_conta("aluno@a.com", Perfil.ALUNO, self.escola_a, self.turma_a)
        self.aluno_a2 = criar_conta("aluno2@a.com", Perfil.ALUNO, self.escola_a, self.turma_a2)
        self.aluno_b = criar_conta("aluno@b.com", Perfil.ALUNO, self.escola_b, self.turma_b)


class EscolaContratoTests(TestCase):
    def test_situacao_do_acesso_pelas_datas_e_pelo_ativa(self):
        hoje = timezone.localdate()
        escola = Escola(nome="X", contrato_inicio=hoje - timedelta(days=10), contrato_fim=hoje)
        self.assertTrue(escola.esta_liberada())  # o último dia ainda vale
        self.assertFalse(escola.esta_liberada(hoje + timedelta(days=1)))  # vencido
        self.assertFalse(escola.esta_liberada(hoje - timedelta(days=11)))  # ainda não começou
        escola.ativa = False
        self.assertFalse(escola.esta_liberada())
        self.assertTrue(Escola(nome="Sem datas").esta_liberada())

    def test_queryset_liberadas_bate_com_esta_liberada(self):
        hoje = timezone.localdate()
        liberada = Escola.objects.create(nome="Liberada", contrato_fim=hoje + timedelta(days=5))
        Escola.objects.create(nome="Vencida", contrato_fim=hoje - timedelta(days=1))
        Escola.objects.create(nome="Desativada", ativa=False)
        Escola.objects.create(nome="Futura", contrato_inicio=hoje + timedelta(days=1))
        self.assertEqual(list(Escola.objects.liberadas()), [liberada])

    def test_fim_antes_do_inicio_e_recusado(self):
        escola = Escola(nome="X", contrato_inicio=date(2027, 2, 1), contrato_fim=date(2027, 1, 1))
        with self.assertRaises(ValidationError):
            escola.full_clean()


class LimitesTests(DuasEscolasMixin, TestCase):
    def test_limite_de_professores_da_escola(self):
        criar_conta("prof3@a.com", Perfil.PROFESSOR, self.escola_a)  # 3º de 3
        novo = criar_conta("prof4@a.com", Perfil.OUTRO)
        novo.perfil.tipo, novo.perfil.escola = Perfil.PROFESSOR, self.escola_a
        with self.assertRaisesMessage(ValidationError, "Limite do plano atingido"):
            novo.perfil.full_clean()

    def test_professor_desativado_nao_conta_no_limite(self):
        criar_conta("prof3@a.com", Perfil.PROFESSOR, self.escola_a, ativa=False)
        novo = criar_conta("prof4@a.com", Perfil.OUTRO)
        novo.perfil.tipo, novo.perfil.escola = Perfil.PROFESSOR, self.escola_a
        novo.perfil.full_clean()  # sem erro: só 2 ativos

    def test_reativar_professor_alem_do_limite_e_recusado(self):
        criar_conta("prof3@a.com", Perfil.PROFESSOR, self.escola_a)
        inativo = criar_conta("prof4@a.com", Perfil.PROFESSOR, self.escola_a, ativa=False)
        inativo.is_active = True
        with self.assertRaisesMessage(ValidationError, "Limite do plano atingido"):
            inativo.perfil.full_clean()

    def test_nao_reduz_limite_abaixo_dos_professores_ativos(self):
        self.escola_a.limite_professores = 1
        with self.assertRaises(ValidationError):
            self.escola_a.full_clean()

    def test_limite_de_alunos_por_turma(self):
        for i in range(LIMITE_ALUNOS_POR_TURMA - 1):  # aluno_a já está na turma
            criar_conta(f"aluno{i}@x.com", Perfil.ALUNO, self.escola_a, self.turma_a)
        novo = criar_conta("aluno-novo@a.com", Perfil.ALUNO, self.escola_a)
        novo.perfil.turma = self.turma_a
        with self.assertRaisesMessage(ValidationError, f"já tem {LIMITE_ALUNOS_POR_TURMA} alunos"):
            novo.perfil.full_clean()
        self.aluno_a.perfil.full_clean()  # quem já está na turma continua válido

    def test_turma_de_outra_escola_e_recusada(self):
        self.aluno_a.perfil.turma = self.turma_b
        with self.assertRaisesMessage(ValidationError, "outra escola"):
            self.aluno_a.perfil.full_clean()

    def test_turma_so_para_aluno(self):
        self.prof_a.perfil.turma = self.turma_a
        with self.assertRaisesMessage(ValidationError, "Só alunos"):
            self.prof_a.perfil.full_clean()

    def test_escola_vem_da_turma(self):
        novo = criar_conta("aluno-novo@a.com", Perfil.ALUNO)
        novo.perfil.turma = self.turma_a2
        novo.perfil.full_clean()
        self.assertEqual(novo.perfil.escola, self.escola_a)

    def test_admin_da_escola_precisa_de_escola(self):
        novo = criar_conta("admin-novo@a.com", Perfil.OUTRO)
        novo.perfil.tipo = Perfil.ADMIN_ESCOLA
        with self.assertRaises(ValidationError):
            novo.perfil.full_clean()

    def test_professor_de_outra_escola_nao_assume_turma(self):
        turma = Turma(escola=self.escola_a, nome="5º A", professor=self.prof_b.perfil)
        with self.assertRaisesMessage(ValidationError, "não é desta escola"):
            turma.full_clean()

    def test_professor_com_turmas_nao_muda_de_tipo(self):
        self.prof_a.perfil.tipo = Perfil.ALUNO
        with self.assertRaisesMessage(ValidationError, "professor(a) responsável"):
            self.prof_a.perfil.full_clean()


class GruposDePapelTests(TestCase):
    def test_grupos_existem(self):
        for nome in (GRUPO_ADMIN_ESCOLA, GRUPO_PROFESSOR, GRUPO_ALUNO, "Equipe administrativa"):
            self.assertTrue(Group.objects.filter(name=nome).exists(), nome)

    def test_grupo_acompanha_o_tipo_sem_mexer_nos_outros(self):
        usuario = criar_conta("pessoa@x.com", Perfil.ALUNO)
        usuario.groups.add(Group.objects.get(name="Equipe editorial"))
        self.assertEqual(set(usuario.groups.values_list("name", flat=True)), {GRUPO_ALUNO, "Equipe editorial"})
        usuario.perfil.tipo = Perfil.PROFESSOR
        usuario.perfil.save()
        self.assertEqual(set(usuario.groups.values_list("name", flat=True)), {GRUPO_PROFESSOR, "Equipe editorial"})
        usuario.perfil.tipo = Perfil.OUTRO
        usuario.perfil.save()
        self.assertEqual(set(usuario.groups.values_list("name", flat=True)), {"Equipe editorial"})

    def test_permissoes_dos_papeis(self):
        professor = criar_conta("prof@x.com", Perfil.PROFESSOR)
        admin_escola = criar_conta("admin@x.com", Perfil.ADMIN_ESCOLA, Escola.objects.create(nome="X"))
        self.assertTrue(professor.has_perm("contas.cadastrar_alunos"))
        self.assertFalse(professor.has_perm("contas.cadastrar_professores"))
        self.assertTrue(admin_escola.has_perm("contas.cadastrar_professores"))
        self.assertFalse(admin_escola.has_perm("contas.cadastrar_alunos"))


@override_settings(ROOT_URLCONF="contas.tests")
class IsolamentoEntreEscolasTests(DuasEscolasMixin, TestCase):
    """Fora do escopo da conta, a resposta é 404 (não revela que o registro existe)."""

    def _status(self, usuario, url):
        self.client.force_login(usuario)
        return self.client.get(url).status_code

    def test_professor_ve_so_a_propria_turma(self):
        self.assertEqual(self._status(self.prof_a, f"/teste/turma/{self.turma_a.pk}/"), 200)
        self.assertEqual(self._status(self.prof_a, f"/teste/turma/{self.turma_b.pk}/"), 404)  # outra escola
        self.assertEqual(self._status(self.prof_a, f"/teste/turma/{self.turma_a2.pk}/"), 404)  # colega

    def test_admin_da_escola_ve_turmas_e_professores_so_da_propria_escola(self):
        self.assertEqual(self._status(self.admin_a, f"/teste/turma/{self.turma_a2.pk}/"), 200)
        self.assertEqual(self._status(self.admin_a, f"/teste/turma/{self.turma_b.pk}/"), 404)
        self.assertEqual(self._status(self.admin_a, f"/teste/professor/{self.prof_a.perfil.pk}/"), 200)
        self.assertEqual(self._status(self.admin_a, f"/teste/professor/{self.prof_b.perfil.pk}/"), 404)

    def test_admin_da_escola_nao_ve_alunos(self):
        self.assertEqual(self._status(self.admin_a, f"/teste/aluno/{self.aluno_a.perfil.pk}/"), 404)

    def test_professor_ve_so_alunos_das_proprias_turmas(self):
        self.assertEqual(self._status(self.prof_a, f"/teste/aluno/{self.aluno_a.perfil.pk}/"), 200)
        self.assertEqual(self._status(self.prof_a, f"/teste/aluno/{self.aluno_a2.perfil.pk}/"), 404)
        self.assertEqual(self._status(self.prof_a, f"/teste/aluno/{self.aluno_b.perfil.pk}/"), 404)
        self.assertEqual(self._status(self.prof_a, f"/teste/professor/{self.prof_a2.perfil.pk}/"), 404)

    def test_aluno_nao_ve_turma_nem_colega(self):
        self.assertEqual(self._status(self.aluno_a, f"/teste/turma/{self.turma_a.pk}/"), 404)
        self.assertEqual(self._status(self.aluno_a, f"/teste/aluno/{self.aluno_a2.perfil.pk}/"), 404)

    def test_equipe_da_plataforma_ve_todas_as_escolas(self):
        equipe = User.objects.create_user("equipe@plataforma.com", is_staff=True)
        self.assertEqual(self._status(equipe, f"/teste/turma/{self.turma_b.pk}/"), 200)
        self.assertEqual(self._status(equipe, f"/teste/aluno/{self.aluno_b.perfil.pk}/"), 200)

    def test_resultados_do_quiz_isolados_e_historico_acompanha_o_aluno(self):
        from obras.models import Obra
        from quiz.models import ResultadoQuiz

        obra = Obra.objects.create(titulo="Obra", slug="obra", publicada=True)
        antigo = ResultadoQuiz.objects.create(
            perfil=self.aluno_a2.perfil, turma=self.turma_a2, obra=obra, pontuacao=1, total=2, tempo_segundos=10
        )
        do_b = ResultadoQuiz.objects.create(
            perfil=self.aluno_b.perfil, turma=self.turma_b, obra=obra, pontuacao=2, total=2, tempo_segundos=10
        )
        self.assertEqual(self._status(self.prof_a, f"/teste/resultado/{antigo.pk}/"), 404)
        self.assertEqual(self._status(self.prof_a, f"/teste/resultado/{do_b.pk}/"), 404)
        self.assertEqual(self._status(self.admin_a, f"/teste/resultado/{antigo.pk}/"), 404)
        # O aluno muda para a turma do prof_a: o histórico vai junto.
        self.aluno_a2.perfil.turma = self.turma_a
        self.aluno_a2.perfil.save()
        self.assertEqual(self._status(self.prof_a, f"/teste/resultado/{antigo.pk}/"), 200)
        antigo.refresh_from_db()
        self.assertEqual(antigo.turma, self.turma_a2)  # a turma da época continua registrada
        self.assertEqual(self._status(self.aluno_a2, f"/teste/resultado/{antigo.pk}/"), 200)
        self.assertEqual(self._status(self.aluno_a2, f"/teste/resultado/{do_b.pk}/"), 404)

    def test_escola_bloqueada_nao_ve_nada(self):
        self.escola_a.ativa = False
        self.escola_a.save()
        usuario = User.objects.get(pk=self.prof_a.pk)
        self.assertFalse(turmas_visiveis(usuario).exists())
        self.assertFalse(alunos_visiveis(usuario).exists())
        self.assertFalse(resultados_quiz_visiveis(usuario).exists())
        self.assertFalse(professores_visiveis(User.objects.get(pk=self.admin_a.pk)).exists())


class BloqueioPorContratoTests(TestCase):
    """Bloqueio automático (decisão da cliente de 09/11/2026)."""

    def setUp(self):
        hoje = timezone.localdate()
        self.escola = Escola.objects.create(nome="Escola", contrato_fim=hoje)
        self.prof = criar_conta("prof@escola.com", Perfil.PROFESSOR, self.escola, senha="senha-teste-123")

    def _vencer(self):
        self.escola.contrato_fim = timezone.localdate() - timedelta(days=1)
        self.escola.save()

    def _entrar(self):
        return self.client.post(
            reverse("contas:login"), {"username": "prof@escola.com", "password": "senha-teste-123"}
        )

    def test_entra_no_ultimo_dia_do_contrato(self):
        self.assertEqual(self._entrar().status_code, 302)

    def test_login_recusado_com_contrato_vencido(self):
        self._vencer()
        resposta = self._entrar()
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "está suspenso")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_senha_errada_nao_revela_o_bloqueio(self):
        self._vencer()
        resposta = self.client.post(reverse("contas:login"), {"username": "prof@escola.com", "password": "errada"})
        self.assertNotContains(resposta, "está suspenso")

    def test_quem_estava_logado_e_desconectado(self):
        self.client.force_login(self.prof)
        self.assertEqual(self.client.get(reverse("obras:home")).status_code, 200)
        self._vencer()
        resposta = self.client.get(reverse("obras:home"), follow=True)
        self.assertRedirects(resposta, reverse("contas:login"))
        self.assertContains(resposta, MENSAGEM_ESCOLA_BLOQUEADA)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_escola_desativada_bloqueia_na_hora(self):
        self.escola.ativa = False
        self.escola.save()
        self.assertTrue(escola_bloqueada(User.objects.get(pk=self.prof.pk)))

    def test_renovar_o_contrato_libera_de_novo(self):
        self._vencer()
        self.escola.contrato_fim = timezone.localdate() + timedelta(days=365)
        self.escola.save()
        self.assertEqual(self._entrar().status_code, 302)

    def test_equipe_da_plataforma_nunca_e_bloqueada(self):
        self._vencer()
        self.prof.is_staff = True
        self.prof.save()
        self.assertEqual(self._entrar().status_code, 302)

    def test_conta_sem_escola_nao_e_afetada(self):
        self._vencer()
        criar_conta("avulso@x.com", Perfil.PROFESSOR, senha="senha-teste-123")
        resposta = self.client.post(reverse("contas:login"), {"username": "avulso@x.com", "password": "senha-teste-123"})
        self.assertEqual(resposta.status_code, 302)


class AdminEscolasTests(DuasEscolasMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.equipe = User.objects.create_user("equipe@plataforma.com", password="senha-teste-123", is_staff=True)
        self.equipe.groups.add(Group.objects.get(name="Equipe administrativa"))
        self.client.force_login(self.equipe)

    def test_equipe_administrativa_ve_escolas_e_turmas(self):
        resposta = self.client.get(reverse("admin:contas_escola_changelist"))
        self.assertContains(resposta, "Escola A")
        self.assertContains(resposta, "2 / 3")  # professores ativos / limite
        resposta = self.client.get(reverse("admin:contas_turma_changelist"), {"escola__id__exact": self.escola_b.pk})
        self.assertContains(resposta, "3º B")
        self.assertNotContains(resposta, "3º A")

    def test_filtro_de_escolas_bloqueadas(self):
        self.escola_b.contrato_fim = timezone.localdate() - timedelta(days=1)
        self.escola_b.save()
        resposta = self.client.get(reverse("admin:contas_escola_changelist"), {"situacao": "bloqueada"})
        self.assertContains(resposta, "Escola B")
        self.assertNotContains(resposta, "Escola A")

    def test_usuarios_filtrados_por_escola(self):
        resposta = self.client.get(reverse("admin:auth_user_changelist"), {"perfil__escola__id__exact": self.escola_a.pk})
        self.assertContains(resposta, "aluno@a.com")
        self.assertNotContains(resposta, "aluno@b.com")

    def test_cria_aluno_na_turma(self):
        dados = {**DADOS_NOVO_USUARIO, "email": "novo@a.com", "tipo": Perfil.ALUNO, "turma": self.turma_a.pk}
        resposta = self.client.post(reverse("admin:auth_user_add"), dados)
        self.assertEqual(resposta.status_code, 302)
        perfil = User.objects.get(username="novo@a.com").perfil
        self.assertEqual((perfil.escola, perfil.turma), (self.escola_a, self.turma_a))
        self.assertTrue(perfil.user.groups.filter(name=GRUPO_ALUNO).exists())

    def test_nao_cria_professor_alem_do_limite(self):
        criar_conta("prof3@a.com", Perfil.PROFESSOR, self.escola_a)
        dados = {**DADOS_NOVO_USUARIO, "escola": self.escola_a.pk}
        resposta = self.client.post(reverse("admin:auth_user_add"), dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Limite do plano atingido")
        self.assertFalse(User.objects.filter(username="ana@exemplo.com").exists())

    def test_inline_do_perfil_valida_a_turma(self):
        url = reverse("admin:auth_user_change", args=[self.aluno_a.pk])
        dados = {
            "username": "aluno@a.com",
            "is_active": "on",
            "date_joined_0": "2026-11-09",
            "date_joined_1": "10:00:00",
            "perfil-TOTAL_FORMS": "1",
            "perfil-INITIAL_FORMS": "1",
            "perfil-MIN_NUM_FORMS": "0",
            "perfil-MAX_NUM_FORMS": "1",
            "perfil-0-id": self.aluno_a.perfil.pk,
            "perfil-0-user": self.aluno_a.pk,
            "perfil-0-tipo": Perfil.ALUNO,
            "perfil-0-escola": self.escola_a.pk,
            "perfil-0-turma": self.turma_b.pk,
        }
        resposta = self.client.post(url, dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Esta turma é de outra escola.")

    def test_registra_consentimento_do_responsavel(self):
        resposta = self.client.post(reverse("admin:contas_consentimentoresponsavel_add"), {
            "aluno": self.aluno_a.perfil.pk,
            "nome_responsavel": "Maria",
            "parentesco": "mãe",
            "versao_termo": "2026-11",
            "meio": ConsentimentoResponsavel.PAPEL,
            "data_consentimento_0": "2026-11-09",
            "data_consentimento_1": "10:00:00",
        })
        self.assertEqual(resposta.status_code, 302)
        consentimento = ConsentimentoResponsavel.objects.get()
        self.assertEqual(consentimento.registrado_por, self.equipe)
        self.assertEqual(self.aluno_a.perfil.consentimento_valido(), consentimento)
        consentimento.revogado_em = timezone.now()
        consentimento.save()
        self.assertIsNone(self.aluno_a.perfil.consentimento_valido())

    def test_consentimento_so_para_aluno(self):
        consentimento = ConsentimentoResponsavel(aluno=self.prof_a.perfil, nome_responsavel="X", parentesco="pai")
        with self.assertRaises(ValidationError):
            consentimento.full_clean()

    def test_equipe_administrativa_ve_resultados_do_quiz(self):
        self.assertEqual(self.client.get(reverse("admin:quiz_resultadoquiz_changelist")).status_code, 200)

    def test_telas_do_admin_abrem(self):
        urls = [
            reverse("admin:contas_escola_add"),
            reverse("admin:contas_escola_change", args=[self.escola_a.pk]),
            reverse("admin:contas_turma_add"),
            reverse("admin:contas_turma_change", args=[self.turma_a.pk]),
            reverse("admin:contas_consentimentoresponsavel_add"),
            reverse("admin:contas_consentimentoresponsavel_changelist"),
            reverse("admin:auth_user_add"),
            reverse("admin:auth_user_change", args=[self.aluno_a.pk]),
            reverse("admin:autocomplete") + "?app_label=contas&model_name=consentimentoresponsavel&field_name=aluno&term=aluno",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        # A busca de aluno do consentimento só traz alunos.
        ids = {int(item["id"]) for item in self.client.get(urls[-1]).json()["results"]}
        self.assertIn(self.aluno_a.perfil.pk, ids)
        self.assertNotIn(self.prof_a.perfil.pk, ids)
