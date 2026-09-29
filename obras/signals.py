"""
Limpeza do arquivo de "Atividade de apoio (PDF)" no storage — evita que
trocar, limpar ou excluir a obra deixe arquivos órfãos em media/.
Registrado em ObrasConfig.ready() (ver apps.py).
"""

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import Obra


@receiver(pre_save, sender=Obra)
def apagar_pdf_antigo_ao_trocar(sender, instance, **kwargs):
    """Se o PDF foi trocado ou limpo nesta gravação, apaga o arquivo antigo."""
    if not instance.pk:
        return
    try:
        antiga = Obra.objects.get(pk=instance.pk)
    except Obra.DoesNotExist:
        return
    arquivo_antigo = antiga.atividade_pdf
    if arquivo_antigo and arquivo_antigo != instance.atividade_pdf:
        arquivo_antigo.delete(save=False)


@receiver(post_delete, sender=Obra)
def apagar_pdf_ao_excluir_obra(sender, instance, **kwargs):
    """Apaga o PDF da obra quando a própria obra é excluída."""
    if instance.atividade_pdf:
        instance.atividade_pdf.delete(save=False)
