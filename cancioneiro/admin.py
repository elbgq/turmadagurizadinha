from django.contrib import admin

from .models import Musica


@admin.register(Musica)
class MusicaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "ordem", "publicada")
    list_filter = ("publicada",)
    list_editable = ("ordem", "publicada")
    search_fields = ("titulo", "descricao")
