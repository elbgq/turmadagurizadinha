from .models import ConfiguracaoSite


def tema_ativo(request):
    """
    Disponibiliza o caminho do CSS do tema ativo (ConfiguracaoSite) para
    todos os templates — usado no base.html, junto do base.css estrutural.
    """
    tema = ConfiguracaoSite.obter().tema
    return {"tema_css": f"css/temas/tema-{tema}.css"}
