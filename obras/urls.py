from django.urls import path

from . import views

app_name = "obras"

urlpatterns = [
    path("", views.home, name="home"),
    path("quem-somos/", views.quem_somos, name="quem_somos"),
    path("a-turminha/", views.a_turminha, name="a_turminha"),
    path("obra/<slug:slug>/", views.detalhe_obra, name="detalhe"),
    path("obra/<slug:slug>/atividade.pdf", views.atividade_pdf, name="atividade_pdf"),
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
    # Conteúdo institucional editável (acréscimo de 29/09/2026)
    path("gerenciar/quem-somos/", views.quem_somos_editar, name="quem_somos_editar"),
    path("gerenciar/a-turminha/", views.a_turminha_editar, name="a_turminha_editar"),
]
