from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contas.models import LIMITE_ALUNOS_POR_TURMA, ConsentimentoResponsavel, Escola, Perfil, Turma
from obras.models import Obra
from quiz.models import ResultadoQuiz

from .acessos import gerar_login, gerar_senha
from .views import CHAVE_CARTOES


def criar_conta(login, tipo, escola=None, turma=None, ativa=True):
    usuario = User.objects.create(username=login, email=login if "@" in login else "", first_name=login.split("@")[0], is_active=ativa)
    perfil = usuario.perfil
    perfil.tipo, perfil.escola, perfil.turma = tipo, escola, turma
    perfil.save()
    return usuario


class EscolasMixin:
    """Escola A (admin, 2 professores com uma turma cada) e escola B."""

    def setUp(self):
        super().setUp()
        self.escola_a = Escola.objects.create(nome="Escola A", limite_professores=3)
        self.escola_b = Escola.objects.create(nome="Escola B")
        self.admin_a = criar_conta("admin@a.com", Perfil.ADMIN_ESCOLA, self.escola_a)
        self.admin_b = criar_conta("admin@b.com", Perfil.ADMIN_ESCOLA, self.escola_b)
        self.prof_a = criar_conta("prof@a.com", Perfil.PROFESSOR, self.escola_a)
        self.prof_a2 = criar_conta("prof2@a.com", Perfil.PROFESSOR, self.escola_a)
        self.prof_b = criar_conta("prof@b.com", Perfil.PROFESSOR, self.escola_b)
        self.turma_a = Turma.objects.create(escola=self.escola_a, nome="3º ano A", professor=self.prof_a.perfil)
        self.turma_a2 = Turma.objects.create(escola=self.escola_a, nome="4º ano A", professor=self.prof_a2.perfil)
        self.turma_b = Turma.objects.create(escola=self.escola_b, nome="3º ano B", professor=self.prof_b.perfil)
        self.aluno_a = criar_conta("aluno.a", Perfil.ALUNO, self.escola_a, self.turma_a)
        self.aluno_a2 = criar_conta("aluno.a2", Perfil.ALUNO, self.escola_a, self.turma_a2)
        self.aluno_b = criar_conta("aluno.b", Perfil.ALUNO, self.escola_b, self.turma_b)


class GeracaoDeAcessoTests(TestCase):
    def test_senha_simples(self):
        for _ in range(50):
            self.assertRegex(gerar_senha(), r"^[a-z]+[0-9]{3}$")

    def test_login_curto_sem_acento_e_unico(self):
        escola = Escola.objects.create(nome="E")
        turma = Turma.objects.create(escola=escola, nome="3º ano B")
        self.assertEqual(gerar_login("João da Silva", turma), "joao.3oanob")
        User.objects.create(username="joao.3oanob")
        self.assertEqual(gerar_login("João Pedro", turma), "joao2.3oanob")
        User.objects.create(username="JOAO2.3oanob")
        self.assertEqual(gerar_login("joão", turma), "joao3.3oanob")


class AcessoAAreaDaEscolaTests(EscolasMixin, TestCase):
    def _status(self, usuario, nome, *args, metodo="get"):
        self.client.force_login(usuario)
        return getattr(self.client, metodo)(reverse(f"escola:{nome}", args=args)).status_code

    def test_inicio_leva_cada_papel_para_sua_tela(self):
        self.client.force_login(self.admin_a)
        self.assertRedirects(self.client.get(reverse("escola:inicio")), reverse("escola:professores"))
        self.client.force_login(self.prof_a)
        self.assertRedirects(self.client.get(reverse("escola:inicio")), reverse("escola:turmas"))
        self.assertEqual(self._status(self.aluno_a, "inicio"), 403)

    def test_aluno_e_conta_sem_escola_nao_entram(self):
        self.assertEqual(self._status(self.aluno_a, "turmas"), 403)
        self.assertEqual(self._status(self.aluno_a, "professores"), 403)
        avulso = criar_conta("avulso@x.com", Perfil.PROFESSOR)
        self.assertEqual(self._status(avulso, "turmas"), 403)
        equipe = User.objects.create_superuser("equipe", password="senha-teste-123")
        self.assertEqual(self._status(equipe, "professores"), 403)  # a equipe usa o Admin

    def test_professor_nao_gerencia_professores(self):
        self.assertEqual(self._status(self.prof_a, "professores"), 403)
        self.assertEqual(self._status(self.prof_a, "professor_novo"), 403)

    def test_professor_nao_cadastra_nem_mexe_no_acesso_dos_alunos(self):
        """13/11/2026: cadastro, edição, mudança de turma, termo e senhas são do Admin da escola."""
        aluno = self.aluno_a.perfil.pk
        for nome, args, metodo in [
            ("aluno_novo", [self.turma_a.pk], "get"), ("aluno_novo", [self.turma_a.pk], "post"),
            ("alunos_lote", [self.turma_a.pk], "get"), ("alunos_lote", [self.turma_a.pk], "post"),
            ("novas_senhas_turma", [self.turma_a.pk], "post"),
            ("aluno_editar", [aluno], "get"), ("aluno_editar", [aluno], "post"),
            ("aluno_nova_senha", [aluno], "post"), ("aluno_ativo", [aluno], "post"),
            ("aluno_consentimento", [aluno], "get"), ("aluno_consentimento", [aluno], "post"),
        ]:
            with self.subTest(nome, metodo=metodo):
                self.assertEqual(self._status(self.prof_a, nome, *args, metodo=metodo), 403)
        self.aluno_a.refresh_from_db()
        self.assertTrue(self.aluno_a.is_active)
        self.assertFalse(self.aluno_a.perfil.consentimentos.exists())

    def test_admin_da_escola_nao_ve_desempenho(self):
        """13/11/2026: relatórios, resultados e atividade complementar são só do professor."""
        for nome, args, metodo in [
            ("turma_relatorio", [self.turma_a.pk], "get"),
            ("aluno_relatorio", [self.aluno_a.perfil.pk], "get"),
            ("atividades_lancar", [self.turma_a.pk], "get"),
            ("atividades_lancar", [self.turma_a.pk], "post"),
        ]:
            with self.subTest(nome, metodo=metodo):
                self.assertEqual(self._status(self.admin_a, nome, *args, metodo=metodo), 403)

    def test_desempenho_fica_fora_do_admin_da_escola_mesmo_com_a_permissao(self):
        """Segunda trava: a turma/aluno do relatório é buscada só entre as do professor (404)."""
        from django.contrib.auth.models import Permission

        self.admin_a.user_permissions.add(Permission.objects.get(codename="ver_desempenho_turma"))
        admin = User.objects.get(pk=self.admin_a.pk)  # limpa o cache de permissões
        self.assertEqual(self._status(admin, "turma_relatorio", self.turma_a.pk), 404)
        self.assertEqual(self._status(admin, "aluno_relatorio", self.aluno_a.perfil.pk), 404)
        self.assertEqual(self._status(admin, "atividades_lancar", self.turma_a.pk), 404)

    def test_admin_da_escola_nao_tem_acesso_ao_django_admin(self):
        self.client.force_login(self.admin_a)
        resposta = self.client.get(reverse("admin:quiz_resultadoquiz_changelist"))
        self.assertRedirects(resposta, reverse("admin:login") + "?next=" + reverse("admin:quiz_resultadoquiz_changelist"))
        resposta = self.client.get(reverse("admin:escola_entregaatividade_changelist"))
        self.assertEqual(resposta.status_code, 302)

    def test_professor_nao_cria_nem_edita_turma(self):
        self.assertEqual(self._status(self.prof_a, "turma_nova"), 403)
        self.assertEqual(self._status(self.prof_a, "turma_editar", self.turma_a.pk), 403)

    def test_isolamento_entre_escolas_da_404(self):
        self.assertEqual(self._status(self.admin_a, "professor_editar", self.prof_b.perfil.pk), 404)
        self.assertEqual(self._status(self.admin_a, "professor_ativo", self.prof_b.perfil.pk, metodo="post"), 404)
        self.assertEqual(self._status(self.prof_a, "turma", self.turma_b.pk), 404)
        self.assertEqual(self._status(self.admin_a, "turma", self.turma_b.pk), 404)
        self.assertEqual(self._status(self.admin_a, "aluno_editar", self.aluno_b.perfil.pk), 404)
        self.assertEqual(self._status(self.admin_a, "aluno_nova_senha", self.aluno_b.perfil.pk, metodo="post"), 404)
        self.assertEqual(self._status(self.admin_a, "aluno_consentimento", self.aluno_b.perfil.pk), 404)
        self.assertEqual(self._status(self.admin_a, "aluno_novo", self.turma_b.pk), 404)
        self.prof_b.refresh_from_db()
        self.assertTrue(self.prof_b.is_active)

    def test_professor_nao_ve_turma_nem_aluno_do_colega(self):
        self.assertEqual(self._status(self.prof_a, "turma", self.turma_a2.pk), 404)
        self.assertEqual(self._status(self.prof_a, "cartoes", self.turma_a2.pk), 404)
        self.assertEqual(self._status(self.prof_a, "aluno_relatorio", self.aluno_a2.perfil.pk), 404)

    def test_navbar_mostra_o_link_certo(self):
        self.client.force_login(self.admin_a)
        self.assertContains(self.client.get(reverse("obras:home")), "Minha escola")
        self.client.force_login(self.prof_a)
        self.assertContains(self.client.get(reverse("obras:home")), "Minhas turmas")
        self.client.force_login(self.aluno_a)
        resposta = self.client.get(reverse("obras:home"))
        self.assertNotContains(resposta, "Minhas turmas")
        self.assertNotContains(resposta, "Minha escola")


class ProfessoresDoAdminDaEscolaTests(EscolasMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_a)

    def test_lista_so_os_professores_da_escola(self):
        resposta = self.client.get(reverse("escola:professores"))
        self.assertContains(resposta, "prof@a.com")
        self.assertContains(resposta, "prof2@a.com")
        self.assertNotContains(resposta, "prof@b.com")
        self.assertContains(resposta, "2 de 3 professores ativos")

    def test_cadastra_professor_e_manda_link_de_senha(self):
        resposta = self.client.post(reverse("escola:professor_novo"), {"nome": "Ana", "email": "Ana@A.com"})
        self.assertRedirects(resposta, reverse("escola:professores"))
        ana = User.objects.get(username="ana@a.com")
        self.assertEqual((ana.perfil.tipo, ana.perfil.escola), (Perfil.PROFESSOR, self.escola_a))
        self.assertTrue(ana.groups.filter(name="Professor").exists())
        self.assertEqual(mail.outbox[0].to, ["ana@a.com"])

    def test_limite_do_plano(self):
        criar_conta("prof3@a.com", Perfil.PROFESSOR, self.escola_a)
        resposta = self.client.get(reverse("escola:professores"))
        self.assertContains(resposta, "Limite do plano atingido")
        self.assertNotContains(resposta, reverse("escola:professor_novo"))
        resposta = self.client.post(reverse("escola:professor_novo"), {"nome": "Ana", "email": "ana@a.com"})
        self.assertContains(resposta, "Limite do plano atingido")
        self.assertFalse(User.objects.filter(username="ana@a.com").exists())

    def test_email_repetido_e_recusado(self):
        resposta = self.client.post(reverse("escola:professor_novo"), {"nome": "X", "email": "PROF@b.com"})
        self.assertContains(resposta, "Já existe uma conta")

    def test_edita_nome_e_email(self):
        url = reverse("escola:professor_editar", args=[self.prof_a.perfil.pk])
        self.client.post(url, {"nome": "Professora Ana", "email": "ana.nova@a.com"})
        self.prof_a.refresh_from_db()
        self.assertEqual((self.prof_a.first_name, self.prof_a.username, self.prof_a.email),
                         ("Professora Ana", "ana.nova@a.com", "ana.nova@a.com"))

    def test_desativa_e_reativa_dentro_do_limite(self):
        url = reverse("escola:professor_ativo", args=[self.prof_a.perfil.pk])
        self.client.post(url)
        self.prof_a.refresh_from_db()
        self.assertFalse(self.prof_a.is_active)
        criar_conta("prof3@a.com", Perfil.PROFESSOR, self.escola_a)
        criar_conta("prof4@a.com", Perfil.PROFESSOR, self.escola_a)  # 3 de 3 ativos agora
        resposta = self.client.post(url, follow=True)
        self.assertContains(resposta, "Limite do plano atingido")
        self.prof_a.refresh_from_db()
        self.assertFalse(self.prof_a.is_active)

    def test_get_nao_desativa(self):
        self.client.get(reverse("escola:professor_ativo", args=[self.prof_a.perfil.pk]))
        self.prof_a.refresh_from_db()
        self.assertTrue(self.prof_a.is_active)

    def test_ve_turmas_da_escola_com_link_para_os_alunos(self):
        resposta = self.client.get(reverse("escola:turmas"))
        self.assertContains(resposta, "3º ano A")
        self.assertContains(resposta, "4º ano A")
        self.assertNotContains(resposta, "3º ano B")
        self.assertContains(resposta, 'href="%s"' % reverse("escola:turma", args=[self.turma_a.pk]))
        self.assertContains(resposta, 'href="%s"' % reverse("escola:turma", args=[self.turma_a2.pk]))


class TurmasDoProfessorTests(EscolasMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.prof_a)

    def test_lista_so_as_proprias_turmas(self):
        resposta = self.client.get(reverse("escola:turmas"))
        self.assertContains(resposta, "3º ano A")
        self.assertNotContains(resposta, "4º ano A")

    def test_lista_avisa_que_a_turma_vem_da_escola(self):
        resposta = self.client.get(reverse("escola:turmas"))
        self.assertContains(resposta, "As turmas e o cadastro dos alunos ficam com a administração da escola")
        self.assertNotContains(resposta, reverse("escola:turma_nova"))


class TurmasDoAdminDaEscolaTests(EscolasMixin, TestCase):
    """Revisão de 09/11/2026: o Admin da escola cria as turmas e designa o professor."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_a)

    def test_lista_todas_as_turmas_da_escola_com_editar(self):
        resposta = self.client.get(reverse("escola:turmas"))
        self.assertContains(resposta, "3º ano A")
        self.assertContains(resposta, "4º ano A")
        self.assertNotContains(resposta, "3º ano B")
        self.assertContains(resposta, reverse("escola:turma_nova"))
        self.assertContains(resposta, reverse("escola:turma_editar", args=[self.turma_a.pk]))

    def test_cria_turma_e_designa_professor(self):
        resposta = self.client.post(
            reverse("escola:turma_nova"), {"nome": "5º ano C", "ano_letivo": 2027, "professor": self.prof_a2.perfil.pk}
        )
        self.assertRedirects(resposta, reverse("escola:turmas"))
        turma = Turma.objects.get(nome="5º ano C")
        self.assertEqual((turma.escola, turma.professor), (self.escola_a, self.prof_a2.perfil))
        # O professor designado passa a ver a turma; o colega, não.
        self.client.force_login(self.prof_a2)
        self.assertEqual(self.client.get(reverse("escola:turma", args=[turma.pk])).status_code, 200)
        self.client.force_login(self.prof_a)
        self.assertEqual(self.client.get(reverse("escola:turma", args=[turma.pk])).status_code, 404)
        self.client.force_login(self.admin_a)  # a escola vê todas as turmas dela
        self.assertEqual(self.client.get(reverse("escola:turma", args=[turma.pk])).status_code, 200)

    def test_cria_turma_sem_professor(self):
        self.client.post(reverse("escola:turma_nova"), {"nome": "5º ano C", "ano_letivo": 2027})
        self.assertIsNone(Turma.objects.get(nome="5º ano C").professor)
        self.assertContains(self.client.get(reverse("escola:turmas")), "sem professor(a)")

    def test_so_professores_ativos_da_escola_aparecem(self):
        self.prof_a2.is_active = False
        self.prof_a2.save()
        campo = self.client.get(reverse("escola:turma_nova")).context["form"].fields["professor"]
        self.assertEqual(list(campo.queryset), [self.prof_a.perfil])
        resposta = self.client.post(
            reverse("escola:turma_nova"), {"nome": "5º ano C", "ano_letivo": 2027, "professor": self.prof_b.perfil.pk}
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Turma.objects.filter(nome="5º ano C").exists())

    def test_troca_o_professor_da_turma(self):
        url = reverse("escola:turma_editar", args=[self.turma_a.pk])
        self.client.post(url, {
            "nome": "3º ano A", "ano_letivo": self.turma_a.ano_letivo, "professor": self.prof_a2.perfil.pk, "ativa": "on",
        })
        self.turma_a.refresh_from_db()
        self.assertEqual(self.turma_a.professor, self.prof_a2.perfil)
        self.assertEqual(self.turma_a.alunos_ativos().count(), 1)  # os alunos ficam na turma

    def test_turma_repetida_no_mesmo_ano_e_recusada(self):
        resposta = self.client.post(
            reverse("escola:turma_nova"), {"nome": "4º ANO A", "ano_letivo": self.turma_a2.ano_letivo}
        )
        self.assertContains(resposta, "já tem uma turma com este nome")

    def test_encerra_turma(self):
        url = reverse("escola:turma_editar", args=[self.turma_a.pk])
        self.client.post(url, {"nome": "3º ano A", "ano_letivo": self.turma_a.ano_letivo, "professor": self.prof_a.perfil.pk})
        self.turma_a.refresh_from_db()
        self.assertFalse(self.turma_a.ativa)
        self.assertEqual(self.turma_a.professor, self.prof_a.perfil)

    def test_turma_de_outra_escola_da_404(self):
        self.assertEqual(self.client.get(reverse("escola:turma_editar", args=[self.turma_b.pk])).status_code, 404)

    def test_telas_abrem(self):
        for nome, args in [("turmas", []), ("turma_nova", []), ("turma_editar", [self.turma_a.pk])]:
            with self.subTest(nome):
                self.assertEqual(self.client.get(reverse(f"escola:{nome}", args=args)).status_code, 200)


class AlunosDoAdminDaEscolaTests(EscolasMixin, TestCase):
    """13/11/2026: o cadastro e o acesso dos alunos passaram do professor para o Admin da escola."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin_a)

    def _cartoes(self):
        return self.client.session.get(CHAVE_CARTOES, [])

    def test_cadastra_aluno_com_login_e_senha_e_mostra_o_cartao(self):
        resposta = self.client.post(reverse("escola:aluno_novo", args=[self.turma_a.pk]), {"nome": "João da Silva"}, follow=True)
        self.assertRedirects(resposta, reverse("escola:cartoes", args=[self.turma_a.pk]))
        joao = User.objects.get(first_name="João da Silva")
        self.assertEqual(joao.username, "joao.3oanoa")
        self.assertEqual(joao.email, "")
        self.assertEqual((joao.perfil.tipo, joao.perfil.escola, joao.perfil.turma), (Perfil.ALUNO, self.escola_a, self.turma_a))
        self.assertTrue(joao.groups.filter(name="Aluno").exists())
        cartao = self._cartoes()[0]
        self.assertTrue(joao.check_password(cartao["senha"]))
        self.assertContains(resposta, "joao.3oanoa")
        self.assertContains(resposta, cartao["senha"])

    def test_aluno_entra_com_o_usuario_do_cartao(self):
        self.client.post(reverse("escola:aluno_novo", args=[self.turma_a.pk]), {"nome": "Maria"})
        cartao = self._cartoes()[0]
        self.client.logout()
        resposta = self.client.post(reverse("contas:login"), {"username": cartao["login"].upper(), "password": cartao["senha"]})
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), User.objects.get(username=cartao["login"]).pk)

    def test_cadastro_em_lote(self):
        nomes = "Ana Souza\n\n  Bruno   Lima \nAna Costa\n"
        resposta = self.client.post(reverse("escola:alunos_lote", args=[self.turma_a.pk]), {"nomes": nomes})
        self.assertRedirects(resposta, reverse("escola:cartoes", args=[self.turma_a.pk]))
        logins = sorted(c["login"] for c in self._cartoes())
        self.assertEqual(logins, ["ana.3oanoa", "ana2.3oanoa", "bruno.3oanoa"])
        self.assertTrue(User.objects.filter(first_name="Bruno Lima").exists())

    def test_lote_alem_do_limite_nao_cria_ninguem(self):
        nomes = "\n".join(f"Aluno {i}" for i in range(LIMITE_ALUNOS_POR_TURMA))  # 1 já está na turma
        resposta = self.client.post(reverse("escola:alunos_lote", args=[self.turma_a.pk]), {"nomes": nomes})
        self.assertContains(resposta, "29 vaga(s)")
        self.assertEqual(self.turma_a.alunos.count(), 1)

    def test_turma_cheia_recusa_aluno_individual(self):
        for i in range(LIMITE_ALUNOS_POR_TURMA - 1):
            criar_conta(f"x{i}", Perfil.ALUNO, self.escola_a, self.turma_a)
        resposta = self.client.post(reverse("escola:aluno_novo", args=[self.turma_a.pk]), {"nome": "Sobrando"})
        self.assertContains(resposta, f"já tem {LIMITE_ALUNOS_POR_TURMA} alunos")
        self.assertFalse(User.objects.filter(first_name="Sobrando").exists())

    def test_nova_senha_troca_a_senha_e_gera_o_cartao(self):
        self.aluno_a.set_password("antiga123")
        self.aluno_a.save()
        self.client.post(reverse("escola:aluno_nova_senha", args=[self.aluno_a.perfil.pk]))
        self.aluno_a.refresh_from_db()
        self.assertFalse(self.aluno_a.check_password("antiga123"))
        self.assertTrue(self.aluno_a.check_password(self._cartoes()[0]["senha"]))

    def test_senhas_novas_para_a_turma_toda(self):
        criar_conta("inativo", Perfil.ALUNO, self.escola_a, self.turma_a, ativa=False)
        self.client.post(reverse("escola:novas_senhas_turma", args=[self.turma_a.pk]))
        self.assertEqual([c["login"] for c in self._cartoes()], ["aluno.a"])

    def test_cadastra_em_qualquer_turma_da_escola(self):
        self.client.post(reverse("escola:aluno_novo", args=[self.turma_a2.pk]), {"nome": "Rita"})
        self.assertEqual(User.objects.get(first_name="Rita").perfil.turma, self.turma_a2)
        sem_professor = Turma.objects.create(escola=self.escola_a, nome="5º ano")
        self.client.post(reverse("escola:alunos_lote", args=[sem_professor.pk]), {"nomes": "Lia\nTeo"})
        self.assertEqual(sem_professor.alunos.count(), 2)

    def test_cartoes_de_outra_turma_nao_aparecem(self):
        self.client.post(reverse("escola:aluno_novo", args=[self.turma_a.pk]), {"nome": "Maria"})
        senha = self._cartoes()[0]["senha"]
        resposta = self.client.get(reverse("escola:cartoes", args=[self.turma_a2.pk]))
        self.assertNotContains(resposta, senha)
        self.assertNotContains(resposta, "maria.3oanoa")
        self.assertContains(resposta, "aluno.a2")  # sem senha na sessão: cartões só com o usuário
        self.assertContains(resposta, "Senha: ____________")

    def test_tela_da_turma_tem_as_acoes_de_cadastro_e_nao_o_desempenho(self):
        resposta = self.client.get(reverse("escola:turma", args=[self.turma_a.pk]))
        self.assertContains(resposta, reverse("escola:aluno_novo", args=[self.turma_a.pk]))
        self.assertContains(resposta, reverse("escola:aluno_editar", args=[self.aluno_a.perfil.pk]))
        self.assertContains(resposta, reverse("escola:aluno_consentimento", args=[self.aluno_a.perfil.pk]))
        self.assertContains(resposta, reverse("escola:novas_senhas_turma", args=[self.turma_a.pk]))
        self.assertNotContains(resposta, reverse("escola:turma_relatorio", args=[self.turma_a.pk]))
        self.assertNotContains(resposta, reverse("escola:atividades_lancar", args=[self.turma_a.pk]))
        self.assertNotContains(resposta, reverse("escola:aluno_relatorio", args=[self.aluno_a.perfil.pk]))

    def test_muda_de_turma_e_o_historico_vai_junto(self):
        outra = Turma.objects.create(escola=self.escola_a, nome="Outra", professor=self.prof_a.perfil)
        obra = Obra.objects.create(titulo="Obra", slug="obra", publicada=True)
        ResultadoQuiz.objects.create(perfil=self.aluno_a.perfil, turma=self.turma_a, obra=obra, pontuacao=1, total=2, tempo_segundos=5)
        url = reverse("escola:aluno_editar", args=[self.aluno_a.perfil.pk])
        self.client.post(url, {"nome": "Aluno A", "turma": outra.pk})
        self.aluno_a.perfil.refresh_from_db()
        self.assertEqual(self.aluno_a.perfil.turma, outra)
        self.assertEqual(self.aluno_a.perfil.resultados_quiz.count(), 1)

    def test_move_aluno_entre_turmas_da_escola_mas_nao_para_outra_escola(self):
        url = reverse("escola:aluno_editar", args=[self.aluno_a.perfil.pk])
        resposta = self.client.post(url, {"nome": "Aluno A", "turma": self.turma_b.pk})
        self.assertEqual(resposta.status_code, 200)
        self.aluno_a.perfil.refresh_from_db()
        self.assertEqual(self.aluno_a.perfil.turma, self.turma_a)
        resposta = self.client.post(url, {"nome": "Aluno A", "turma": self.turma_a2.pk})
        self.assertRedirects(resposta, reverse("escola:turma", args=[self.turma_a.pk]))
        self.aluno_a.perfil.refresh_from_db()
        self.assertEqual(self.aluno_a.perfil.turma, self.turma_a2)
        # Quem passa a ver o aluno é o professor da turma nova.
        self.client.force_login(self.prof_a2)
        self.assertEqual(self.client.get(reverse("escola:aluno_relatorio", args=[self.aluno_a.perfil.pk])).status_code, 200)
        self.client.force_login(self.prof_a)
        self.assertEqual(self.client.get(reverse("escola:aluno_relatorio", args=[self.aluno_a.perfil.pk])).status_code, 404)

    def test_desativa_e_reativa_aluno(self):
        url = reverse("escola:aluno_ativo", args=[self.aluno_a.perfil.pk])
        self.client.post(url)
        self.aluno_a.refresh_from_db()
        self.assertFalse(self.aluno_a.is_active)
        self.client.post(url)
        self.aluno_a.refresh_from_db()
        self.assertTrue(self.aluno_a.is_active)

    def test_registra_consentimento(self):
        url = reverse("escola:aluno_consentimento", args=[self.aluno_a.perfil.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        resposta = self.client.post(url, {
            "nome_responsavel": "Maria", "parentesco": "mãe", "meio": ConsentimentoResponsavel.PAPEL,
            "data_consentimento": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertRedirects(resposta, reverse("escola:turma", args=[self.turma_a.pk]))
        consentimento = self.aluno_a.perfil.consentimento_valido()
        self.assertEqual((consentimento.nome_responsavel, consentimento.registrado_por), ("Maria", self.admin_a))
        self.assertContains(self.client.get(reverse("escola:turma", args=[self.turma_a.pk])), "Sim (Maria)")
        # O professor da turma vê o termo, só para leitura.
        self.client.force_login(self.prof_a)
        self.assertContains(self.client.get(reverse("escola:turma", args=[self.turma_a.pk])), "Sim (Maria)")

    def test_telas_abrem(self):
        for nome, args in [
            ("turmas", []), ("turma", [self.turma_a.pk]),
            ("aluno_novo", [self.turma_a.pk]), ("alunos_lote", [self.turma_a.pk]), ("cartoes", [self.turma_a.pk]),
            ("aluno_editar", [self.aluno_a.perfil.pk]), ("aluno_consentimento", [self.aluno_a.perfil.pk]),
            ("turma", [self.turma_a2.pk]),
        ]:
            with self.subTest(nome):
                self.assertEqual(self.client.get(reverse(f"escola:{nome}", args=args)).status_code, 200)


class TurmaVistaPeloProfessorTests(EscolasMixin, TestCase):
    """13/11/2026: o professor vê os alunos, o termo (só leitura) e os cartões sem senha."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.prof_a)

    def test_lista_os_alunos_sem_as_acoes_de_cadastro(self):
        resposta = self.client.get(reverse("escola:turma", args=[self.turma_a.pk]))
        self.assertContains(resposta, "aluno.a")
        self.assertContains(resposta, reverse("escola:turma_relatorio", args=[self.turma_a.pk]))
        self.assertContains(resposta, reverse("escola:atividades_lancar", args=[self.turma_a.pk]))
        self.assertContains(resposta, reverse("escola:aluno_relatorio", args=[self.aluno_a.perfil.pk]))
        for url in [
            reverse("escola:aluno_novo", args=[self.turma_a.pk]), reverse("escola:alunos_lote", args=[self.turma_a.pk]),
            reverse("escola:aluno_editar", args=[self.aluno_a.perfil.pk]),
            reverse("escola:aluno_nova_senha", args=[self.aluno_a.perfil.pk]),
            reverse("escola:aluno_ativo", args=[self.aluno_a.perfil.pk]),
            reverse("escola:aluno_consentimento", args=[self.aluno_a.perfil.pk]),
            reverse("escola:novas_senhas_turma", args=[self.turma_a.pk]),
        ]:
            with self.subTest(url):
                self.assertNotContains(resposta, url)

    def test_termo_so_leitura(self):
        self.assertContains(self.client.get(reverse("escola:turma", args=[self.turma_a.pk])), "Não registrado")
        ConsentimentoResponsavel.objects.create(
            aluno=self.aluno_a.perfil, nome_responsavel="Joana", parentesco="mãe",
            meio=ConsentimentoResponsavel.PAPEL, data_consentimento=timezone.now(), registrado_por=self.admin_a,
        )
        self.assertContains(self.client.get(reverse("escola:turma", args=[self.turma_a.pk])), "Sim (Joana)")

    def test_cartoes_so_com_o_usuario(self):
        criar_conta("inativo", Perfil.ALUNO, self.escola_a, self.turma_a, ativa=False)
        sessao = self.client.session
        sessao[CHAVE_CARTOES] = [{"turma": self.turma_a.pk, "nome": "X", "login": "aluno.a", "senha": "sapo123"}]
        sessao.save()
        resposta = self.client.get(reverse("escola:cartoes", args=[self.turma_a.pk]))
        self.assertContains(resposta, "aluno.a")
        self.assertNotContains(resposta, "inativo")
        self.assertNotContains(resposta, "sapo123")  # o professor nunca vê senha
        self.assertContains(resposta, "Senha: ____________")
        self.assertContains(resposta, "peça à administração da escola")


class EscolaBloqueadaTests(EscolasMixin, TestCase):
    def test_professor_de_escola_vencida_e_desconectado(self):
        from datetime import timedelta

        self.escola_a.contrato_fim = timezone.localdate() - timedelta(days=1)
        self.escola_a.save()
        self.client.force_login(self.prof_a)
        self.assertRedirects(self.client.get(reverse("escola:turmas")), reverse("contas:login"))


# --------------------------------------------------------------------
# Etapa 3 (09/11/2026): relatórios por turma/aluno e atividade complementar
# --------------------------------------------------------------------

from decimal import Decimal  # noqa: E402

from quiz.models import RespostaQuiz  # noqa: E402

from . import relatorios  # noqa: E402
from .models import EntregaAtividade  # noqa: E402


class RelatoriosMixin(EscolasMixin):
    def setUp(self):
        super().setUp()
        self.obra = Obra.objects.create(titulo="Lenda da Erva-Mate", slug="lenda", publicada=True)
        self.outra_obra = Obra.objects.create(titulo="Negrinho do Pastoreio", slug="negrinho", publicada=True)
        Obra.objects.create(titulo="Rascunho", slug="rascunho", publicada=False)
        self.aluno_a3 = criar_conta("aluno.a3", Perfil.ALUNO, self.escola_a, self.turma_a)

    def jogar(self, usuario, pontuacao, total=2, obra=None, respostas=(), turma=None):
        resultado = ResultadoQuiz.objects.create(
            perfil=usuario.perfil, turma=turma or usuario.perfil.turma, obra=obra or self.obra,
            pontuacao=pontuacao, total=total, tempo_segundos=60,
        )
        for ordem, (enunciado, correta) in enumerate(respostas, start=1):
            RespostaQuiz.objects.create(
                resultado=resultado, enunciado=enunciado, correta=correta, tempo_segundos=10 * ordem, ordem=ordem
            )
        return resultado


class CalculosDoRelatorioTests(RelatoriosMixin, TestCase):
    def test_resumo_usa_a_primeira_tentativa(self):
        self.jogar(self.aluno_a, 1)  # 50%
        self.jogar(self.aluno_a, 2)  # 100%, repetição
        self.jogar(self.aluno_a3, 2)  # 100%
        EntregaAtividade.objects.create(aluno=self.aluno_a.perfil, obra=self.obra, situacao=EntregaAtividade.ENTREGUE)
        resumo = {linha["obra"].slug: linha for linha in relatorios.resumo_da_turma(self.turma_a.alunos_ativos())}
        self.assertEqual(set(resumo), {"lenda", "negrinho"})  # só obras publicadas
        self.assertEqual(
            (resumo["lenda"]["fizeram"], resumo["lenda"]["total"], resumo["lenda"]["media_primeira"], resumo["lenda"]["entregaram"]),
            (2, 2, 75, 1),
        )
        self.assertIsNone(resumo["negrinho"]["media_primeira"])

    def test_detalhe_por_aluno_e_por_pergunta(self):
        self.jogar(self.aluno_a, 1, respostas=[("P1?", True), ("P2?", False)])
        self.jogar(self.aluno_a, 2, respostas=[("P1?", True), ("P2?", True)])  # repetição não entra nas perguntas
        self.jogar(self.aluno_a3, 0, respostas=[("P1?", False), ("P2?", False)])
        detalhe = relatorios.detalhe_da_obra(self.turma_a.alunos_ativos().order_by("user__username"), self.obra)
        linha = detalhe["linhas"][0]
        self.assertEqual(linha["aluno"], self.aluno_a.perfil)
        self.assertEqual((linha["quiz"]["primeira"].porcentagem, linha["quiz"]["melhor"].porcentagem, linha["quiz"]["quantidade"]), (50, 100, 2))
        self.assertEqual((detalhe["media_primeira"], detalhe["media_melhor"]), (25, 50))
        self.assertEqual([(p["enunciado"], p["certas"], p["respostas"]) for p in detalhe["perguntas"]], [("P1?", 1, 2), ("P2?", 0, 2)])

    def test_aluno_que_veio_de_outra_turma_traz_o_historico(self):
        self.jogar(self.aluno_a2, 2, turma=self.turma_a2)
        self.aluno_a2.perfil.turma = self.turma_a
        self.aluno_a2.perfil.save()
        resumo = {linha["obra"].slug: linha for linha in relatorios.resumo_da_turma(self.turma_a.alunos_ativos())}
        self.assertEqual(resumo["lenda"]["fizeram"], 1)


class TelasDoRelatorioTests(RelatoriosMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.prof_a)

    def test_relatorio_da_turma_resumo_e_detalhe(self):
        self.jogar(self.aluno_a, 1, respostas=[("Quem plantou a erva?", False)])
        url = reverse("escola:turma_relatorio", args=[self.turma_a.pk])
        resposta = self.client.get(url)
        self.assertContains(resposta, "Lenda da Erva-Mate")
        self.assertContains(resposta, "1 de 2")
        self.assertNotContains(resposta, "Rascunho")
        resposta = self.client.get(url, {"obra": "lenda"})
        self.assertContains(resposta, "1/2 (50%)")
        self.assertContains(resposta, "Não fez")  # aluno_a3
        self.assertContains(resposta, "Quem plantou a erva?")
        self.assertNotContains(resposta, "aluno.a2")  # aluno de outra turma

    def test_relatorio_do_aluno(self):
        self.jogar(self.aluno_a, 2, respostas=[("P1?", True)])
        EntregaAtividade.objects.create(
            aluno=self.aluno_a.perfil, obra=self.obra, turma=self.turma_a,
            situacao=EntregaAtividade.ENTREGUE, nota=Decimal("8.5"), observacao="Caprichou",
        )
        resposta = self.client.get(reverse("escola:aluno_relatorio", args=[self.aluno_a.perfil.pk]))
        self.assertContains(resposta, "2 de 2")
        self.assertContains(resposta, "Caprichou")
        self.assertContains(resposta, "8,5")

    def test_isolamento_dos_relatorios(self):
        self.assertEqual(self.client.get(reverse("escola:turma_relatorio", args=[self.turma_a2.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("escola:turma_relatorio", args=[self.turma_b.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("escola:aluno_relatorio", args=[self.aluno_b.perfil.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("escola:atividades_lancar", args=[self.turma_b.pk])).status_code, 404)
        self.client.force_login(self.admin_a)  # admin da escola não vê desempenho
        self.assertEqual(self.client.get(reverse("escola:turma_relatorio", args=[self.turma_a.pk])).status_code, 403)
        self.client.force_login(self.aluno_a)
        self.assertEqual(self.client.get(reverse("escola:aluno_relatorio", args=[self.aluno_a.perfil.pk])).status_code, 403)

    def _dados(self, **por_aluno):
        dados = {}
        for perfil in (self.aluno_a.perfil, self.aluno_a3.perfil):
            situacao, nota, obs = por_aluno.get(perfil.user.username, ("", "", ""))
            dados.update({f"aluno{perfil.pk}-situacao": situacao, f"aluno{perfil.pk}-nota": nota, f"aluno{perfil.pk}-observacao": obs})
        return dados

    def test_lanca_atividade_da_turma(self):
        url = reverse("escola:atividades_lancar", args=[self.turma_a.pk]) + "?obra=lenda"
        self.assertContains(self.client.get(url), "aluno.a3")
        resposta = self.client.post(url, self._dados(**{
            "aluno.a": ("entregue", "9", "Muito bem"), "aluno.a3": ("nao_entregue", "", ""),
        }))
        self.assertRedirects(resposta, reverse("escola:turma_relatorio", args=[self.turma_a.pk]) + "?obra=lenda")
        entrega = EntregaAtividade.objects.get(aluno=self.aluno_a.perfil)
        self.assertEqual((entrega.situacao, entrega.nota, entrega.turma, entrega.registrado_por), ("entregue", Decimal("9"), self.turma_a, self.prof_a))
        self.assertEqual(EntregaAtividade.objects.count(), 2)
        # "—" apaga o lançamento; o outro continua.
        self.client.post(url, self._dados(**{"aluno.a": ("entregue", "9", "Muito bem")}))
        self.assertEqual(list(EntregaAtividade.objects.values_list("aluno__user__username", flat=True)), ["aluno.a"])

    def test_lancamento_invalido_nao_grava_nada(self):
        url = reverse("escola:atividades_lancar", args=[self.turma_a.pk]) + "?obra=lenda"
        resposta = self.client.post(url, self._dados(**{
            "aluno.a": ("entregue", "11", ""), "aluno.a3": ("nao_entregue", "5", ""),
        }))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Não dá para dar nota a quem não entregou.")
        self.assertFalse(EntregaAtividade.objects.exists())

    def test_sem_obra_mostra_a_lista_para_escolher(self):
        resposta = self.client.get(reverse("escola:atividades_lancar", args=[self.turma_a.pk]))
        self.assertContains(resposta, "?obra=lenda")
        self.assertNotContains(resposta, "rascunho")
        resposta = self.client.get(reverse("escola:atividades_lancar", args=[self.turma_a.pk]), {"obra": "rascunho"})
        self.assertNotContains(resposta, "aluno.a3")

    def test_equipe_administrativa_consulta_no_admin(self):
        from django.contrib.auth.models import Group

        equipe = User.objects.create_user("equipe@x.com", is_staff=True)
        equipe.groups.add(Group.objects.get(name="Equipe administrativa"))
        self.client.force_login(equipe)
        self.assertEqual(self.client.get(reverse("admin:escola_entregaatividade_changelist")).status_code, 200)
