import shutil
import tempfile

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import (
    ObraForm, PersonagemATurminhaFormSet, QuestaoFormSet, TermoGlossarioFormSet,
    ValorQuemSomosFormSet,
)
from .models import Obra, PaginaATurminha, PaginaQuemSomos, TermoGlossario

PDF_MINIMO = b"%PDF-1.4\n%%EOF"

# PNG 1x1 transparente válido — usado nos testes de upload de imagem do
# conteúdo institucional (PaginaQuemSomos/PersonagemATurminha).
PNG_MINIMO = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08"
    b"\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00"
    b"\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

TEMP_MEDIA = tempfile.mkdtemp()


def pdf_upload(nome="atividade.pdf", conteudo=PDF_MINIMO, content_type="application/pdf"):
    return SimpleUploadedFile(nome, conteudo, content_type=content_type)


def png_upload(nome="imagem.png"):
    return SimpleUploadedFile(nome, PNG_MINIMO, content_type="image/png")


def dados_obra_validos(**extras):
    dados = {
        "titulo": "Obra de teste",
        "categoria": "",
        "ilustrador": "",
        "texto_breve": "",
        "texto_completo": "",
        "topicos_resumo": "",
        "tempo_limite_segundos": 600,
        "ordem": 0,
        "publicada": False,
    }
    dados.update(extras)
    return dados


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ObraAtividadePdfTests(TestCase):
    """
    Upload de PDF da "Atividade de apoio" (acréscimo à Fase 6, pedido pela
    cliente em 28/09/2026) — convive com as perguntas cadastradas
    (Questao/Alternativa) e com a impressão delas na página da obra.
    """

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.usuario_comum = User.objects.create_user("aluno", password="senha-teste-123")
        self.usuario_gestor = User.objects.create_user("editor", password="senha-teste-123")
        self.usuario_gestor.user_permissions.add(
            Permission.objects.get(codename="view_obra", content_type__app_label="obras")
        )

    # -- validação do formulário -----------------------------------------

    def test_pdf_valido_e_aceito_pelo_form(self):
        form = ObraForm(
            data=dados_obra_validos(slug="obra-teste-1"),
            files={"atividade_pdf": pdf_upload()},
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_arquivo_txt_e_recusado(self):
        form = ObraForm(
            data=dados_obra_validos(slug="obra-teste-2"),
            files={"atividade_pdf": pdf_upload("atividade.txt", b"so texto", "text/plain")},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("atividade_pdf", form.errors)

    def test_pdf_com_conteudo_invalido_e_recusado(self):
        form = ObraForm(
            data=dados_obra_validos(slug="obra-teste-3"),
            files={"atividade_pdf": pdf_upload(conteudo=b"isto nao e um pdf de verdade")},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("atividade_pdf", form.errors)

    def test_pdf_acima_de_10mb_e_recusado(self):
        conteudo_grande = b"%PDF-1.4\n" + (b"0" * (10 * 1024 * 1024 + 1))
        form = ObraForm(
            data=dados_obra_validos(slug="obra-teste-4"),
            files={"atividade_pdf": pdf_upload(conteudo=conteudo_grande)},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("atividade_pdf", form.errors)

    # -- download protegido ------------------------------------------------

    def _obra_publicada_com_pdf(self, slug="obra-com-pdf"):
        return Obra.objects.create(
            titulo="Obra com PDF", slug=slug, publicada=True,
            atividade_pdf=pdf_upload(),
        )

    def test_download_sem_login_redireciona_para_login(self):
        obra = self._obra_publicada_com_pdf()
        resposta = self.client.get(reverse("obras:atividade_pdf", args=[obra.slug]))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("contas:login"), resposta.url)

    def test_download_logado_recebe_o_pdf_como_anexo(self):
        obra = self._obra_publicada_com_pdf()
        self.client.login(username="aluno", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:atividade_pdf", args=[obra.slug]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "application/pdf")
        self.assertIn("attachment", resposta["Content-Disposition"])
        self.assertIn(f"{obra.slug}-atividade.pdf", resposta["Content-Disposition"])

    def test_obra_sem_pdf_da_404(self):
        obra = Obra.objects.create(titulo="Sem PDF", slug="obra-sem-pdf", publicada=True)
        self.client.login(username="aluno", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:atividade_pdf", args=[obra.slug]))
        self.assertEqual(resposta.status_code, 404)

    def test_obra_nao_publicada_da_404_para_usuario_comum(self):
        obra = Obra.objects.create(
            titulo="Rascunho", slug="obra-rascunho", publicada=False,
            atividade_pdf=pdf_upload(),
        )
        self.client.login(username="aluno", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:atividade_pdf", args=[obra.slug]))
        self.assertEqual(resposta.status_code, 404)

    def test_obra_nao_publicada_e_liberada_para_quem_tem_view_obra(self):
        obra = Obra.objects.create(
            titulo="Rascunho", slug="obra-rascunho-2", publicada=False,
            atividade_pdf=pdf_upload(),
        )
        self.client.login(username="editor", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:atividade_pdf", args=[obra.slug]))
        self.assertEqual(resposta.status_code, 200)

    # -- limpeza de arquivos no storage ------------------------------------

    def test_trocar_o_pdf_apaga_o_arquivo_antigo(self):
        obra = self._obra_publicada_com_pdf(slug="obra-troca-pdf")
        caminho_antigo = obra.atividade_pdf.path
        self.assertTrue(obra.atividade_pdf.storage.exists(caminho_antigo))

        obra.atividade_pdf = pdf_upload("nova.pdf")
        obra.save()

        self.assertFalse(obra.atividade_pdf.storage.exists(caminho_antigo))

    def test_limpar_o_pdf_apaga_o_arquivo(self):
        obra = self._obra_publicada_com_pdf(slug="obra-limpa-pdf")
        caminho = obra.atividade_pdf.path

        obra.atividade_pdf = None
        obra.save()

        self.assertFalse(obra.atividade_pdf.storage.exists(caminho))

    def test_excluir_a_obra_apaga_o_arquivo(self):
        obra = self._obra_publicada_com_pdf(slug="obra-excluir-pdf")
        storage = obra.atividade_pdf.storage
        caminho = obra.atividade_pdf.path

        obra.delete()

        self.assertFalse(storage.exists(caminho))

    # -- página da obra ------------------------------------------------------

    def test_pagina_de_atividade_mostra_botao_de_download_so_quando_ha_pdf(self):
        # Acréscimo de 01/10/2026: Atividade passou a ter rota própria
        # (obras:obra_atividade), em vez de uma seção dentro de
        # obras:detalhe — ver obras/views.py.
        self.client.login(username="aluno", password="senha-teste-123")

        obra_sem_pdf = Obra.objects.create(
            titulo="Sem PDF", slug="pagina-sem-pdf", publicada=True,
        )
        resposta = self.client.get(reverse("obras:obra_atividade", args=[obra_sem_pdf.slug]))
        self.assertNotContains(resposta, "Baixar Atividade de Apoio")

        obra_com_pdf = self._obra_publicada_com_pdf(slug="pagina-com-pdf")
        resposta = self.client.get(reverse("obras:obra_atividade", args=[obra_com_pdf.slug]))
        self.assertContains(resposta, "Baixar Atividade de Apoio")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ConteudoInstitucionalTests(TestCase):
    """
    Conteúdo editável de "Quem somos" e "A Turminha" pela equipe
    editorial, sem depender do desenvolvedor (acréscimo de 29/09/2026,
    pedido da cliente) — ver PaginaQuemSomos/ValorQuemSomos/
    PaginaATurminha/PersonagemATurminha em models.py. A migration 0007
    já semeia uma linha de cada página no banco (mesmo texto que antes
    estava fixo nos templates), então os testes partem desse conteúdo.
    """

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.usuario_comum = User.objects.create_user("aluno-institucional", password="senha-teste-123")
        self.usuario_editor = User.objects.create_user("editor-institucional", password="senha-teste-123")
        self.usuario_editor.user_permissions.add(
            Permission.objects.get(codename="change_paginaquemsomos", content_type__app_label="obras"),
            Permission.objects.get(codename="change_paginaaturminha", content_type__app_label="obras"),
        )

    def _dados_management_form(self, formset):
        return {
            f"{formset.prefix}-TOTAL_FORMS": str(formset.total_form_count()),
            f"{formset.prefix}-INITIAL_FORMS": str(formset.initial_form_count()),
            f"{formset.prefix}-MIN_NUM_FORMS": "0",
            f"{formset.prefix}-MAX_NUM_FORMS": "1000",
        }

    def _dados_formset_existente(self, formset, campos):
        """Reaproduz, sem alterar, os dados de cada form já existente no formset."""
        dados = {}
        for i, form in enumerate(formset.forms):
            if not form.instance.pk:
                continue
            dados[f"{formset.prefix}-{i}-id"] = str(form.instance.pk)
            for campo in campos:
                dados[f"{formset.prefix}-{i}-{campo}"] = str(getattr(form.instance, campo))
        return dados

    # -- acesso às telas de edição (permissão obras.change_pagina*) --------

    def test_edicao_quem_somos_exige_login(self):
        resposta = self.client.get(reverse("obras:quem_somos_editar"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("contas:login"), resposta.url)

    def test_edicao_quem_somos_403_sem_permissao(self):
        self.client.login(username="aluno-institucional", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:quem_somos_editar"))
        self.assertEqual(resposta.status_code, 403)

    def test_edicao_quem_somos_ok_com_permissao(self):
        self.client.login(username="editor-institucional", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:quem_somos_editar"))
        self.assertEqual(resposta.status_code, 200)

    def test_edicao_a_turminha_403_sem_permissao(self):
        self.client.login(username="aluno-institucional", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:a_turminha_editar"))
        self.assertEqual(resposta.status_code, 403)

    def test_edicao_a_turminha_ok_com_permissao(self):
        self.client.login(username="editor-institucional", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:a_turminha_editar"))
        self.assertEqual(resposta.status_code, 200)

    # -- páginas públicas mostram o conteúdo do banco (semeado pela 0007) --
    # (login continua obrigatório em todo o site — LoginRequiredMiddleware.)

    def test_pagina_quem_somos_mostra_texto_e_valores_do_banco(self):
        self.client.login(username="aluno-institucional", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:quem_somos"))
        self.assertContains(resposta, "Agudo")
        self.assertContains(resposta, "Aprender é tri")

    def test_pagina_a_turminha_mostra_personagens_do_banco(self):
        self.client.login(username="aluno-institucional", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:a_turminha"))
        self.assertContains(resposta, "Guri")
        self.assertContains(resposta, "Cícero")

    def test_link_editar_so_aparece_para_quem_tem_permissao(self):
        self.client.login(username="aluno-institucional", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:quem_somos"))
        self.assertNotContains(resposta, "Editar esta página")

        self.client.login(username="editor-institucional", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:quem_somos"))
        self.assertContains(resposta, "Editar esta página")

    # -- salvar o formulário: texto, lista editável e upload de imagem -----

    def test_salvar_quem_somos_atualiza_texto_e_adiciona_valor(self):
        self.client.login(username="editor-institucional", password="senha-teste-123")
        pagina = PaginaQuemSomos.objects.get(pk=1)
        formset = ValorQuemSomosFormSet(instance=pagina)

        dados = {"historia_texto": pagina.historia_texto, "missao_texto": "Missão atualizada pelo teste", "visao_texto": pagina.visao_texto}
        dados.update(self._dados_management_form(formset))
        dados.update(self._dados_formset_existente(formset, ["titulo", "tema", "texto", "ordem"]))
        novo_indice = formset.total_form_count() - 1
        dados[f"valores-{novo_indice}-titulo"] = "Valor novo do teste"
        dados[f"valores-{novo_indice}-tema"] = "teste"
        dados[f"valores-{novo_indice}-texto"] = "Texto do valor novo."
        dados[f"valores-{novo_indice}-ordem"] = "6"

        resposta = self.client.post(reverse("obras:quem_somos_editar"), data=dados)
        self.assertEqual(resposta.status_code, 302, getattr(resposta, "context", None) and resposta.context["form"].errors)

        pagina.refresh_from_db()
        self.assertEqual(pagina.missao_texto, "Missão atualizada pelo teste")
        self.assertEqual(pagina.valores.count(), 7)
        self.assertTrue(pagina.valores.filter(titulo="Valor novo do teste").exists())

    def test_salvar_quem_somos_com_imagem_nova(self):
        self.client.login(username="editor-institucional", password="senha-teste-123")
        pagina = PaginaQuemSomos.objects.get(pk=1)
        formset = ValorQuemSomosFormSet(instance=pagina)

        dados = {"historia_texto": pagina.historia_texto, "missao_texto": pagina.missao_texto, "visao_texto": pagina.visao_texto}
        dados.update(self._dados_management_form(formset))
        dados.update(self._dados_formset_existente(formset, ["titulo", "tema", "texto", "ordem"]))
        # Form extra (índice 6, ainda em branco) — precisa reproduzir os
        # mesmos valores que o navegador enviaria (inclui "ordem": "0",
        # valor padrão do model) para o Django não interpretá-lo como
        # alterado e cobrar os campos obrigatórios.
        indice_extra = formset.total_form_count() - 1
        dados[f"valores-{indice_extra}-titulo"] = ""
        dados[f"valores-{indice_extra}-tema"] = ""
        dados[f"valores-{indice_extra}-texto"] = ""
        dados[f"valores-{indice_extra}-ordem"] = "0"
        # O client de teste do Django não tem um parâmetro "files" à parte
        # (isso é convenção de outras libs) — o arquivo entra junto no
        # próprio dicionário "data", como o navegador faria num POST
        # multipart/form-data.
        dados["historia_imagem"] = png_upload()

        resposta = self.client.post(reverse("obras:quem_somos_editar"), data=dados)
        self.assertEqual(
            resposta.status_code, 302,
            resposta.context["formset"].errors if resposta.status_code == 200 else None,
        )
        pagina.refresh_from_db()
        self.assertIn("imagem", pagina.historia_imagem.name)

    def test_salvar_a_turminha_atualiza_personagem_e_permite_excluir(self):
        self.client.login(username="editor-institucional", password="senha-teste-123")
        pagina = PaginaATurminha.objects.get(pk=1)
        formset = PersonagemATurminhaFormSet(instance=pagina)
        # Último personagem JÁ EXISTENTE (não o form extra em branco no
        # final da lista) — os 4 semeados pela migration são Guri,
        # Cícero, Germano e Catarina, nessa ordem.
        ultimo_indice = formset.initial_form_count() - 1
        personagem_a_excluir = formset.forms[ultimo_indice].instance

        dados = {"texto_introducao": pagina.texto_introducao}
        dados.update(self._dados_management_form(formset))
        dados.update(self._dados_formset_existente(formset, ["nome", "texto", "ordem"]))
        # Form extra em branco — mesma lógica do teste de imagem acima.
        indice_extra = formset.total_form_count() - 1
        dados[f"personagens-{indice_extra}-nome"] = ""
        dados[f"personagens-{indice_extra}-texto"] = ""
        dados[f"personagens-{indice_extra}-ordem"] = "0"
        # Marca o último personagem (Catarina) para exclusão.
        dados[f"personagens-{ultimo_indice}-DELETE"] = "on"
        # Altera o texto do primeiro personagem (Guri).
        dados["personagens-0-texto"] = "Texto do Guri atualizado pelo teste."

        resposta = self.client.post(reverse("obras:a_turminha_editar"), data=dados)
        self.assertEqual(
            resposta.status_code, 302,
            resposta.context["formset"].errors if resposta.status_code == 200 else None,
        )

        pagina.refresh_from_db()
        self.assertEqual(pagina.personagens.count(), 3)
        self.assertFalse(pagina.personagens.filter(pk=personagem_a_excluir.pk).exists())
        self.assertTrue(pagina.personagens.filter(nome="Guri", texto="Texto do Guri atualizado pelo teste.").exists())


# --------------------------------------------------------------------
# Acréscimo acordado em reunião com a cliente de 01/10/2026: Resumo
# (texto + PDF opcional), Resumo/Atividade/Quiz com rota e template
# próprios (antes eram seções dentro de obras/detalhe.html), e Glossário
# Gauchês (lista estruturada TermoGlossario), em destaque na página da
# obra. Ver obras/models.py, obras/forms.py, obras/views.py e
# obras/urls.py.
# --------------------------------------------------------------------


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ObraResumoPdfTests(TestCase):
    """Upload e download do PDF de "Resumo para o professor" — mesmo padrão de atividade_pdf."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.usuario_comum = User.objects.create_user("aluno-resumo", password="senha-teste-123")

    def test_resumo_pdf_valido_e_aceito_pelo_form(self):
        form = ObraForm(
            data=dados_obra_validos(slug="obra-resumo-1"),
            files={"resumo_pdf": pdf_upload("resumo.pdf")},
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_resumo_pdf_com_conteudo_invalido_e_recusado(self):
        form = ObraForm(
            data=dados_obra_validos(slug="obra-resumo-2"),
            files={"resumo_pdf": pdf_upload("resumo.pdf", conteudo=b"isto nao e um pdf de verdade")},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("resumo_pdf", form.errors)

    def _obra_publicada_com_resumo_pdf(self, slug="obra-com-resumo-pdf"):
        return Obra.objects.create(
            titulo="Obra com resumo em PDF", slug=slug, publicada=True,
            resumo_pdf=pdf_upload("resumo.pdf"),
        )

    def test_download_sem_login_redireciona_para_login(self):
        obra = self._obra_publicada_com_resumo_pdf()
        resposta = self.client.get(reverse("obras:resumo_pdf", args=[obra.slug]))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("contas:login"), resposta.url)

    def test_download_logado_recebe_o_pdf_como_anexo(self):
        obra = self._obra_publicada_com_resumo_pdf()
        self.client.login(username="aluno-resumo", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:resumo_pdf", args=[obra.slug]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "application/pdf")
        self.assertIn(f"{obra.slug}-resumo.pdf", resposta["Content-Disposition"])

    def test_obra_sem_resumo_pdf_da_404(self):
        obra = Obra.objects.create(titulo="Sem resumo em PDF", slug="obra-sem-resumo-pdf", publicada=True)
        self.client.login(username="aluno-resumo", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:resumo_pdf", args=[obra.slug]))
        self.assertEqual(resposta.status_code, 404)


class ObraRotasSeparadasTests(TestCase):
    """
    Resumo, Atividade e Quiz Interativo em rotas e templates próprios
    (decisão da cliente em 01/10/2026: mudar de abas/accordion na mesma
    página para rotas separadas).
    """

    def setUp(self):
        self.usuario = User.objects.create_user("aluno-rotas", password="senha-teste-123")
        self.obra = Obra.objects.create(
            titulo="Obra com rotas", slug="obra-com-rotas", publicada=True,
            topicos_resumo="Tópico 1 para o professor.",
            texto_completo="Era uma vez...",
        )
        self.questao = self.obra.questoes.create(enunciado="Pergunta de teste?", ordem=0)
        self.questao.alternativas.create(texto="Resposta A", correta=True)
        self.client.login(username="aluno-rotas", password="senha-teste-123")

    def test_resumo_requer_login(self):
        self.client.logout()
        resposta = self.client.get(reverse("obras:obra_resumo", args=[self.obra.slug]))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("contas:login"), resposta.url)

    def test_resumo_mostra_topicos_resumo(self):
        resposta = self.client.get(reverse("obras:obra_resumo", args=[self.obra.slug]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Tópico 1 para o professor.")

    def test_resumo_mostra_cada_linha_como_topico_sem_marcador(self):
        # Layout de 02/10/2026: cada linha de topicos_resumo vira um <li>
        # no quadro do Resumo; o "- " digitado pela equipe sai, e linhas
        # vazias ou só com o marcador são ignoradas.
        self.obra.topicos_resumo = "- Primeiro tópico;\r\n\r\n-\r\n• Segundo tópico."
        self.obra.save()
        self.assertEqual(self.obra.topicos_resumo_lista, ["Primeiro tópico;", "Segundo tópico."])
        resposta = self.client.get(reverse("obras:obra_resumo", args=[self.obra.slug]))
        self.assertContains(resposta, "<li>Primeiro tópico;</li>", html=True)
        self.assertContains(resposta, "<li>Segundo tópico.</li>", html=True)

    def test_atividade_mostra_pergunta_cadastrada(self):
        resposta = self.client.get(reverse("obras:obra_atividade", args=[self.obra.slug]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Pergunta de teste?")
        # Sem gabarito no HTML — o texto da alternativa aparece, mas não
        # há indicação de qual é a correta.
        self.assertContains(resposta, "Resposta A")

    def test_quiz_mostra_links_para_a_logica_da_fase_7(self):
        resposta = self.client.get(reverse("obras:obra_quiz", args=[self.obra.slug]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, reverse("quiz:quiz", args=[self.obra.slug]))
        self.assertContains(resposta, reverse("quiz:resultado", args=[self.obra.slug]))

    def test_detalhe_nao_mostra_mais_a_pergunta_nem_o_texto_de_resumo(self):
        # Perguntas e tópicos de resumo saíram de obras:detalhe — agora
        # moram em obra_atividade/obra_resumo, cada um na sua própria rota.
        resposta = self.client.get(reverse("obras:detalhe", args=[self.obra.slug]))
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, "Pergunta de teste?")
        self.assertNotContains(resposta, "Tópico 1 para o professor.")

    def test_detalhe_mostra_links_de_navegacao(self):
        resposta = self.client.get(reverse("obras:detalhe", args=[self.obra.slug]))
        self.assertContains(resposta, reverse("obras:obra_resumo", args=[self.obra.slug]))
        self.assertContains(resposta, reverse("obras:obra_atividade", args=[self.obra.slug]))
        self.assertContains(resposta, reverse("obras:obra_quiz", args=[self.obra.slug]))


class TermoGlossarioTests(TestCase):
    """
    Glossário Gauchês — lista estruturada (TermoGlossario), em destaque,
    fora do texto, na página da obra; editável pela equipe editorial via
    formset inline na tela de gestão (decisão da cliente em 01/10/2026).
    """

    def setUp(self):
        self.usuario = User.objects.create_user("aluno-glossario", password="senha-teste-123")
        self.usuario_editor = User.objects.create_user("editor-glossario", password="senha-teste-123")
        self.usuario_editor.user_permissions.add(
            Permission.objects.get(codename="change_obra", content_type__app_label="obras")
        )
        self.obra = Obra.objects.create(
            titulo="Obra com glossário", slug="obra-com-glossario", publicada=True,
        )

    def _dados_management_form(self, formset):
        return {
            f"{formset.prefix}-TOTAL_FORMS": str(formset.total_form_count()),
            f"{formset.prefix}-INITIAL_FORMS": str(formset.initial_form_count()),
            f"{formset.prefix}-MIN_NUM_FORMS": "0",
            f"{formset.prefix}-MAX_NUM_FORMS": "1000",
        }

    def test_pagina_da_obra_nao_mostra_glossario_quando_vazio(self):
        self.client.login(username="aluno-glossario", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:detalhe", args=[self.obra.slug]))
        self.assertNotContains(resposta, "Glossário Gauchês")

    def test_pagina_da_obra_mostra_termos_do_glossario_em_destaque(self):
        self.obra.termos_glossario.create(termo="Bah", definicao="Interjeição gaúcha de uso geral.", ordem=0)
        self.client.login(username="aluno-glossario", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:detalhe", args=[self.obra.slug]))
        self.assertContains(resposta, "Glossário Gauchês")
        self.assertContains(resposta, "Bah")
        self.assertContains(resposta, "Interjeição gaúcha de uso geral.")

    def test_adicionar_termo_via_formset_na_tela_de_gestao(self):
        self.client.login(username="editor-glossario", password="senha-teste-123")
        formset = TermoGlossarioFormSet(instance=self.obra, prefix="glossario")
        formset_questoes = QuestaoFormSet(instance=self.obra)

        dados = dados_obra_validos(slug=self.obra.slug, titulo=self.obra.titulo)
        dados.update(self._dados_management_form(formset))
        dados.update(self._dados_management_form(formset_questoes))
        # Form extra (em branco) do QuestaoFormSet — mesma lógica já usada
        # em ConteudoInstitucionalTests: reproduzir os valores em branco
        # que o navegador enviaria, senão o Django cobra os campos
        # obrigatórios de um form "alterado".
        indice_questao_extra = formset_questoes.total_form_count() - 1
        dados[f"{formset_questoes.prefix}-{indice_questao_extra}-enunciado"] = ""
        dados[f"{formset_questoes.prefix}-{indice_questao_extra}-ordem"] = "0"
        # Com `extra=10` no TermoGlossarioFormSet (01/10/2026 — dá pra
        # preencher vários termos de uma vez), as linhas extras não usadas
        # precisam reproduzir o que o navegador de fato envia: o campo
        # "ordem" de cada linha em branco já vem preenchido com o valor
        # padrão do model (0), não ausente do POST — se o teste omitisse
        # essas chaves, o Django veria uma "mudança" espúria (0 vs string
        # vazia) e cobraria termo/definição como obrigatórios à toa.
        novo_indice = formset.total_form_count() - 1
        for indice in range(novo_indice):
            dados[f"glossario-{indice}-termo"] = ""
            dados[f"glossario-{indice}-definicao"] = ""
            dados[f"glossario-{indice}-ordem"] = "0"
        dados[f"glossario-{novo_indice}-termo"] = "Tchê"
        dados[f"glossario-{novo_indice}-definicao"] = "Forma de tratamento, equivalente a 'cara' ou 'amigo'."
        dados[f"glossario-{novo_indice}-ordem"] = "0"

        resposta = self.client.post(reverse("obras:obra_editar", args=[self.obra.pk]), data=dados)
        self.assertEqual(
            resposta.status_code, 302,
            resposta.context["glossario_formset"].errors if resposta.status_code == 200 else None,
        )
        self.assertEqual(self.obra.termos_glossario.count(), 1)
        self.assertTrue(self.obra.termos_glossario.filter(termo="Tchê").exists())

    def test_excluir_termo_via_formset_na_tela_de_gestao(self):
        termo = self.obra.termos_glossario.create(termo="Guasca", definicao="Tira de couro cru.", ordem=0)
        self.client.login(username="editor-glossario", password="senha-teste-123")
        formset = TermoGlossarioFormSet(instance=self.obra, prefix="glossario")
        formset_questoes = QuestaoFormSet(instance=self.obra)

        dados = dados_obra_validos(slug=self.obra.slug, titulo=self.obra.titulo)
        dados.update(self._dados_management_form(formset))
        dados.update(self._dados_management_form(formset_questoes))
        indice_questao_extra = formset_questoes.total_form_count() - 1
        dados[f"{formset_questoes.prefix}-{indice_questao_extra}-enunciado"] = ""
        dados[f"{formset_questoes.prefix}-{indice_questao_extra}-ordem"] = "0"
        dados[f"glossario-0-id"] = str(termo.pk)
        dados[f"glossario-0-termo"] = termo.termo
        dados[f"glossario-0-definicao"] = termo.definicao
        dados[f"glossario-0-ordem"] = str(termo.ordem)
        dados[f"glossario-0-DELETE"] = "on"
        # Linhas extras em branco (ver comentário equivalente no teste
        # acima) — reproduz o valor padrão que o navegador já envia.
        novo_indice = formset.total_form_count() - 1
        for indice in range(formset.initial_form_count(), novo_indice + 1):
            dados[f"glossario-{indice}-termo"] = ""
            dados[f"glossario-{indice}-definicao"] = ""
            dados[f"glossario-{indice}-ordem"] = "0"

        resposta = self.client.post(reverse("obras:obra_editar", args=[self.obra.pk]), data=dados)
        self.assertEqual(
            resposta.status_code, 302,
            resposta.context["glossario_formset"].errors if resposta.status_code == 200 else None,
        )
        self.assertFalse(self.obra.termos_glossario.filter(pk=termo.pk).exists())


class ObraListaPublicaEBuscaTests(TestCase):
    """
    "Lista de obras" pública + campo de busca (texto/categoria) + ajuste
    de colunas em "Gerenciar obras" — acréscimo da reunião de 01/10/2026,
    itens 3 e 4 (ver README.md), confirmados com o usuário em 01/10/2026:
    link único na navbar que muda de nome/destino conforme a permissão,
    busca por GET (?q=...&categoria=...) compartilhada pelas duas telas,
    e "Publicada" só aparece em "Gerenciar obras" (redundante na pública,
    que só lista obras já publicadas).
    """

    def setUp(self):
        self.usuario_comum = User.objects.create_user("aluno-lista", password="senha-teste-123")
        self.usuario_gestor = User.objects.create_user("editor-lista", password="senha-teste-123")
        for codename in ("view_obra", "change_obra", "delete_obra"):
            self.usuario_gestor.user_permissions.add(
                Permission.objects.get(codename=codename, content_type__app_label="obras")
            )

        self.obra_publicada = Obra.objects.create(
            titulo="Lenda da Erva-Mate", slug="lenda-erva-mate-lista",
            categoria=Obra.Categoria.LENDAS_GAUCHAS, publicada=True,
        )
        self.obra_rascunho = Obra.objects.create(
            titulo="Obra ainda não publicada", slug="obra-rascunho-lista",
            categoria=Obra.Categoria.BIOMA, publicada=False,
        )

    # --- Acesso ---

    def test_lista_publica_requer_login(self):
        resposta = self.client.get(reverse("obras:obra_lista_publica"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("contas:login"), resposta.url)

    def test_lista_publica_acessivel_a_qualquer_usuario_logado_sem_permissao_especial(self):
        self.client.login(username="aluno-lista", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:obra_lista_publica"))
        self.assertEqual(resposta.status_code, 200)

    def test_gerenciar_obras_continua_exigindo_permissao(self):
        self.client.login(username="aluno-lista", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:obra_lista"))
        self.assertEqual(resposta.status_code, 403)

    # --- Conteúdo/colunas ---

    def test_lista_publica_mostra_so_obras_publicadas(self):
        self.client.login(username="aluno-lista", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:obra_lista_publica"))
        self.assertContains(resposta, "Lenda da Erva-Mate")
        self.assertNotContains(resposta, "Obra ainda não publicada")

    def test_lista_publica_nao_mostra_coluna_publicada_nem_acoes_de_gestao(self):
        self.client.login(username="aluno-lista", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:obra_lista_publica"))
        self.assertNotContains(resposta, "<th>Publicada</th>", html=False)
        self.assertNotContains(resposta, "Editar")
        self.assertNotContains(resposta, "Excluir")
        self.assertContains(resposta, "Acessar Obra")

    def test_lista_publica_mostra_categoria_e_nao_mostra_ordem(self):
        self.client.login(username="aluno-lista", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:obra_lista_publica"))
        self.assertContains(resposta, "<th>Categoria</th>", html=False)
        self.assertNotContains(resposta, "<th>Ordem</th>", html=False)

    def test_gerenciar_obras_mostra_publicada_e_categoria_mas_nao_ordem(self):
        self.client.login(username="editor-lista", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:obra_lista"))
        self.assertContains(resposta, "<th>Publicada</th>", html=False)
        self.assertContains(resposta, "<th>Categoria</th>", html=False)
        self.assertNotContains(resposta, "<th>Ordem</th>", html=False)
        # continua mostrando as duas obras, publicada ou não
        self.assertContains(resposta, "Lenda da Erva-Mate")
        self.assertContains(resposta, "Obra ainda não publicada")

    # --- Busca ---

    def test_busca_por_titulo_na_lista_publica(self):
        self.client.login(username="aluno-lista", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:obra_lista_publica"), {"q": "Erva-Mate"})
        self.assertContains(resposta, "Lenda da Erva-Mate")

    def test_busca_por_titulo_sem_resultado_na_lista_publica(self):
        self.client.login(username="aluno-lista", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:obra_lista_publica"), {"q": "Não existe"})
        self.assertNotContains(resposta, "Lenda da Erva-Mate")
        self.assertContains(resposta, "Nenhuma obra encontrada.")

    def test_busca_por_categoria_na_lista_publica(self):
        self.client.login(username="aluno-lista", password="senha-teste-123")
        resposta = self.client.get(
            reverse("obras:obra_lista_publica"), {"categoria": Obra.Categoria.BIOMA}
        )
        # obra_rascunho é Bioma mas não publicada — não deve aparecer aqui;
        # nenhuma obra publicada é Bioma neste teste, então a lista fica vazia.
        self.assertNotContains(resposta, "Lenda da Erva-Mate")
        self.assertContains(resposta, "Nenhuma obra encontrada.")

    def test_busca_por_categoria_em_gerenciar_obras(self):
        self.client.login(username="editor-lista", password="senha-teste-123")
        resposta = self.client.get(
            reverse("obras:obra_lista"), {"categoria": Obra.Categoria.LENDAS_GAUCHAS}
        )
        self.assertContains(resposta, "Lenda da Erva-Mate")
        self.assertNotContains(resposta, "Obra ainda não publicada")

    # --- Navbar ---

    def test_navbar_mostra_gerenciar_obras_para_quem_tem_permissao(self):
        self.client.login(username="editor-lista", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:home"))
        self.assertContains(resposta, "Gerenciar obras")
        self.assertContains(resposta, reverse("obras:obra_lista"))
        self.assertNotContains(resposta, reverse("obras:obra_lista_publica"))

    def test_navbar_mostra_lista_de_obras_para_usuario_comum(self):
        self.client.login(username="aluno-lista", password="senha-teste-123")
        resposta = self.client.get(reverse("obras:home"))
        self.assertContains(resposta, "Lista de obras")
        self.assertContains(resposta, reverse("obras:obra_lista_publica"))
        self.assertNotContains(resposta, ">Gerenciar obras<")
