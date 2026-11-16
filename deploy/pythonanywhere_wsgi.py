"""
Modelo do arquivo WSGI do PythonAnywhere (servidor de TESTE).

NÃO é usado pelo projeto: o PythonAnywhere cria o arquivo dele em
/var/www/eloibgq_pythonanywhere_com_wsgi.py. Abra esse arquivo pela aba
"Web" (link "WSGI configuration file"), APAGUE todo o conteúdo e cole este,
trocando SEUUSUARIO pelo seu usuário. Passo a passo completo em
docs/deploy-pythonanywhere.md.

As variáveis (SECRET_KEY, DEBUG etc.) vêm do .env da pasta do projeto, que o
próprio config/settings.py carrega — não precisa repetir nada aqui.
"""

import os
import sys

PASTA_DO_PROJETO = "/home/eloibgq/turmadagurizadinha"

if PASTA_DO_PROJETO not in sys.path:
    sys.path.insert(0, PASTA_DO_PROJETO)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
