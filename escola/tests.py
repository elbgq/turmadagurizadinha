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

    def test_admin_da_escola_nao_mexe_em_alunos(self):
        self.assertEqual(self._status(self.admin_a, "turma", self.turma_a.pk), 403)
        self.assertEqual(self._status(self.admin_a, "aluno_editar", self.aluno_a.perfil.pk), 403)
        self.assertEqual(self._status(self.admin_a, "turma_nova"), 403)

    def test_isolamento_entre_escolas_da_404(self):
        self.assertEqual(self._status(self.admin_a, "professor_editar", self.prof_b.perfil.pk), 404)
        self.assertEqual(self._status(self.admin_a, "professor_ativo", self.prof_b.perfil.pk, metodo="post"), 404)
        self.assertEqual(self._status(self.prof_a, "turma", self.turma_b.pk), 404)
        self.assertEqual(self._status(self.prof_a, "aluno_editar", self.aluno_b.perfil.pk), 404)
        self.assertEqual(self._status(self.prof_a, "aluno_nova_senha", self.aluno_b.perfil.pk, metodo="post"), 404)
        self.prof_b.refresh_from_db()
        self.assertTrue(self.prof_b.is_active)

    def test_professor_nao_ve_turma_nem_aluno_do_colega(self):
        self.assertEqual(self._status(self.prof_a, "turma", self.turma_a2.pk), 404)
        self.assertEqual(self._status(self.prof_a, "turma_editar", self.turma_a2.pk), 404)
        self.assertEqual(self._status(self.prof_a, "aluno_ativo", self.aluno_a2.perfil.pk, metodo="post"), 404)
        self.assertEqual(self._status(self.prof_a, "aluno_consentimento", self.aluno_a2.perfil.pk), 404)

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

    def test_ve_turmas_da_escola_sem_alunos(self):
        resposta = self.client.get(reverse("escola:turmas"))
        self.assertContains(resposta, "3º ano A")
        self.assertContains(resposta, "4º ano A")
        self.assertNotContains(resposta, "3º ano B")
        self.assertNotContains(resposta, reverse("escola:turma", args=[self.turma_a.pk]))


class TurmasDoProfessorTests(EscolasMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.prof_a)

    def test_lista_so_as_proprias_turmas(self):
        resposta = self.client.get(reverse("escola:turmas"))
        self.assertContains(resposta, "3º ano A")
        self.assertNotContains(resposta, "4º ano A")

    def test_cria_turma_na_propria_escola(self):
        resposta = self.client.post(reverse("escola:turma_nova"), {"nome": "5º ano C", "ano_letivo": 2027})
        turma = Turma.objects.get(nome="5º ano C")
        self.assertRedirects(resposta, reverse("escola:turma", args=[turma.pk]))
        self.assertEqual((turma.escola, turma.professor), (self.escola_a, self.prof_a.perfil))

    def test_turma_repetida_no_mesmo_ano_e_recusada(self):
        resposta = self.client.post(
            reverse("escola:turma_nova"), {"nome": "4º ANO A", "ano_letivo": self.turma_a2.ano_letivo}
        )
        self.assertContains(resposta, "já tem uma turma com este nome")

    def test_encerra_turma(self):
        url = reverse("escola:turma_editar", args=[self.turma_a.pk])
        self.client.post(url, {"nome": "3º ano A", "ano_letivo": self.turma_a.ano_letivo})
        self.turma_a.refresh_from_db()
        self.assertFalse(self.turma_a.ativa)


class AlunosDoProfessorTests(EscolasMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.prof_a)

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

    def test_cartoes_de_outra_turma_nao_aparecem(self):
        self.client.post(reverse("escola:aluno_novo", args=[self.turma_a.pk]), {"nome": "Maria"})
        outra = Turma.objects.create(escola=self.escola_a, nome="Outra", professor=self.prof_a.perfil)
        resposta = self.client.get(reverse("escola:cartoes", args=[outra.pk]))
        self.assertContains(resposta, "Nenhum cartão para imprimir")

    def test_muda_de_turma_e_o_historico_vai_junto(self):
        outra = Turma.objects.create(escola=self.escola_a, nome="Outra", professor=self.prof_a.perfil)
        obra = Obra.objects.create(titulo="Obra", slug="obra", publicada=True)
        ResultadoQuiz.objects.create(perfil=self.aluno_a.perfil, turma=self.turma_a, obra=obra, pontuacao=1, total=2, tempo_segundos=5)
        url = reverse("escola:aluno_editar", args=[self.aluno_a.perfil.pk])
        self.client.post(url, {"nome": "Aluno A", "turma": outra.pk})
        self.aluno_a.perfil.refresh_from_db()
        self.assertEqual(self.aluno_a.perfil.turma, outra)
        self.assertEqual(self.aluno_a.perfil.resultados_quiz.count(), 1)

    def test_nao_move_aluno_para_turma_do_colega(self):
        url = reverse("escola:aluno_editar", args=[self.aluno_a.perfil.pk])
        resposta = self.client.post(url, {"nome": "Aluno A", "turma": self.turma_a2.pk})
        self.assertEqual(resposta.status_code, 200)
        self.aluno_a.perfil.refresh_from_db()
        self.assertEqual(self.aluno_a.perfil.turma, self.turma_a)

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
        self.assertEqual((consentimento.nome_responsavel, consentimento.registrado_por), ("Maria", self.prof_a))
        self.assertContains(self.client.get(reverse("escola:turma", args=[self.turma_a.pk])), "Sim (Maria)")

    def test_telas_abrem(self):
        for nome, args in [
            ("turmas", []), ("turma_nova", []), ("turma", [self.turma_a.pk]), ("turma_editar", [self.turma_a.pk]),
            ("aluno_novo", [self.turma_a.pk]), ("alunos_lote", [self.turma_a.pk]), ("cartoes", [self.turma_a.pk]),
            ("aluno_editar", [self.aluno_a.perfil.pk]),
        ]:
            with self.subTest(nome):
                self.assertEqual(self.client.get(reverse(f"escola:{nome}", args=args)).status_code, 200)


class EscolaBloqueadaTests(EscolasMixin, TestCase):
    def test_professor_de_escola_vencida_e_desconectado(self):
        from datetime import timedelta

        self.escola_a.contrato_fim = timezone.localdate() - timedelta(days=1)
        self.escola_a.save()
        self.client.force_login(self.prof_a)
        self.assertRedirects(self.client.get(reverse("escola:turmas")), reverse("contas:login"))
