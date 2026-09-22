from django.contrib import admin

from .models import ResultadoQuiz


@admin.register(ResultadoQuiz)
class ResultadoQuizAdmin(admin.ModelAdmin):
    list_display = ("perfil", "obra", "pontuacao", "total", "tempo_segundos", "criado_em")
    list_filter = ("obra",)
    date_hierarchy = "criado_em"
    readonly_fields = ("criado_em",)
