from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from contas.models import Perfil, Turma
from obras.models import Obra


class EntregaAtividade(models.Model):
    """
    Registro da atividade complementar (a atividade de apoio impressa da
    obra) de um aluno, lançado pelo professor — multiescola, etapa 3
    (09/11/2026). A atividade continua sendo feita no papel; aqui fica só
    se o aluno entregou, a nota (opcional, de 0 a 10) e uma observação.

    Um registro por aluno e obra: como o histórico do quiz, ele acompanha
    o aluno se ele mudar de turma; `turma` guarda a turma da época.
    """

    ENTREGUE = "entregue"
    NAO_ENTREGUE = "nao_entregue"
    SITUACAO_CHOICES = [
        (ENTREGUE, "Entregou"),
        (NAO_ENTREGUE, "Não entregou"),
    ]

    aluno = models.ForeignKey(
        Perfil, on_delete=models.CASCADE, related_name="entregas_atividade",
        limit_choices_to={"tipo": "aluno"}, verbose_name="Aluno(a)",
    )
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="entregas_atividade", verbose_name="Obra")
    turma = models.ForeignKey(
        Turma, on_delete=models.PROTECT, null=True, blank=True,
        related_name="entregas_atividade", verbose_name="Turma na época",
    )
    situacao = models.CharField("Situação", max_length=20, choices=SITUACAO_CHOICES)
    nota = models.DecimalField(
        "Nota", max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Opcional, de 0 a 10.",
    )
    observacao = models.CharField("Observação", max_length=300, blank=True)
    registrado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="Registrado por"
    )
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Entrega de atividade complementar"
        verbose_name_plural = "Entregas de atividade complementar"
        ordering = ["obra__titulo", "aluno__user__first_name"]
        constraints = [
            models.UniqueConstraint(fields=["aluno", "obra"], name="entrega_unica_por_aluno_e_obra"),
        ]

    def __str__(self):
        return f"{self.aluno} — {self.obra} ({self.get_situacao_display()})"
