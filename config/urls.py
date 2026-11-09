"""
URL configuration for config project (Turma da Gurizadinha).

Cada app tem seu próprio urls.py, incluído aqui com um prefixo e um
namespace. Isso mantém as rotas organizadas conforme os módulos do
projeto (contas, obras, quiz). O app "avaliacoes" foi removido: as
questões/alternativas (impressão de atividades de apoio) agora vivem
dentro do próprio app "obras" (ver obras/models.py e obras/views.py) —
não é mais uma rota própria. O relatório de desempenho do quiz é uma
rota dentro do próprio app "quiz" (ver quiz/urls.py).
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("contas/", include("contas.urls")),
    path("", include("obras.urls")),
    path("quiz/", include("quiz.urls")),
    # Área da escola: admin da escola e professor (multiescola, 09/11/2026)
    path("escola/", include("escola.urls")),
]

# Uploads (media/): servidos pelo próprio Django também em produção. O
# volume é pequeno e o LoginRequiredMiddleware protege esses arquivos como o
# resto do site (só quem está logado vê as ilustrações e PDFs).
# `static()` só funciona com DEBUG=True, por isso a rota é declarada direto.
def servir_media(request, path):
    # MEDIA_ROOT lido a cada requisição (e não fixado na hora de montar as
    # rotas), para respeitar o override_settings dos testes.
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns += [
    re_path(rf"^{settings.MEDIA_URL.lstrip('/')}(?P<path>.*)$", servir_media),
]
