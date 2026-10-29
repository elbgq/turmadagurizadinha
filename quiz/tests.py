from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from obras.models import Obra

from .forms import AlternativaQuizFormSet
from contas.models import Perfil

from .models import (
    MENSAGEM_ACIMA_70, MENSAGEM_ATE_50, MENSAGEM_ATE_70, AlternativaQuiz,
    PerguntaQuiz, RespostaQuiz, ResultadoQuiz, formatar_tempo, mensagem_desempenho,
)


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


def criar_pergunta(obra, ordem, enunciado, textos=("Certa", "Errada 1", "Errada 2"), correta=0):
    pergunta = PerguntaQuiz.objects.create(
        obra=obra, ordem=ordem, enunciado=enunciado, explicacao=f"Explicação da {enunciado}"
    )
    alternativas = [
        AlternativaQuiz.objects.create(pergunta=pergunta, texto=texto, correta=(i == correta), ordem=i)
        for i, texto in enumerate(textos)
    ]
    return pergunta, alternativas


class FluxoQuizTests(TestCase):
    """
    Telas do aluno (Fase 7, etapa 2): INICIAR → pergunta → CORRETO/ERRADO
    com explicação → ... → resultado.
    """

    def setUp(self):
        self.obra = Obra.objects.create(titulo="Lenda da Erva-Mate", slug="lenda-da-erva-mate", publicada=True)
        self.p1, self.alts1 = criar_pergunta(self.obra, 1, "Pergunta um?")
        self.p2, self.alts2 = criar_pergunta(self.obra, 2, "Pergunta dois?")
        # Incompleta (só 2 alternativas): fica fora do quiz.
        criar_pergunta(self.obra, 3, "Pergunta incompleta?", textos=("A", "B"))
        self.aluno = User.objects.create_user("aluno", password="senha-teste-123")
        self.client.force_login(self.aluno)

    def _url(self, nome, *args):
        return reverse(f"quiz:{nome}", args=[self.obra.slug, *args])

    def _iniciar(self):
        return self.client.post(self._url("quiz"))

    def test_pagina_inicial_mostra_tema_e_iniciar(self):
        resposta = self.client.get(reverse("obras:obra_quiz", args=[self.obra.slug]))
        self.assertContains(resposta, "Lenda da Erva-Mate")
        self.assertContains(resposta, "INICIAR")
        self.assertContains(resposta, "2 perguntas")

    def test_obra_sem_perguntas_nao_mostra_iniciar(self):
        obra = Obra.objects.create(titulo="Sem quiz", slug="sem-quiz", publicada=True)
        resposta = self.client.get(reverse("obras:obra_quiz", args=[obra.slug]))
        self.assertNotContains(resposta, "INICIAR")
        self.assertContains(resposta, "ainda não tem perguntas")

    def test_iniciar_leva_a_primeira_pergunta(self):
        self.assertRedirects(self._iniciar(), self._url("pergunta", 1))
        resposta = self.client.get(self._url("pergunta", 1))
        self.assertContains(resposta, "Pergunta um?")
        self.assertContains(resposta, "1/2")
        for alternativa in self.alts1:
            self.assertContains(resposta, alternativa.texto)

    def test_resposta_certa_mostra_correto_e_explicacao(self):
        self._iniciar()
        resposta = self.client.post(self._url("pergunta", 1), {"alternativa": self.alts1[0].pk})
        self.assertRedirects(resposta, self._url("resposta", 1))
        resposta = self.client.get(self._url("resposta", 1))
        self.assertContains(resposta, "CORRETO")
        self.assertContains(resposta, "Explicação da Pergunta um?")
        self.assertContains(resposta, self._url("pergunta", 2))

    def test_resposta_errada_mostra_errado_e_a_mesma_explicacao(self):
        self._iniciar()
        self.client.post(self._url("pergunta", 1), {"alternativa": self.alts1[1].pk})
        resposta = self.client.get(self._url("resposta", 1))
        self.assertContains(resposta, "ERRADO")
        self.assertContains(resposta, "Explicação da Pergunta um?")

    def test_nao_da_para_trocar_resposta_ja_dada(self):
        self._iniciar()
        self.client.post(self._url("pergunta", 1), {"alternativa": self.alts1[1].pk})
        self.client.post(self._url("pergunta", 1), {"alternativa": self.alts1[0].pk})
        self.assertContains(self.client.get(self._url("resposta", 1)), "ERRADO")

    def test_nao_da_para_pular_pergunta(self):
        self._iniciar()
        self.assertRedirects(self.client.get(self._url("pergunta", 2)), self._url("pergunta", 1))
        self.assertRedirects(self.client.get(self._url("fim")), self._url("pergunta", 1))

    def test_alternativa_de_outra_pergunta_e_ignorada(self):
        self._iniciar()
        resposta = self.client.post(self._url("pergunta", 1), {"alternativa": self.alts2[0].pk})
        self.assertEqual(resposta.status_code, 200)
        self.assertRedirects(self.client.get(self._url("resposta", 1)), self._url("pergunta", 1))

    def test_fluxo_completo_conta_acertos(self):
        self._iniciar()
        self.client.post(self._url("pergunta", 1), {"alternativa": self.alts1[0].pk})
        self.client.post(self._url("pergunta", 2), {"alternativa": self.alts2[2].pk})
        resposta = self.client.get(self._url("resposta", 2))
        self.assertContains(resposta, self._url("fim"))
        self.assertContains(self.client.get(self._url("fim")), "Tu acertaste 1 de 2")

    def test_jogar_de_novo_zera_a_tentativa(self):
        self._iniciar()
        self.client.post(self._url("pergunta", 1), {"alternativa": self.alts1[0].pk})
        self._iniciar()
        self.assertContains(self.client.get(self._url("pergunta", 1)), "Pergunta um?")

    def test_sem_iniciar_volta_para_a_pagina_inicial(self):
        inicio = reverse("obras:obra_quiz", args=[self.obra.slug])
        self.assertRedirects(self.client.get(self._url("pergunta", 1)), inicio)
        self.assertRedirects(self.client.get(self._url("quiz")), inicio)

    def test_obra_nao_publicada_da_404(self):
        self.obra.publicada = False
        self.obra.save()
        self.assertEqual(self._iniciar().status_code, 404)


class MensagemDesempenhoTests(TestCase):
    """Faixas de 29/10/2026: até 50%, acima de 50% até 70%, acima de 70%."""

    def test_limites_das_faixas(self):
        casos = [
            (0, 6, MENSAGEM_ATE_50), (3, 6, MENSAGEM_ATE_50), (5, 10, MENSAGEM_ATE_50),
            (3, 5, MENSAGEM_ATE_70), (4, 6, MENSAGEM_ATE_70), (7, 10, MENSAGEM_ATE_70),
            (3, 4, MENSAGEM_ACIMA_70), (5, 7, MENSAGEM_ACIMA_70), (6, 6, MENSAGEM_ACIMA_70),
        ]
        for acertos, total, esperada in casos:
            with self.subTest(acertos=acertos, total=total):
                self.assertEqual(mensagem_desempenho(acertos, total), esperada)

    def test_formatar_tempo(self):
        self.assertEqual(formatar_tempo(45), "45 s")
        self.assertEqual(formatar_tempo(90), "1 min 30 s")
        self.assertEqual(formatar_tempo(120), "2 min")


class ResultadoFinalQuizTests(TestCase):
    """Etapa 3: gravação no histórico, mensagem da faixa e visão do professor."""

    def setUp(self):
        self.obra = Obra.objects.create(titulo="Lenda da Erva-Mate", slug="lenda-da-erva-mate", publicada=True)
        self.p1, self.alts1 = criar_pergunta(self.obra, 1, "Pergunta um?")
        self.p2, self.alts2 = criar_pergunta(self.obra, 2, "Pergunta dois?")
        self.aluno = User.objects.create_user("aluno", password="senha-teste-123")
        self.aluno.perfil.tipo = Perfil.ALUNO
        self.aluno.perfil.save()
        self.professor = User.objects.create_user("prof", password="senha-teste-123")
        self.professor.perfil.tipo = Perfil.PROFESSOR
        self.professor.perfil.save()

    def _url(self, nome, *args):
        return reverse(f"quiz:{nome}", args=[self.obra.slug, *args])

    def _jogar(self, usuario, certas=1):
        self.client.force_login(usuario)
        self.client.post(self._url("quiz"))
        self.client.post(self._url("pergunta", 1), {"alternativa": self.alts1[0 if certas >= 1 else 1].pk})
        self.client.post(self._url("pergunta", 2), {"alternativa": self.alts2[0 if certas >= 2 else 1].pk})
        return self.client.get(self._url("fim"))

    def test_grava_resultado_e_respostas_uma_vez_so(self):
        self._jogar(self.aluno)
        self.client.get(self._url("fim"))  # recarregar não duplica
        resultado = ResultadoQuiz.objects.get()
        self.assertEqual((resultado.perfil, resultado.pontuacao, resultado.total), (self.aluno.perfil, 1, 2))
        respostas = list(resultado.respostas.all())
        self.assertEqual([r.correta for r in respostas], [True, False])
        self.assertEqual([r.enunciado for r in respostas], ["Pergunta um?", "Pergunta dois?"])
        self.assertEqual(respostas[1].alternativa, self.alts2[1])

    def test_mostra_mensagem_da_faixa(self):
        self.assertContains(self._jogar(self.aluno, certas=1), "Bah, vivente!")  # 50%
        self.assertContains(self._jogar(self.aluno, certas=2), "Mas barbaridade, tchê!")  # 100%

    def test_aluno_nao_ve_porcentagem(self):
        resposta = self._jogar(self.aluno)
        self.assertContains(resposta, "Tu acertaste 1 de 2")
        self.assertNotContains(resposta, "50%")
        self.assertNotContains(resposta, "Para o professor")

    def test_professor_ve_porcentagem_e_tempo(self):
        resposta = self._jogar(self.professor)
        self.assertContains(resposta, "50%")
        self.assertContains(resposta, "tempo total")
        self.assertContains(resposta, "Pergunta dois?")

    def test_relatorio_lista_so_as_tentativas_da_propria_conta(self):
        self._jogar(self.aluno)
        self._jogar(self.professor, certas=2)
        self.client.force_login(self.aluno)
        resposta = self.client.get(self._url("resultado"))
        self.assertContains(resposta, "1 de 2")
        self.assertNotContains(resposta, "2 de 2")

    def test_relatorio_do_professor_tem_porcentagem_e_detalhe(self):
        self._jogar(self.professor)
        resposta = self.client.get(self._url("resultado"))
        self.assertContains(resposta, "50%")
        self.assertContains(resposta, "Ver pergunta por pergunta")
