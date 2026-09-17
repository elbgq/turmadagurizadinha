"""
URL configuration for config project (Turma da Gurizadinha).

Cada app tem seu próprio urls.py, incluído aqui com um prefixo e um
namespace. Isso mantém as rotas organizadas conforme os módulos do
projeto (obras, avaliações, quiz). O relatório de desempenho do quiz
é uma rota dentro do próprio app "quiz" (ver quiz/urls.py).
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("contas/", include("contas.urls")),
    path("", include("obras.urls")),
    path("avaliacoes/", include("avaliacoes.urls")),
    path("quiz/", include("quiz.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
