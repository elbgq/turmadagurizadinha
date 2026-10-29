from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from obras.models import Obra

from .forms import AlternativaQuizFormSet
from .models import AlternativaQuiz, PerguntaQuiz, RespostaQuiz, ResultadoQuiz


class ResultadoQuizTests(TestCase):
    def test_superusuario_consegue_gravar_resultado(self):
        # Antes do sinal de contas/signals.py, superusuários criados por
        # createsuperuser ficavam sem Perfil e não conseguiam gravar resultado.
        admin = User.objects.create_superuser("admin", password="senha-teste-123")
        obra = Obra.objects.create(titulo="Obra do quiz", slug="obra-do-quiz", publicada=True)

        resultado = ResultadoQuiz.objects.create(
            perfil=admin.perfil, obra=obra, pontuacao=3, total=5, tempo_segundos=90
        )

        self.assertEqual(list(admin.perfil.resultados_quiz.all()), [resultado])


def dados_alternativas(pergunta, alternativas):
    """
    Monta o POST da tela de alternativas: `alternativas` é uma lista de
    (texto, correta); as linhas que sobram até 5 vão em branco, como o
    navegador envia.
    """
    formset = AlternativaQuizFormSet(instance=pergunta)
    prefixo = formset.prefix
    dados = {
        f"{prefixo}-TOTAL_FORMS": "5",
        f"{prefixo}-INITIAL_FORMS": "0",
        f"{prefixo}-MIN_NUM_FORMS": "0",
        f"{prefixo}-MAX_NUM_FORMS": "5",
    }
    for i in range(5):
        texto, correta = alternativas[i] if i < len(alternativas) else ("", False)
        dados[f"{prefixo}-{i}-texto"] = texto
        dados[f"{prefixo}-{i}-ordem"] = "0"
        if correta:
            dados[f"{prefixo}-{i}-correta"] = "on"
    return dados


class AlternativaQuizFormSetTests(TestCase):
    """Regra da cliente (28/10/2026): de 3 a 5 alternativas, uma só correta."""

    def setUp(self):
        obra = Obra.objects.create(titulo="Lenda", slug="lenda")
        self.pergunta = PerguntaQuiz.objects.create(obra=obra, enunciado="Pergunta?", explicacao="Porque sim.")

    def _formset(self, alternativas):
        return AlternativaQuizFormSet(dados_alternativas(self.pergunta, alternativas), instance=self.pergunta)

    def test_tres_alternativas_com_uma_correta_e_valido(self):
        formset = self._formset([("A", True), ("B", False), ("C", False)])
        self.assertTrue(formset.is_valid(), formset.non_form_errors())

    def test_cinco_alternativas_e_valido(self):
        formset = self._formset([("A", False), ("B", False), ("C", True), ("D", False), ("E", False)])
        self.assertTrue(formset.is_valid(), formset.non_form_errors())

    def test_menos_de_tres_alternativas_e_recusado(self):
        formset = self._formset([("A", True), ("B", False)])
        self.assertFalse(formset.is_valid())
        self.assertIn("de 3 a 5 alternativas", formset.non_form_errors()[0])

    def test_nenhuma_correta_e_recusado(self):
        formset = self._formset([("A", False), ("B", False), ("C", False)])
        self.assertFalse(formset.is_valid())
        self.assertIn("exatamente uma", formset.non_form_errors()[0])

    def test_duas_corretas_e_recusado(self):
        formset = self._formset([("A", True), ("B", True), ("C", False)])
        self.assertFalse(formset.is_valid())

    def test_tela_mostra_ate_cinco_linhas(self):
        self.assertEqual(len(AlternativaQuizFormSet(instance=self.pergunta).forms), 5)


class PerguntaQuizModelTests(TestCase):
    def setUp(self):
        self.obra = Obra.objects.create(titulo="Lenda", slug="lenda", imagem_pagina="obras/paginas/lenda.png")
        self.pergunta = PerguntaQuiz.objects.create(obra=self.obra, enunciado="Pergunta?", explicacao="Explicação.")

    def test_sem_imagem_usa_a_imagem_da_obra(self):
        self.assertEqual(self.pergunta.imagem_exibida.name, "obras/paginas/lenda.png")

    def test_com_imagem_propria_usa_a_da_pergunta(self):
        self.pergunta.imagem = "quiz/perguntas/yari.png"
        self.assertEqual(self.pergunta.imagem_exibida.name, "quiz/perguntas/yari.png")

    def test_esta_completa(self):
        self.assertFalse(self.pergunta.esta_completa)
        for i, correta in enumerate([True, False, False]):
            AlternativaQuiz.objects.create(pergunta=self.pergunta, texto=f"Alt {i}", correta=correta)
        self.assertTrue(self.pergunta.esta_completa)

    def test_resposta_continua_no_historico_se_a_pergunta_for_excluida(self):
        usuario = User.objects.create_user("aluno", password="senha-teste-123")
        resultado = ResultadoQuiz.objects.create(
            perfil=usuario.perfil, obra=self.obra, pontuacao=1, total=1, tempo_segundos=30
        )
        RespostaQuiz.objects.create(
            resultado=resultado, pergunta=self.pergunta, enunciado=self.pergunta.enunciado,
            correta=True, tempo_segundos=30,
        )
        self.pergunta.delete()
        resposta = resultado.respostas.get()
        self.assertIsNone(resposta.pergunta)
        self.assertEqual(resposta.enunciado, "Pergunta?")


class CadastroPerguntasQuizTests(TestCase):
    """Telas /quiz/gerenciar/ — só para quem tem permissão (grupo Equipe editorial)."""

    def setUp(self):
        self.obra = Obra.objects.create(titulo="Lenda da Erva-Mate", slug="lenda-da-erva-mate")
        self.aluno = User.objects.create_user("aluno", password="senha-teste-123")
        self.editor = User.objects.create_user("editor", password="senha-teste-123")
        self.editor.groups.add(Group.objects.get(name="Equipe editorial"))
        self.url = reverse("quiz:perguntas_editar", args=[self.obra.pk])

    def test_usuario_sem_permissao_recebe_403(self):
        self.client.force_login(self.aluno)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_equipe_editorial_cadastra_pergunta(self):
        self.client.force_login(self.editor)
        resposta = self.client.post(self.url, {
            "perguntas_quiz-TOTAL_FORMS": "1",
            "perguntas_quiz-INITIAL_FORMS": "0",
            "perguntas_quiz-MIN_NUM_FORMS": "0",
            "perguntas_quiz-MAX_NUM_FORMS": "1000",
            "perguntas_quiz-0-enunciado": "Como Yari ficou conhecida?",
            "perguntas_quiz-0-explicacao": "Yari virou a deusa da erva-mate, Yari-Caá.",
            "perguntas_quiz-0-ordem": "6",
        })
        self.assertRedirects(resposta, self.url)
        self.assertEqual(self.obra.perguntas_quiz.get().enunciado, "Como Yari ficou conhecida?")

    def test_equipe_editorial_salva_alternativas(self):
        pergunta = PerguntaQuiz.objects.create(obra=self.obra, enunciado="Pergunta?", explicacao="Explicação.")
        self.client.force_login(self.editor)
        resposta = self.client.post(
            reverse("quiz:pergunta_alternativas", args=[pergunta.pk]),
            dados_alternativas(pergunta, [("Rainha da Floresta", False), ("Yari-Caá", True), ("Guardiã do Trovão", False)]),
        )
        self.assertRedirects(resposta, self.url)
        self.assertEqual(pergunta.alternativas.count(), 3)
        self.assertTrue(pergunta.esta_completa)

    def test_alternativas_invalidas_mostram_o_erro(self):
        pergunta = PerguntaQuiz.objects.create(obra=self.obra, enunciado="Pergunta?", explicacao="Explicação.")
        self.client.force_login(self.editor)
        resposta = self.client.post(
            reverse("quiz:pergunta_alternativas", args=[pergunta.pk]),
            dados_alternativas(pergunta, [("A", True), ("B", False)]),
        )
        self.assertContains(resposta, "de 3 a 5 alternativas")
        self.assertEqual(pergunta.alternativas.count(), 0)

    def test_link_na_tela_da_obra(self):
        self.editor.user_permissions.add(*Group.objects.get(name="Equipe editorial").permissions.all())
        self.client.force_login(self.editor)
        resposta = self.client.get(reverse("obras:obra_editar", args=[self.obra.pk]))
        self.assertContains(resposta, self.url)
