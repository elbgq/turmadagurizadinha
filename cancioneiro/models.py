import re
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ValidationError
from django.db import models

# Domínios aceitos no link da música: os vídeos ficam no canal da autora
# no YouTube (reunião de 19/11/2026) — a plataforma só aponta para lá.
DOMINIOS_YOUTUBE = ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be")
_ID_VIDEO = re.compile(r"^[A-Za-z0-9_-]{11}$")


def validar_link_youtube(valor):
    """Aceita só endereços do YouTube (vídeo, playlist ou canal)."""
    host = (urlparse(valor).hostname or "").lower()
    if host not in DOMINIOS_YOUTUBE:
        raise ValidationError("Informe um link do YouTube (youtube.com ou youtu.be).")


def id_do_video_youtube(link):
    """
    Tira o id do vídeo de um link do YouTube, para montar a miniatura:
    youtu.be/<id>, youtube.com/watch?v=<id>, /shorts/<id>, /embed/<id>,
    /live/<id>. Link de canal ou playlist não tem id → None.
    """
    if not link:
        return None
    url = urlparse(link)
    host = (url.hostname or "").lower()
    candidato = None
    if host == "youtu.be":
        candidato = url.path.strip("/").split("/")[0]
    elif host in DOMINIOS_YOUTUBE:
        if url.path == "/watch":
            candidato = parse_qs(url.query).get("v", [None])[0]
        else:
            partes = url.path.strip("/").split("/")
            if len(partes) >= 2 and partes[0] in ("shorts", "embed", "live", "v"):
                candidato = partes[1]
    if candidato and _ID_VIDEO.match(candidato):
        return candidato
    return None


class Musica(models.Model):
    """
    Música do Cancioneiro (reunião com a cliente de 19/11/2026): um card
    com título, descrição curta e miniatura, e um botão que abre o vídeo
    no canal da autora no YouTube, em outra aba. A miniatura vem do
    próprio YouTube (pelo id do vídeo) ou da imagem enviada, que tem
    prioridade. Cadastro pela Equipe editorial (migration 0002).
    """

    titulo = models.CharField("título", max_length=200)
    descricao = models.CharField("descrição curta", max_length=300, blank=True)
    link_youtube = models.URLField(
        "link do YouTube", max_length=300, validators=[validar_link_youtube],
        help_text="Endereço do vídeo no canal do YouTube, por exemplo https://www.youtube.com/watch?v=...",
    )
    imagem = models.ImageField(
        "imagem do card", upload_to="cancioneiro/", blank=True, null=True,
        help_text="Opcional. Sem imagem, o card usa a miniatura do próprio vídeo no YouTube.",
    )
    ordem = models.PositiveIntegerField(default=0)
    publicada = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Música"
        verbose_name_plural = "Músicas"
        ordering = ["ordem", "titulo"]

    def __str__(self):
        return self.titulo

    @property
    def id_video(self):
        return id_do_video_youtube(self.link_youtube)

    @property
    def miniatura_url(self):
        """Imagem do card: a enviada ou, se não houver, a do YouTube."""
        if self.imagem:
            return self.imagem.url
        if self.id_video:
            return f"https://img.youtube.com/vi/{self.id_video}/hqdefault.jpg"
        return ""
