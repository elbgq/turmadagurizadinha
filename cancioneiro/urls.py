from django.urls import path

from . import views

app_name = "cancioneiro"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("gerenciar/", views.gestao_lista, name="gestao_lista"),
    path("gerenciar/nova/", views.musica_nova, name="musica_nova"),
    path("gerenciar/<int:pk>/", views.musica_editar, name="musica_editar"),
    path("gerenciar/<int:pk>/excluir/", views.musica_excluir, name="musica_excluir"),
]
