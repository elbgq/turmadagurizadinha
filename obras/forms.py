from django.forms import inlineformset_factory
from django import forms
from django.utils.text import slugify

from .models import Alternativa, Obra, Questao


class ObraForm(forms.ModelForm):
    """
    Cadastro de obra fora do Django Admin (ver README — "Cadastro de
    conteúdo fora do Admin"). Quem acessa esta tela é a equipe da
    cliente (grupo "Equipe editorial" ou superusuário — mesma permissão
    obras.add_obra/change_obra já criada na Fase 4).
    """

    class Meta:
        model = Obra
        fields = [
            "titulo", "slug", "autor", "ilustrador", "faixa_etaria", "capa",
            "texto_breve", "texto_completo", "topicos_resumo",
            "tempo_limite_segundos", "ordem", "publicada",
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
