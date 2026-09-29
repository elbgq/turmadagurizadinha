from django.contrib import admin

from .models import (
    Alternativa, Obra, PaginaATurminha, PaginaQuemSomos,
    PersonagemATurminha, Questao, ValorQuemSomos,
)


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


# Conteúdo institucional editável (acréscimo de 29/09/2026) — a tela
# principal para a equipe editorial é /gerenciar/quem-somos/ e
# /gerenciar/a-turminha/ (ver obras/views.py); o Admin fica disponível
# também para quem for staff/superusuário, mesmo padrão de Obra acima.


class ValorQuemSomosInline(admin.TabularInline):
    model = ValorQuemSomos
    extra = 1


@admin.register(PaginaQuemSomos)
class PaginaQuemSomosAdmin(admin.ModelAdmin):
    inlines = (ValorQuemSomosInline,)

    def has_add_permission(self, request):
        # Singleton: só existe uma linha (ver PaginaQuemSomos.save()).
        return not PaginaQuemSomos.objects.exists()


class PersonagemATurminhaInline(admin.TabularInline):
    model = PersonagemATurminha
    extra = 1


@admin.register(PaginaATurminha)
class PaginaATurminhaAdmin(admin.ModelAdmin):
    inlines = (PersonagemATurminhaInline,)

    def has_add_permission(self, request):
        return not PaginaATurminha.objects.exists()
