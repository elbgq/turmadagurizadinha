from django.db import models

from contas.models import Perfil
from obras.models import Obra

# Regras do quiz definidas pela cliente (reunião de 28/10/2026, documento
# quiz-porto_alegre.pdf): cada pergunta tem de 3 a 5 alternativas e uma
# imagem, e só uma alternativa é a correta.
MIN_ALTERNATIVAS = 3
MAX_ALTERNATIVAS = 5

# Mensagens mostradas junto com o número de acertos, ao fim do quiz —
# texto da cliente, sem alteração (documento de 28/10/2026). Faixas
# definidas em 29/10/2026: até 50%, acima de 50% até 70%, acima de 70%
# (o documento fala em "60% a 70%" e "80% a 100%", o que deixaria sem
# mensagem resultados como 55% ou 75%).
MENSAGEM_ATE_50 = (
    "Bah, vivente! Ainda tem muita coisa boa pra descobrir! Cada pergunta é uma "
    "oportunidade de aprender. Não te atucana, dá mais uma espiada nas histórias e "
    "volta pra peleia. Tu vais longe, tchê!"
)
MENSAGEM_ATE_70 = (
    "Buenas! Tu já estás no rumo certo! Acertou uma boa parte da prosa. Segue "
    "aprendendo, que conhecimento nunca é demais. Bora pra próxima, tchê!"
)
MENSAGEM_ACIMA_70 = (
    "Mas barbaridade, tchê! Tu deste um show de conhecimento! Tá mais afiado que "
    "faca de gaúcho! Parabéns, vivente! Segue assim, curioso(a) e aprendendo, que "
    "tu é um(a) baita conhecedor(a) da nossa cultura!"
)


def mensagem_desempenho(acertos, total):
    """
    Mensagem da faixa de acerto. Compara em números inteiros
    (acertos × 100 contra limite × total) para os limites exatos — 50% e
    70% — não dependerem de arredondamento: 5 de 10 é "até 50%", 7 de 10
    é "até 70%".
    """
    if acertos * 100 <= 50 * total:
        return MENSAGEM_ATE_50
    if acertos * 100 <= 70 * total:
        return MENSAGEM_ATE_70
    return MENSAGEM_ACIMA_70


def formatar_tempo(segundos):
    """90 → "1 min 30 s"; 45 → "45 s" — para o professor ler o tempo."""
    minutos, segundos = divmod(segundos, 60)
    if minutos:
        return f"{minutos} min {segundos} s" if segundos else f"{minutos} min"
    return f"{segundos} s"


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

    @property
    def porcentagem(self):
        """Porcentagem de acerto, arredondada (para o professor)."""
        return round(self.pontuacao * 100 / self.total) if self.total else 0

    @property
    def mensagem(self):
        return mensagem_desempenho(self.pontuacao, self.total)

    @property
    def tempo_formatado(self):
        return formatar_tempo(self.tempo_segundos)


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

    @property
    def tempo_formatado(self):
        return formatar_tempo(self.tempo_segundos)
