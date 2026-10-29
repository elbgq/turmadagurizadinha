from django.contrib import admin

from .forms import BaseAlternativaQuizFormSet
from .models import AlternativaQuiz, PerguntaQuiz, RespostaQuiz, ResultadoQuiz


class AlternativaQuizInline(admin.TabularInline):
    model = AlternativaQuiz
    formset = BaseAlternativaQuizFormSet  # mesma regra da tela de gestão: 3 a 5, uma correta
    extra = 3
    max_num = 5


@admin.register(PerguntaQuiz)
class PerguntaQuizAdmin(admin.ModelAdmin):
    list_display = ("enunciado", "obra", "ordem")
    list_filter = ("obra",)
    search_fields = ("enunciado",)
    inlines = (AlternativaQuizInline,)


class RespostaQuizInline(admin.TabularInline):
    model = RespostaQuiz
    extra = 0
    can_delete = False
    fields = ("ordem", "enunciado", "alternativa", "correta", "tempo_segundos")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ResultadoQuiz)
class ResultadoQuizAdmin(admin.ModelAdmin):
    list_display = ("perfil", "obra", "pontuacao", "total", "tempo_segundos", "criado_em")
    list_filter = ("obra",)
    date_hierarchy = "criado_em"
    readonly_fields = ("criado_em",)
    inlines = (RespostaQuizInline,)
