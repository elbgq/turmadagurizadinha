from django import forms

from .models import Musica


class MusicaForm(forms.ModelForm):
    """Cadastro de música do Cancioneiro (Equipe editorial)."""

    class Meta:
        model = Musica
        fields = ["titulo", "descricao", "link_youtube", "imagem", "ordem", "publicada"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 2})}
