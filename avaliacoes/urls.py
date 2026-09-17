from django.urls import path

from . import views

app_name = "avaliacoes"

urlpatterns = [
    path("<slug:obra_slug>/", views.avaliacao_obra, name="avaliacao"),
]
