from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Musica, id_do_video_youtube, validar_link_youtube

LINK = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


class LinkYoutubeTests(TestCase):
    def test_id_do_video_nos_formatos_comuns(self):
        for link in (
            LINK, "https://youtu.be/dQw4w9WgXcQ", "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=10s", "https://www.youtube.com/embed/dQw4w9WgXcQ",
        ):
            with self.subTest(link=link):
                self.assertEqual(id_do_video_youtube(link), "dQw4w9WgXcQ")

    def test_link_de_canal_nao_tem_id(self):
        self.assertIsNone(id_do_video_youtube("https://www.youtube.com/@canaldaautora"))

    def test_so_aceita_youtube(self):
        validar_link_youtube(LINK)
        with self.assertRaises(ValidationError):
            validar_link_youtube("https://exemplo.com/video")

    def test_miniatura_do_youtube_sem_imagem(self):
        musica = Musica(titulo="Hino", link_youtube=LINK)
        self.assertEqual(musica.miniatura_url, "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg")


class CancioneiroListaTests(TestCase):
    """Aba "Cancioneiro" (19/11/2026): só as publicadas, para qualquer logado."""

    def setUp(self):
        self.usuario = User.objects.create_user("aluno", password="senha-teste-123")
        self.usuario.perfil.tipo = "aluno"
        self.usuario.perfil.save()
        Musica.objects.create(titulo="Música publicada", descricao="Uma milonga.", link_youtube=LINK, publicada=True)
        Musica.objects.create(titulo="Música rascunho", link_youtube=LINK)

    def test_exige_login(self):
        resposta = self.client.get(reverse("cancioneiro:lista"))
        self.assertEqual(resposta.status_code, 302)

    def test_mostra_so_as_publicadas_com_link_em_nova_aba(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("cancioneiro:lista"))
        self.assertContains(resposta, "Música publicada")
        self.assertContains(resposta, "Uma milonga.")
        self.assertNotContains(resposta, "Música rascunho")
        self.assertContains(resposta, f'href="{LINK}"')
        self.assertContains(resposta, 'target="_blank" rel="noopener noreferrer"')
        self.assertContains(resposta, "img.youtube.com/vi/dQw4w9WgXcQ")
        self.assertNotContains(resposta, "Gerenciar músicas")

    def test_aba_na_navbar(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("obras:home"))
        self.assertContains(resposta, f'href="{reverse("cancioneiro:lista")}"')


class CancioneiroGestaoTests(TestCase):
    """Cadastro só pela Equipe editorial (permissões da migration 0002)."""

    def setUp(self):
        self.aluno = User.objects.create_user("aluno", password="senha-teste-123")
        self.editor = User.objects.create_user("editor", password="senha-teste-123")
        self.editor.groups.add(Group.objects.get(name="Equipe editorial"))
        self.musica = Musica.objects.create(titulo="Música", link_youtube=LINK)

    def test_grupo_tem_as_permissoes(self):
        for perm in ("view_musica", "add_musica", "change_musica", "delete_musica"):
            self.assertTrue(self.editor.has_perm(f"cancioneiro.{perm}"))

    def test_sem_permissao_da_403(self):
        self.client.force_login(self.aluno)
        for url in (
            reverse("cancioneiro:gestao_lista"), reverse("cancioneiro:musica_nova"),
            reverse("cancioneiro:musica_editar", args=[self.musica.pk]),
            reverse("cancioneiro:musica_excluir", args=[self.musica.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_editor_lista_rascunho_e_cadastra(self):
        self.client.force_login(self.editor)
        self.assertContains(self.client.get(reverse("cancioneiro:gestao_lista")), "Música")
        resposta = self.client.post(reverse("cancioneiro:musica_nova"), {
            "titulo": "Nova", "descricao": "", "link_youtube": "https://youtu.be/dQw4w9WgXcQ",
            "ordem": "1", "publicada": "on",
        })
        self.assertRedirects(resposta, reverse("cancioneiro:gestao_lista"))
        self.assertTrue(Musica.objects.get(titulo="Nova").publicada)

    def test_link_fora_do_youtube_nao_salva(self):
        self.client.force_login(self.editor)
        resposta = self.client.post(reverse("cancioneiro:musica_nova"), {
            "titulo": "Errada", "link_youtube": "https://exemplo.com/x", "ordem": "0",
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Musica.objects.filter(titulo="Errada").exists())

    def test_editar_e_excluir(self):
        self.client.force_login(self.editor)
        self.client.post(reverse("cancioneiro:musica_editar", args=[self.musica.pk]), {
            "titulo": "Renomeada", "link_youtube": LINK, "ordem": "0",
        })
        self.musica.refresh_from_db()
        self.assertEqual(self.musica.titulo, "Renomeada")
        self.client.post(reverse("cancioneiro:musica_excluir", args=[self.musica.pk]))
        self.assertFalse(Musica.objects.exists())

    def test_publicada_em_destaque_no_topo(self):
        # Nos moldes da edição de obra (pedido do Eloi, 19/11/2026).
        self.client.force_login(self.editor)
        resposta = self.client.get(reverse("cancioneiro:musica_editar", args=[self.musica.pk]))
        html = resposta.content.decode()
        self.assertContains(resposta, 'class="form__publicacao"')
        self.assertContains(resposta, "Publicar esta música")
        self.assertContains(resposta, "não publicada (rascunho)")
        self.assertLess(html.index("form__publicacao"), html.index('<legend class="form__secao-titulo">Música</legend>'))
        self.assertEqual(html.count('name="publicada"'), 1)
        self.musica.publicada = True
        self.musica.save()
        resposta = self.client.get(reverse("cancioneiro:musica_editar", args=[self.musica.pk]))
        self.assertContains(resposta, "form__publicacao form__publicacao--publicada")

    def test_link_gerenciar_na_aba_para_o_editor(self):
        self.client.force_login(self.editor)
        self.assertContains(self.client.get(reverse("cancioneiro:lista")), "Gerenciar músicas")
