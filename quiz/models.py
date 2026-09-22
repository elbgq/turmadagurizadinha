from django.db import models

from contas.models import Perfil
from obras.models import Obra


class ResultadoQuiz(models.Model):
    """
    Resultado de uma tentativa do quiz de uma Obra, gravado por conta —
    login obrigatório em toda a plataforma (Fase 4), então o relatório de
    desempenho deixou de existir só na sessão do navegador. Cada
    tentativa vira um registro, permitindo histórico ao longo do tempo.

    PerguntaQuiz e AlternativaQuiz (as perguntas interativas em si) ficam
    para a Fase 7 — Módulo de Quiz; este model só guarda o resultado.
    """

    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name="resultados_quiz")
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="resultados_quiz")
    pontuacao = models.PositiveIntegerField()
    total = models.PositiveIntegerField()
    tempo_segundos = models.PositiveIntegerField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Resultado de quiz"
        verbose_name_plural = "Resultados de quiz"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.perfil} — {self.obra} ({self.pontuacao}/{self.total})"
