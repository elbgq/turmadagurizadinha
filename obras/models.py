from django.core.validators import FileExtensionValidator
from django.db import models

from .validators import validar_pdf


class Obra(models.Model):
    """
    Uma obra infantil ilustrada — texto completo, tópicos/resumo para o
    professor e atividades de apoio para impressão (Questao/Alternativa
    abaixo). Não há model de galeria de imagens (IlustracaoObra foi
    descartado): duas imagens fixas por obra — `capa` (card da Home) e
    `imagem_pagina` (página da própria obra) — solicitado pela cliente
    em 28/09/2026.
    """

    class Categoria(models.TextChoices):
        TRADICIONALISMO_GAUCHO = "tradicionalismo_gaucho", "Tradicionalismo Gaúcho"
        PELOS_PAGOS_DO_RIO_GRANDE = "pelos_pagos_do_rio_grande", "Pelos Pagos do Rio Grande"
        BIOMA = "bioma", "Bioma"
        LENDAS_GAUCHAS = "lendas_gauchas", "Lendas Gaúchas"
        CURIOSIDADES = "curiosidades", "Curiosidades"

    titulo = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    categoria = models.CharField(
        max_length=30,
        choices=Categoria.choices,
        blank=True,
        default="",
        help_text="Categoria temática da obra (solicitado pela cliente em 28/09/2026).",
    )
    autor = models.CharField(max_length=150, blank=True)
    ilustrador = models.CharField(max_length=150, blank=True)
    faixa_etaria = models.CharField(max_length=50, blank=True)
    capa = models.ImageField(
        upload_to="obras/capas/", blank=True, null=True,
        verbose_name="Imagem do card (Home)",
        help_text="Aparece no card da obra na página inicial.",
    )
    imagem_pagina = models.ImageField(
        upload_to="obras/paginas/", blank=True, null=True,
        verbose_name="Imagem da página da obra",
        help_text="Aparece na página de detalhe da própria obra.",
    )
    atividade_pdf = models.FileField(
        upload_to="obras/atividades/", blank=True, null=True,
        validators=[FileExtensionValidator(["pdf"]), validar_pdf],
        verbose_name="Atividade de apoio (PDF)",
        help_text=(
            "Opcional. Um arquivo PDF de até 10 MB, disponível para download "
            "na página da obra. Convive com as perguntas cadastradas abaixo "
            "(acréscimo à Fase 6, pedido pela cliente em 28/09/2026)."
        ),
    )

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


# --------------------------------------------------------------------
# Conteúdo institucional editável ("Quem somos" e "A Turminha") —
# acréscimo de 29/09/2026, pedido da cliente: antes eram templates
# 100% fixos (texto direto no HTML); agora a equipe editorial pode
# alterar sem depender do desenvolvedor, pela tela /gerenciar/.
# PaginaQuemSomos e PaginaATurminha são "singletons" (uma linha só —
# reforçado em PaginaQuemSomos.save()/PaginaATurminha.save()), no
# mesmo espírito de configuração única de página. Os "Valores" e os
# "Personagens" viram listas editáveis (adicionar/remover/reordenar),
# decisão da cliente em 29/09/2026, e as imagens de cada seção também
# passam a ser substituíveis pela equipe editorial (mesma decisão).
# --------------------------------------------------------------------


class PaginaQuemSomos(models.Model):
    """
    Conteúdo da página "Quem somos" — história, missão, visão e a
    imagem que acompanha a seção "Valores" (os valores em si são a
    lista ValorQuemSomos, abaixo). Modelo singleton: sempre há uma
    única linha, obtida via PaginaQuemSomos.objects.get_or_create()
    nas views (mesmo padrão de "configuração de página única").
    """

    historia_texto = models.TextField(
        blank=True, verbose_name="Texto — História do Clube",
        help_text="Um parágrafo por linha em branco, como no texto completo da obra.",
    )
    historia_imagem = models.ImageField(
        upload_to="institucional/quem_somos/", blank=True, null=True,
        verbose_name="Imagem — História do Clube",
    )
    missao_texto = models.TextField(blank=True, verbose_name="Texto — Missão")
    missao_imagem = models.ImageField(
        upload_to="institucional/quem_somos/", blank=True, null=True,
        verbose_name="Imagem — Missão",
    )
    visao_texto = models.TextField(blank=True, verbose_name="Texto — Visão")
    visao_imagem = models.ImageField(
        upload_to="institucional/quem_somos/", blank=True, null=True,
        verbose_name="Imagem — Visão",
    )
    valores_imagem = models.ImageField(
        upload_to="institucional/quem_somos/", blank=True, null=True,
        verbose_name="Imagem — Valores",
    )

    class Meta:
        verbose_name = "Página Quem somos"
        verbose_name_plural = "Página Quem somos"

    def __str__(self):
        return "Quem somos"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class ValorQuemSomos(models.Model):
    """Um item da lista de Valores, na seção "Valores" de Quem somos."""

    pagina = models.ForeignKey(PaginaQuemSomos, on_delete=models.CASCADE, related_name="valores")
    titulo = models.CharField(max_length=150)
    tema = models.CharField(max_length=100, help_text='Aparece entre parênteses ao lado do título (ex.: "criatividade").')
    texto = models.TextField()
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Valor"
        verbose_name_plural = "Valores"
        ordering = ["ordem", "id"]

    def __str__(self):
        return self.titulo


class PaginaATurminha(models.Model):
    """
    Conteúdo da página "A Turminha" — texto de introdução e a imagem do
    grupo dos 4 personagens reunidos. Os personagens em si são a lista
    PersonagemATurminha, abaixo. Modelo singleton, mesmo padrão de
    PaginaQuemSomos.
    """

    texto_introducao = models.TextField(blank=True, verbose_name="Texto de introdução")
    imagem_grupo = models.ImageField(
        upload_to="institucional/a_turminha/", blank=True, null=True,
        verbose_name="Imagem do grupo (os 4 personagens reunidos)",
    )

    class Meta:
        verbose_name = "Página A Turminha"
        verbose_name_plural = "Página A Turminha"

    def __str__(self):
        return "A Turminha"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class PersonagemATurminha(models.Model):
    """Um personagem (Guri, Cícero, Germano, Catarina...) da página A Turminha."""

    pagina = models.ForeignKey(PaginaATurminha, on_delete=models.CASCADE, related_name="personagens")
    nome = models.CharField(max_length=100)
    texto = models.TextField(help_text="Um parágrafo por linha em branco.")
    imagem = models.ImageField(upload_to="institucional/a_turminha/", blank=True, null=True)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Personagem"
        verbose_name_plural = "Personagens"
        ordering = ["ordem", "id"]

    def __str__(self):
        return self.nome
