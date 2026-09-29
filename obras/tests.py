import shutil
import tempfile

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import ObraForm, PersonagemATurminhaFormSet, ValorQuemSomosFormSet
from .models import Obra, PaginaATurminha, PaginaQuemSomos

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

    def test_pagina_da_obra_mostra_botao_de_download_so_quando_ha_pdf(self):
        self.client.login(username="aluno", password="senha-teste-123")

        obra_sem_pdf = Obra.objects.create(
            titulo="Sem PDF", slug="pagina-sem-pdf", publicada=True,
        )
        resposta = self.client.get(reverse("obras:detalhe", args=[obra_sem_pdf.slug]))
        self.assertNotContains(resposta, "Baixar atividade")

        obra_com_pdf = self._obra_publicada_com_pdf(slug="pagina-com-pdf")
        resposta = self.client.get(reverse("obras:detalhe", args=[obra_com_pdf.slug]))
        self.assertContains(resposta, "Baixar atividade")


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
