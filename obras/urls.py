from django.urls import path

from . import views

app_name = "obras"

urlpatterns = [
    path("", views.home, name="home"),
    path("obra/<slug:slug>/", views.detalhe_obra, name="detalhe"),
    # Cadastro de conteúdo fora do Admin — equipe da cliente (ver views.py)
    path("gerenciar/", views.obra_lista, name="obra_lista"),
    path("gerenciar/nova/", views.obra_nova, name="obra_nova"),
    path("gerenciar/<int:pk>/", views.obra_editar, name="obra_editar"),
    path("gerenciar/<int:pk>/excluir/", views.obra_excluir, name="obra_excluir"),
    path(
        "gerenciar/questao/<int:questao_id>/alternativas/",
        views.questao_alternativas,
        name="questao_alternativas",
    ),
]
