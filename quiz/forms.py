from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from obras.models import Obra

from .models import MAX_ALTERNATIVAS, MIN_ALTERNATIVAS, AlternativaQuiz, PerguntaQuiz

# Perguntas do quiz de uma obra — tela própria em /quiz/gerenciar/<obra>/
# (ver quiz/views.py), no mesmo padrão de QuestaoFormSet em obras/forms.py:
# um item novo por vez, alternativas em outra tela depois de salvar.
PerguntaQuizFormSet = inlineformset_factory(
    Obra, PerguntaQuiz,
    fields=("enunciado", "imagem", "explicacao", "ordem"),
    widgets={
        "enunciado": forms.Textarea(attrs={"rows": 2}),
        "explicacao": forms.Textarea(attrs={"rows": 3}),
    },
    extra=1, can_delete=True,
)


class BaseAlternativaQuizFormSet(BaseInlineFormSet):
    """
    Valida a regra da cliente para cada pergunta: de 3 a 5 alternativas
    e exatamente uma correta. Usado na tela de gestão e no Admin.
    """

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        restantes = [
            form for form in self.forms
            if form.cleaned_data
            and not form.cleaned_data.get("DELETE")
            and form.cleaned_data.get("texto")
        ]
        if not MIN_ALTERNATIVAS <= len(restantes) <= MAX_ALTERNATIVAS:
            raise forms.ValidationError(
                f"Cada pergunta precisa ter de {MIN_ALTERNATIVAS} a {MAX_ALTERNATIVAS} alternativas."
            )
        corretas = sum(1 for form in restantes if form.cleaned_data.get("correta"))
        if corretas != 1:
            raise forms.ValidationError("Marque exatamente uma alternativa como correta.")


# extra/max_num = 5: a tela sempre mostra até 5 linhas (as já salvas mais
# as em branco), e as linhas deixadas em branco são ignoradas.
AlternativaQuizFormSet = inlineformset_factory(
    PerguntaQuiz, AlternativaQuiz,
    formset=BaseAlternativaQuizFormSet,
    fields=("texto", "correta", "ordem"),
    extra=MAX_ALTERNATIVAS, max_num=MAX_ALTERNATIVAS, can_delete=True,
)
