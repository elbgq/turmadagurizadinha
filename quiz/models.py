from django.db import models

from contas.models import Perfil
from obras.models import Obra

# Regras do quiz definidas pela cliente (reunião de 28/10/2026, documento
# quiz-porto_alegre.pdf): cada pergunta tem de 3 a 5 alternativas e uma
# imagem, e só uma alternativa é a correta.
MIN_ALTERNATIVAS = 3
MAX_ALTERNATIVAS = 5


class PerguntaQuiz(models.Model):
    """
    Pergunta do quiz interativo de uma Obra (Fase 7). Separada de
    obras.Questao de propósito: Questao é a atividade de apoio para
    impressão (sem imagem, sem explicação), e o quiz tem tela própria
    para cada pergunta — imagem, alternativas e, depois do clique, a
    tela CORRETO/ERRADO com a `explicacao` logo abaixo (inspirado no
    National Geographic Kids, conforme o documento da cliente).
    """

    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="perguntas_quiz")
    enunciado = models.TextField()
    imagem = models.ImageField(
        upload_to="quiz/perguntas/", blank=True, null=True,
        help_text="Opcional. Sem imagem, a pergunta usa a imagem da página da obra.",
    )
    explicacao = models.TextField(
        verbose_name="Explicação",
        help_text="Aparece depois da resposta, tanto para quem acertou quanto para quem errou.",
    )
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Pergunta do quiz"
        verbose_name_plural = "Perguntas do quiz"
        ordering = ["ordem", "id"]

    def __str__(self):
        return self.enunciado[:60]

    @property
    def imagem_exibida(self):
        """
        Imagem mostrada na tela da pergunta: a da própria pergunta ou,
        enquanto a cliente não envia uma ilustração para cada pergunta,
        a imagem da página da obra (e, por último, a do card da Home).
        """
        return self.imagem or self.obra.imagem_pagina or self.obra.capa or None

    @property
    def esta_completa(self):
        """
        Pergunta pronta para entrar no quiz: de 3 a 5 alternativas e
        exatamente uma correta. O cadastro pela tela de gestão já valida
        isso, mas a pergunta nasce sem alternativas (elas são cadastradas
        depois, em tela própria) — por isso a checagem existe também aqui.
        """
        alternativas = list(self.alternativas.all())
        corretas = sum(1 for a in alternativas if a.correta)
        return MIN_ALTERNATIVAS <= len(alternativas) <= MAX_ALTERNATIVAS and corretas == 1


class AlternativaQuiz(models.Model):
    pergunta = models.ForeignKey(PerguntaQuiz, on_delete=models.CASCADE, related_name="alternativas")
    texto = models.CharField(max_length=300)
    correta = models.BooleanField(default=False)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Alternativa do quiz"
        verbose_name_plural = "Alternativas do quiz"
        ordering = ["ordem", "id"]

    def __str__(self):
        return self.texto[:60]


class ResultadoQuiz(models.Model):
    """
    Resultado de uma tentativa do quiz de uma Obra, gravado por conta —
    login obrigatório em toda a plataforma (Fase 4), então o relatório de
    desempenho deixou de existir só na sessão do navegador. Cada
    tentativa vira um registro, permitindo histórico ao longo do tempo.

    O quiz não tem limite de tempo (decisão de 29/10/2026: não pressionar
    a criança), mas `tempo_segundos` continua gravado para o professor
    entender a dinâmica das respostas.
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


class RespostaQuiz(models.Model):
    """
    Cada resposta dada numa tentativa (um ResultadoQuiz), com o tempo que
    a pessoa levou naquela pergunta — para o professor ver em quais
    perguntas a turma demorou ou errou mais (pedido de 29/10/2026).
    Pergunta/alternativa usam SET_NULL e o enunciado é copiado, para o
    histórico continuar legível mesmo se a equipe editorial alterar ou
    excluir a pergunta depois.
    """

    resultado = models.ForeignKey(ResultadoQuiz, on_delete=models.CASCADE, related_name="respostas")
    pergunta = models.ForeignKey(
        PerguntaQuiz, on_delete=models.SET_NULL, null=True, blank=True, related_name="respostas"
    )
    alternativa = models.ForeignKey(
        AlternativaQuiz, on_delete=models.SET_NULL, null=True, blank=True, related_name="respostas"
    )
    enunciado = models.TextField()
    correta = models.BooleanField()
    tempo_segundos = models.PositiveIntegerField()
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Resposta do quiz"
        verbose_name_plural = "Respostas do quiz"
        ordering = ["ordem", "id"]

    def __str__(self):
        return f"{self.enunciado[:40]} — {'certa' if self.correta else 'errada'}"
