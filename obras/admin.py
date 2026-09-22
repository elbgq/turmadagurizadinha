from django.contrib import admin

from .models import Alternativa, Obra, Questao


class AlternativaInline(admin.TabularInline):
    model = Alternativa
    extra = 1


@admin.register(Questao)
class QuestaoAdmin(admin.ModelAdmin):
    list_display = ("enunciado", "obra", "ordem")
    list_filter = ("obra",)
    search_fields = ("enunciado",)
    inlines = (AlternativaInline,)


class QuestaoInline(admin.StackedInline):
    model = Questao
    extra = 0
    show_change_link = True


@admin.register(Obra)
class ObraAdmin(admin.ModelAdmin):
    list_display = ("titulo", "faixa_etaria", "ordem", "publicada")
    list_filter = ("publicada", "faixa_etaria")
    search_fields = ("titulo", "autor", "ilustrador")
    prepopulated_fields = {"slug": ("titulo",)}
    inlines = (QuestaoInline,)
