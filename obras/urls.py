from django.urls import path

from . import views

app_name = "obras"

urlpatterns = [
    path("", views.home, name="home"),
    path("obra/<slug:slug>/", views.detalhe_obra, name="detalhe"),
]
