import logging
import shutil
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import path, reverse

from config.urls import urlpatterns as urlpatterns_do_site

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class MediaEmProducaoTests(TestCase):
    """
    Fase 10: os uploads (media/) continuam acessíveis com DEBUG=False (o
    `static()` do Django só serve com DEBUG=True), mas só para quem está
    logado — o LoginRequiredMiddleware vale também para eles.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (Path(TEMP_MEDIA) / "ilustracao.txt").write_text("conteudo de teste")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def test_visitante_nao_logado_e_redirecionado_ao_login(self):
        resposta = self.client.get("/media/ilustracao.txt")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/contas/", resposta["Location"])

    def test_usuario_logado_recebe_o_arquivo(self):
        self.client.force_login(User.objects.create_user("aluno", password="x"))
        resposta = self.client.get("/media/ilustracao.txt")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(b"".join(resposta.streaming_content), "conteudo de teste".encode()) # type: ignore

    def test_arquivo_inexistente_retorna_404(self):
        self.client.force_login(User.objects.create_user("aluno", password="x"))
        self.assertEqual(self.client.get("/media/nao-existe.png").status_code, 404)


# --------------------------------------------------------------------
# Revisão de 07/11/2026 (antes da publicação)
# --------------------------------------------------------------------


def _view_que_quebra(request):
    raise RuntimeError("erro de teste")


# Rotas do site + uma que sempre dá erro, para testar o erro 500 (usadas
# com override_settings(ROOT_URLCONF="config.tests")).
urlpatterns = urlpatterns_do_site + [path("teste-erro-500/", _view_que_quebra)]


@override_settings(ROOT_URLCONF="config.tests")
class Erro500Tests(TestCase):
    """Itens 1 e 6: o erro 500 fica no log e mostra a página própria."""

    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.client.force_login(User.objects.create_user("aluno", password="x"))

    def _console_do_django(self):
        return next(
            h for h in logging.getLogger("django").handlers
            if type(h) is logging.StreamHandler
        )

    def test_erro_500_e_registrado_no_log(self):
        console = self._console_do_django()
        saida = StringIO()
        antiga = console.setStream(saida)
        try:
            self.client.get("/teste-erro-500/")
        finally:
            console.setStream(antiga)
        self.assertIn("erro de teste", saida.getvalue())

    def test_pagina_500_propria(self):
        console = self._console_do_django()
        antiga = console.setStream(StringIO())
        try:
            resposta = self.client.get("/teste-erro-500/")
        finally:
            console.setStream(antiga)
        self.assertEqual(resposta.status_code, 500)
        self.assertContains(resposta, "Algo deu errado por aqui", status_code=500)


class PaginasDeErroTests(TestCase):
    """Item 6: 404, 403 e formulário expirado em português, no visual do site."""

    def setUp(self):
        self.client.force_login(User.objects.create_user("aluno", password="x"))

    def test_404(self):
        resposta = self.client.get("/obra/nao-existe/")
        self.assertContains(resposta, "essa página não existe", status_code=404)

    def test_403(self):
        resposta = self.client.get(reverse("obras:obra_lista"))
        self.assertContains(resposta, "Acesso não permitido", status_code=403)

    def test_formulario_expirado(self):
        cliente = Client(enforce_csrf_checks=True)
        with self.assertLogs("django.security.csrf", "WARNING"):
            resposta = cliente.post(reverse("contas:login"), {"username": "a", "password": "b"})
        self.assertContains(resposta, "O formulário expirou", status_code=403)


class CssSemParametroEmProducaoTests(TestCase):
    """Item 7: sem o ?v= a cada acesso, o navegador guarda o CSS em cache."""

    def test_css_sem_timestamp_com_debug_desligado(self):
        self.client.force_login(User.objects.create_user("aluno", password="x"))
        resposta = self.client.get(reverse("obras:home"))
        self.assertContains(resposta, "css/base.css")
        self.assertNotContains(resposta, "base.css?v=")
