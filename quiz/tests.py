from django.contrib.auth.models import User
from django.test import TestCase

from obras.models import Obra

from .models import ResultadoQuiz


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
