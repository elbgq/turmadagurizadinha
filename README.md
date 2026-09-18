# Turma da Gurizadinha

Site com conteúdo de obras infantis ilustradas, criado para uso de professores como material didático. Contará inicialmente com 30 histórias publicadas; cada obra disponibiliza texto completo, tópicos/resumo para uso em sala de aula, questões sobre o conteúdo (versão impressa e interativa) e um quiz com temporizador, pontuação e relatório de desempenho para o professor.

Stack: **Python + Django 5.2 (LTS)**, banco **SQLite** em desenvolvimento, front-end em templates Django (HTML/CSS/JS).

## Estrutura do projeto

```
turmadagurizadinha/
├── config/                 # settings, urls, wsgi/asgi do projeto
├── contas/                  # Fase 4 — autocadastro, login e logout (login obrigatório em todo o site)
├── obras/                  # Fase 5 — Home e Página da Obra
├── avaliacoes/              # Fase 6 — Módulo de Avaliações (impressa e interativa)
├── quiz/                    # Fase 7 — Módulo de Quiz (temporizador, pontuação,
│                              #   e relatório de desempenho — rota "resultado" no próprio app)
├── templates/                # templates globais (base.html, navbar)
├── static/                   # css/js/img globais
├── media/                    # uploads (ilustrações das obras — Fase 4)
├── manage.py
├── requirements.txt
├── .env                       # segredos locais (não versionado — copie de .env.example)
├── .env.example                # modelo do .env, versionado, sem valores reais
└── .vscode/                  # configuração pronta para depurar no VS Code
```

Cada app tem seus próprios `templates/<app>/`, `models.py`, `views.py`, `urls.py`, `admin.py` e `migrations/`, seguindo o padrão do Django — isso facilita desenvolver e testar cada módulo do projeto de forma isolada. Não existe um app dedicado só a relatórios; foi avaliado e descartado por não haver, no momento, nenhuma lógica que precise viver fora do app `quiz`.

**Controle de acesso (decisão atualizada):** toda a plataforma passou a exigir login — público em geral, alunos e professores incluídos, todos com autocadastro aberto (nome, e-mail, senha) pelo app `contas`. A equipe da cliente continua usando o Django Admin separadamente, com conta de staff. Com isso, o relatório de desempenho do quiz deixou de ficar só na sessão do navegador: agora cada tentativa é gravada em banco, vinculada à conta do usuário logado (model `ResultadoQuiz`, no app `quiz`), permitindo ver histórico ao longo do tempo. *(Isso substitui o desenho anterior descrito nos comentários de `quiz/views.py`, que ainda precisa ser atualizado na Fase 4.)*

**Segurança e versão do Django (atualização):** o projeto foi atualizado do Django 5.1 (suporte de segurança encerrado em 31/12/2025) para o **Django 5.2 LTS** (suporte de segurança até abr/2028). O `SECRET_KEY` deixou de ter um valor fixo versionado no `settings.py`: agora ele é lido de um arquivo `.env` local (não versionado — carregado via `python-dotenv`), com `.env.example` servindo de modelo no repositório. Em desenvolvimento, se o `.env` não existir, o projeto ainda roda com uma chave gerada na hora (só localmente); em produção (`DEBUG=False`), a variável de ambiente passa a ser obrigatória — configurada diretamente no servidor na Fase 10, nunca no repositório.

## Como rodar pela primeira vez (Windows / VS Code)

1. Abra a pasta do projeto no VS Code (`File > Open Folder`).
2. Abra um terminal integrado (`` Ctrl+` ``) e crie o ambiente virtual:
   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```
3. Instale as dependências:
   ```powershell
   pip install -r requirements.txt
   ```
   > Se o seu `venv` já existia antes desta atualização (Django 5.1 → 5.2 LTS + `python-dotenv`), rode `pip install -r requirements.txt --upgrade` para atualizar os pacotes já instalados.
4. No VS Code, selecione o interpretador Python do `venv` (`Ctrl+Shift+P` → *Python: Select Interpreter* → escolha o que está em `venv\Scripts\python.exe`).
5. Crie o seu `.env` local a partir do modelo (o `.env` já vem pronto neste projeto com uma chave gerada para você; se precisar gerar uma nova, copie `.env.example` para `.env` e rode):
   ```powershell
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
   Cole o valor gerado em `DJANGO_SECRET_KEY` dentro do `.env`. Esse arquivo não é versionado (ver `.gitignore`).
6. Aplique as migrações iniciais e crie um super usuário para o Django Admin:
   ```powershell
   python manage.py migrate
   python manage.py createsuperuser
   ```
7. Suba o servidor de desenvolvimento:
   ```powershell
   python manage.py runserver
   ```
   Acesse http://127.0.0.1:8000/ (site) e http://127.0.0.1:8000/admin/ (admin).

   Ou use *Run and Debug* (F5) no VS Code — já existe uma configuração pronta em `.vscode/launch.json` ("Django: runserver").
8. Inicialize o repositório Git (se ainda não tiver feito) — o `.env` fica de fora automaticamente, graças ao `.gitignore`:
   ```powershell
   git init
   git add .
   git commit -m "Estrutura inicial do projeto Django"
   ```

## Checklist de fases (documento de projeto)

- [x] **Fase 1 — Levantamento e Planejamento** (1 semana): escopo final, wireframes das telas principais ✅. Falta apenas a lista definitiva das 30 obras (depende da cliente).
- [x] **Fase 2 — Modelagem de Dados e Arquitetura** (1 semana): diagrama do modelo de dados, estrutura de apps Django e fluxo entre templates ✅.
- [x] **Fase 3 — Configuração do Ambiente** (3 dias): projeto Django criado, ambiente virtual, apps iniciais (`obras`, `avaliacoes`, `quiz`), banco SQLite, repositório de versionamento.
- [ ] **Fase 4 — Backend: Modelos, Admin e Controle de Acesso** (2 semanas): Modelos implementados e migrados (incluindo `Perfil` e `ResultadoQuiz`), controle de acesso habilitado com login obrigatório em toda a plataforma e autocadastro aberto para professores, alunos e público em geral, cadastro de conteúdo habilitado via Django Admin com permissões específicas para a equipe da cliente, upload de ilustrações funcionando.
- [ ] **Fase 5 — Front-end: Home e Página da Obra** (2 semanas)
- [ ] **Fase 6 — Módulo de Avaliações** (1,5 semana)
- [ ] **Fase 7 — Módulo de Quiz** (2 semanas)
- [ ] **Fase 8 — Carga das 30 Obras** (2 semanas, em paralelo)
- [ ] **Fase 9 — Testes e Ajustes** (1 semana)
- [ ] **Fase 10 — Publicação** (3 dias)
- [ ] **Fase 11 — Acompanhamento Pós-lançamento** (contínuo)

> Wireframes das 5 telas principais (Home, Página da Obra, Avaliação, Quiz e Resultado do quiz), diagrama do modelo de dados (incluindo `Perfil` e `ResultadoQuiz`), estrutura de apps (incluindo `contas`) e fluxo entre templates (com o portão de login) estão documentados em uma página única (artefato entregue no chat, atualizado). Pendências que seguem em aberto: lista definitiva das 30 obras (depende da cliente), template de coleta de conteúdo para a cliente (deixado para depois, por decisão do projeto) e confirmação se `tempo_limite_segundos` é por quiz (padrão provisório usado no diagrama) ou por pergunta.

## Próximos passos sugeridos

1. Rodar o setup acima e confirmar que `python manage.py runserver` funciona e o Admin abre.
2. Fazer o primeiro commit no Git (ver acima) e, se for usar GitHub/GitLab, criar o repositório remoto.
3. Confirmar o escopo do campo `tempo_limite_segundos` (por quiz ou por pergunta) antes da Fase 4.
4. Definir a lista definitiva das 30 obras com a cliente e, quando fizer sentido, montar o template de coleta de conteúdo (deixado para depois).
5. Avançar para a **Fase 4**: implementar primeiro o app `contas` e o login obrigatório (base de tudo o mais), depois os demais `models.py` (`Obra`, `Questao`, `Alternativa`, `PerguntaQuiz`, `AlternativaQuiz`, `ResultadoQuiz`), migrações e cadastro via Django Admin, com base no diagrama atualizado da Fase 2.
