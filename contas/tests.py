import importlib
from io import StringIO

from django.apps import apps
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Perfil

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


class CadastroTests(TestCase):
    def test_cadastro_grava_tipo_escolhido(self):
        resposta = self.client.post(
            reverse("contas:cadastro"),
            {
                "nome": "Professora Ana",
                "email": "Ana@Exemplo.com",
                "tipo": Perfil.PROFESSOR,
                "password1": "senha-forte-987",
                "password2": "senha-forte-987",
            },
        )
        self.assertRedirects(resposta, reverse("obras:home"), fetch_redirect_response=False)
        usuario = User.objects.get(username="ana@exemplo.com")
        self.assertEqual(usuario.perfil.tipo, Perfil.PROFESSOR)
        self.assertEqual(Perfil.objects.filter(user=usuario).count(), 1)


class AdminUsuarioTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", password="senha-teste-123")
        self.client.force_login(self.admin)

    def test_adicionar_usuario_no_admin_cria_um_perfil(self):
        resposta = self.client.post(
            reverse("admin:auth_user_add"),
            {
                "username": "novo@exemplo.com",
                "usable_password": "true",
                "password1": "senha-forte-987",
                "password2": "senha-forte-987",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        usuario = User.objects.get(username="novo@exemplo.com")
        self.assertEqual(Perfil.objects.filter(user=usuario).count(), 1)

    def test_tela_de_edicao_mostra_o_perfil(self):
        resposta = self.client.get(reverse("admin:auth_user_change", args=[self.admin.pk]))
        self.assertContains(resposta, "perfil-0-tipo")


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
