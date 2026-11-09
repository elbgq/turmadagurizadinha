from django.contrib import admin

from .models import EntregaAtividade


@admin.register(EntregaAtividade)
class EntregaAtividadeAdmin(admin.ModelAdmin):
    """Só consulta para a equipe da plataforma; quem lança é o professor, na área da escola."""

    list_display = ("aluno", "obra", "turma", "situacao", "nota", "atualizado_em")
    list_filter = ("aluno__escola", "turma", "obra", "situacao")
    search_fields = ("aluno__user__first_name", "aluno__user__username", "obra__titulo")
    list_select_related = ("aluno__user", "obra", "turma")
    readonly_fields = ("registrado_por", "atualizado_em")
