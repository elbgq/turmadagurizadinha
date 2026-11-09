"""
Login e senha dos alunos criados pelo professor (multiescola, etapa 2 —
09/11/2026). Criança pequena normalmente não tem e-mail, então o aluno
entra com um usuário curto (ex.: "joao.3anob") e uma senha simples
(palavra + 3 números, ex.: "sapo417"), impressos no cartão de acesso.
Esqueceu? O professor gera uma senha nova (não há e-mail para recuperar).
"""

import secrets

from django.contrib.auth.models import User
from django.utils.text import slugify

# Palavras curtas e fáceis de ler para quem está se alfabetizando.
PALAVRAS = [
    "sapo", "gato", "bola", "pato", "lua", "sol", "uva", "boi", "mate", "cuia",
    "flor", "rio", "mar", "pipa", "bolo", "suco", "casa", "dado", "fada", "galo",
    "leao", "lobo", "mel", "nuvem", "ovo", "peixe", "pião", "rato", "sino", "tatu",
    "urso", "vaca", "zebra", "anel", "barco", "caju", "doce", "foca", "gema", "ilha",
    "jaca", "kiwi", "lago", "milho", "ninho", "onda", "pera", "queijo", "rede", "sapato",
    "teia", "trem", "vento", "xale", "coruja", "tchê", "pampa", "guri", "prenda", "laço",
]


def gerar_senha():
    """Palavra + 3 números (ex.: "sapo417"), sem acento — fácil de digitar."""
    palavra = slugify(secrets.choice(PALAVRAS)).replace("-", "")
    return f"{palavra}{secrets.randbelow(900) + 100}"


def gerar_login(nome, turma):
    """
    "João da Silva" na turma "3º ano B" → "joao.3oanob" (ou "joao2.3oanob",
    "joao3.3oanob"... se já existir). O login é único em toda a
    plataforma, sem o @ dos e-mails dos professores.
    """
    partes = slugify(nome).split("-")
    primeiro = (partes[0] if partes and partes[0] else "aluno")[:20]
    sufixo = slugify(turma.nome).replace("-", "")[:12] or f"t{turma.pk}"
    candidato = f"{primeiro}.{sufixo}"
    n = 2
    while User.objects.filter(username__iexact=candidato).exists():
        candidato = f"{primeiro}{n}.{sufixo}"
        n += 1
    return candidato
