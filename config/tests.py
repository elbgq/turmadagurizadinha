import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

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
        (Path(TEMP_MEDIA) / "ilustracao.txt").write_text("conteúdo de teste")

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
        self.assertEqual(b"".join(resposta.streaming_content), "conteúdo de teste".encode())

    def test_arquivo_inexistente_retorna_404(self):
        self.client.force_login(User.objects.create_user("aluno", password="x"))
        self.assertEqual(self.client.get("/media/nao-existe.png").status_code, 404)
