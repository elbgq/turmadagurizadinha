from django.urls import path

from . import views

app_name = "escola"

# Área da escola (multiescola, etapa 2 — 09/11/2026). Ver views.py.
urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("professores/", views.professores, name="professores"),
    path("professores/novo/", views.professor_novo, name="professor_novo"),
    path("professores/<int:pk>/editar/", views.professor_editar, name="professor_editar"),
    path("professores/<int:pk>/ativo/", views.professor_ativo, name="professor_ativo"),
    path("turmas/", views.turmas, name="turmas"),
    path("turmas/nova/", views.turma_nova, name="turma_nova"),
    path("turmas/<int:pk>/", views.turma, name="turma"),
    path("turmas/<int:pk>/editar/", views.turma_editar, name="turma_editar"),
    path("turmas/<int:pk>/alunos/novo/", views.aluno_novo, name="aluno_novo"),
    path("turmas/<int:pk>/alunos/lote/", views.alunos_em_lote, name="alunos_lote"),
    path("turmas/<int:pk>/cartoes/", views.cartoes, name="cartoes"),
    path("turmas/<int:pk>/novas-senhas/", views.novas_senhas_turma, name="novas_senhas_turma"),
    path("alunos/<int:pk>/editar/", views.aluno_editar, name="aluno_editar"),
    path("alunos/<int:pk>/nova-senha/", views.aluno_nova_senha, name="aluno_nova_senha"),
    path("alunos/<int:pk>/ativo/", views.aluno_ativo, name="aluno_ativo"),
    path("alunos/<int:pk>/consentimento/", views.aluno_consentimento, name="aluno_consentimento"),
]
