from django.urls import path

from . import views

app_name = "quiz"

urlpatterns = [
    # Cadastro das perguntas pela equipe editorial (Fase 7, etapa 1)
    path("gerenciar/<int:obra_pk>/", views.perguntas_editar, name="perguntas_editar"),
    path(
        "gerenciar/pergunta/<int:pergunta_pk>/alternativas/",
        views.pergunta_alternativas,
        name="pergunta_alternativas",
    ),
    path("<slug:obra_slug>/", views.quiz_obra, name="quiz"),
    path("<slug:obra_slug>/pergunta/<int:n>/", views.quiz_pergunta, name="pergunta"),
    path("<slug:obra_slug>/pergunta/<int:n>/resposta/", views.quiz_resposta, name="resposta"),
    path("<slug:obra_slug>/fim/", views.quiz_fim, name="fim"),
    path("<slug:obra_slug>/resultado/", views.quiz_resultado, name="resultado"),
]
