from django.db import models


class Obra(models.Model):
    """
    Uma obra infantil ilustrada — texto completo, tópicos/resumo para o
    professor e atividades de apoio para impressão (Questao/Alternativa
    abaixo). Não há model de galeria de imagens (IlustracaoObra foi
    descartado): cada obra tem só uma imagem, o campo `capa`.
    """

    titulo = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    autor = models.CharField(max_length=150, blank=True)
    ilustrador = models.CharField(max_length=150, blank=True)
    faixa_etaria = models.CharField(max_length=50, blank=True)
    capa = models.ImageField(upload_to="obras/capas/", blank=True, null=True)

    # Subtítulo/breve descrição — usado no card da Home e no topo da
    # página da obra (esboço enviado pela cliente).
    texto_breve = models.CharField(max_length=300, blank=True)
    texto_completo = models.TextField(blank=True)
    topicos_resumo = models.TextField(
        blank=True, help_text="Tópicos/resumo para uso do professor em sala de aula."
    )

    # Tempo único para o quiz inteiro (não por pergunta) — confirmado.
    tempo_limite_segundos = models.PositiveIntegerField(
        default=600, help_text="Tempo total do quiz, em segundos."
    )

    ordem = models.PositiveIntegerField(default=0)
    publicada = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Obra"
        verbose_name_plural = "Obras"
        ordering = ["ordem", "titulo"]

    def __str__(self):
        return self.titulo


class Questao(models.Model):
    """
    Pergunta cadastrada com resposta certa, ligada a uma Obra. Usada só
    para gerar as "atividades de apoio para impressão" na própria página
    da obra — sem versão interativa e sem mostrar o gabarito na tela
    (isso é regra de template, o campo Alternativa.correta existe sim).
    Vivia no antigo app "avaliacoes", removido — ver README.md.
    """

    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="questoes")
    enunciado = models.TextField()
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Questão"
        verbose_name_plural = "Questões"
        ordering = ["ordem", "id"]

    def __str__(self):
        return self.enunciado[:60]


class Alternativa(models.Model):
    questao = models.ForeignKey(Questao, on_delete=models.CASCADE, related_name="alternativas")
    texto = models.CharField(max_length=300)
    correta = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Alternativa"
        verbose_name_plural = "Alternativas"

    def __str__(self):
        return self.texto[:60]
