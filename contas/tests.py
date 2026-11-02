import importlib
import re
from io import StringIO

from django.apps import apps
from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from .models import Perfil, SolicitacaoAcesso

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
