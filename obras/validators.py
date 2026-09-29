"""
Validadores para os arquivos enviados no cadastro de obra.

Hoje só cobre o PDF de "Atividade de apoio" (ver Obra.atividade_pdf em
models.py) — acréscimo à Fase 6 pedido pela cliente em 28/09/2026.
"""

from django.core.exceptions import ValidationError

TAMANHO_MAXIMO_PDF = 10 * 1024 * 1024  # 10 MB


def validar_pdf(arquivo):
    """
    Recusa arquivos acima de 10 MB e arquivos cujos primeiros bytes não
    sejam a assinatura `%PDF-` (confere o conteúdo de verdade, não só a
    extensão do nome do arquivo).
    """
    if arquivo.size > TAMANHO_MAXIMO_PDF:
        raise ValidationError("O arquivo precisa ter no máximo 10 MB.")

    cabecalho = arquivo.read(5)
    arquivo.seek(0)
    if cabecalho != b"%PDF-":
        raise ValidationError("O arquivo enviado não é um PDF válido.")
