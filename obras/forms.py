from django.forms import inlineformset_factory
from django import forms
from django.utils.text import slugify

from .models import (
    Alternativa, Obra, PaginaATurminha, PaginaQuemSomos,
    PersonagemATurminha, Questao, ValorQuemSomos,
)


class ObraForm(forms.ModelForm):
    """
    Cadastro de obra fora do Django Admin (ver README — "Cadastro de
    conteúdo fora do Admin"). Quem acessa esta tela é a equipe da
    cliente (grupo "Equipe editorial" ou superusuário — mesma permissão
    obras.add_obra/change_obra já criada na Fase 4).
    """

    class Meta:
        model = Obra
        # "autor" e "faixa_etaria" continuam existindo no model (e no Django
        # Admin), mas ficam ocultos desta tela de cadastro a pedido da
        # cliente (28/09/2026). "categoria" aparece logo após "titulo".
        fields = [
            "titulo", "categoria", "slug", "ilustrador", "capa", "imagem_pagina",
            "texto_breve", "texto_completo", "topicos_resumo",
            "tempo_limite_segundos", "ordem", "publicada",
            "atividade_pdf",
        ]
        widgets = {
            "texto_completo": forms.Textarea(attrs={"rows": 8}),
            "topicos_resumo": forms.Textarea(attrs={"rows": 4}),
            "texto_breve": forms.Textarea(attrs={"rows": 2}),
        }

    # Campo declarado fora do Meta (nível da classe ObraForm) — é assim que o
    # Django reconhece um campo de formulário de verdade. Oculto da tela:
    # sempre gerado a partir do título em clean_slug(), abaixo.
    slug = forms.SlugField(
        required=False,
        widget=forms.HiddenInput(),
    )

    def clean_slug(self):
        slug = self.cleaned_data.get("slug")
        if not slug:
            base = slugify(self.cleaned_data.get("titulo") or "")
            slug = base
            i = 2
            consulta = Obra.objects.exclude(pk=self.instance.pk)
            while consulta.filter(slug=slug).exists():
                slug = f"{base}-{i}"
                i += 1
        return slug


# Perguntas de apoio (Questao) vinculadas à obra, direto no mesmo formulário.
QuestaoFormSet = inlineformset_factory(
    Obra, Questao,
    fields=("enunciado", "ordem"),
    widgets={"enunciado": forms.Textarea(attrs={"rows": 2})},
    extra=1, can_delete=True,
)

# Alternativas de uma questão — tela própria (ver obras/views.py
# questao_alternativas), porque formset dentro de formset não é algo
# simples no Django puro sem JavaScript extra.
AlternativaFormSet = inlineformset_factory(
    Questao, Alternativa,
    fields=("texto", "correta"),
    extra=2, can_delete=True,
)


# --------------------------------------------------------------------
# Conteúdo institucional editável — telas de gestão para "Quem somos"
# e "A Turminha" (acréscimo de 29/09/2026, ver obras/models.py).
# --------------------------------------------------------------------

class PaginaQuemSomosForm(forms.ModelForm):
    class Meta:
        model = PaginaQuemSomos
        fields = [
            "historia_texto", "historia_imagem",
            "missao_texto", "missao_imagem",
            "visao_texto", "visao_imagem",
            "valores_imagem",
        ]
        widgets = {
            "historia_texto": forms.Textarea(attrs={"rows": 8}),
            "missao_texto": forms.Textarea(attrs={"rows": 3}),
            "visao_texto": forms.Textarea(attrs={"rows": 3}),
        }


# Lista de Valores — adicionar/remover/reordenar direto no mesmo
# formulário (decisão da cliente em 29/09/2026), mesmo padrão de
# QuestaoFormSet acima.
ValorQuemSomosFormSet = inlineformset_factory(
    PaginaQuemSomos, ValorQuemSomos,
    fields=("titulo", "tema", "texto", "ordem"),
    widgets={"texto": forms.Textarea(attrs={"rows": 2})},
    extra=1, can_delete=True,
)


class PaginaATurminhaForm(forms.ModelForm):
    class Meta:
        model = PaginaATurminha
        fields = ["texto_introducao", "imagem_grupo"]
        widgets = {
            "texto_introducao": forms.Textarea(attrs={"rows": 3}),
        }


# Lista de Personagens — mesmo padrão de adicionar/remover/reordenar,
# incluindo a imagem de cada um (decisão da cliente em 29/09/2026).
PersonagemATurminhaFormSet = inlineformset_factory(
    PaginaATurminha, PersonagemATurminha,
    fields=("nome", "texto", "imagem", "ordem"),
    widgets={"texto": forms.Textarea(attrs={"rows": 3})},
    extra=1, can_delete=True,
)
