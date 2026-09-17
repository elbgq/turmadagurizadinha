from django.urls import path

from . import views

app_name = "quiz"

urlpatterns = [
    path("<slug:obra_slug>/", views.quiz_obra, name="quiz"),
    path("<slug:obra_slug>/resultado/", views.quiz_resultado, name="resultado"),
]
