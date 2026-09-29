# Turma da Gurizadinha — guia para o Claude Code

Plataforma web de obras infantis ilustradas para professores usarem como material didático
(texto completo, tópicos/resumo para o professor, atividade de apoio para impressão, quiz).
Cliente: Iolanda Vitoria Rohde Wilhelm. Desenvolvedor: Eloi. Contrato assinado em 11/09/2026
(cronograma no Anexo I — fases 1 a 11). Responda sempre em português.

## Stack e comandos

- Python + Django 5.2 LTS, SQLite (`db.sqlite3`), templates Django + CSS puro (`static/css/base.css`). Sem JS framework.
- Windows, VS Code, ambiente virtual em `venv/` (Claude Code roda em Git Bash):
  - Rodar: `venv/Scripts/python manage.py runserver`
  - Verificar: `venv/Scripts/python manage.py check` e `venv/Scripts/python manage.py makemigrations --check --dry-run`
  - Testes: `venv/Scripts/python manage.py test`
  - Consultar dados: `venv/Scripts/python manage.py shell -c "from obras.models import Obra; print(Obra.objects.count())"`
- Dependências em `requirements.txt`. Segredos no `.env` (modelo em `.env.example`) — nunca ler, exibir ou commitar o `.env`.

## Estrutura

- `config/` — settings e urls raiz.
- `contas/` — cadastro (autocadastro aberto), login por e-mail, senha, `Perfil` (tipo: professor/aluno/outro).
- `obras/` — `Obra`, `Questao`, `Alternativa`; home, página da obra, "Quem somos", "A Turminha"; gestão de conteúdo fora do Admin em `/gerenciar/` (permissões `obras.*_obra`, grupo "Equipe editorial").
- `quiz/` — `ResultadoQuiz`; telas do quiz e do resultado ainda são placeholders (Fase 7).
- `templates/base.html`, `templates/partials/` (navbar, footer); `static/img/` (logo, personagens).

## Regras do projeto (não quebrar)

- Login obrigatório em TODO o site via `LoginRequiredMiddleware`. Só login, cadastro e recuperação de senha usam `@login_not_required`. Páginas institucionais também exigem login.
- Nome do projeto é "Turma da Gurizadinha" — nunca "Clube da Gurizadinha", mesmo que o Manual de Marca use esse nome.
- Identidade visual do Manual de Marca: cores `#4B576B`, `#39404A`, `#FCEECC`, `#F8C140` (variáveis `--cor-*` em `base.css`); fontes Boogaloo (títulos) e Work Sans (texto). Reaproveitar o padrão de card existente (fundo `--cor-card`, borda `--cor-destaque`, `border-radius: 12px`), layout que empilha em telas ≤ 900px.
- Textos institucionais tirados do Manual de Marca entram como estão no manual (decisão da cliente de 28/09/2026).
- Imagens de personagens: só a ilustração-base, sem quadros de variações/expressões/acessórios.
- Fora de escopo: apps `emocoes`, `avaliacoes`, `relatorios`; cobrança/assinatura.
- Atividade de apoio não mostra gabarito na tela nem no impresso.

## Como trabalhar

- Uma tarefa por sessão. Para features grandes, apresente um plano antes de editar.
- Toda feature nova vem com testes (Django `TestCase`, com usuário logado). Antes de dizer que terminou: `check`, `makemigrations --check` e `test` verdes.
- Migrations: nunca editar uma migration já aplicada; criar nova. Antes de migration que altere tabela com dados, copiar `db.sqlite3` para `db.backup.sqlite3`.
- Nunca rodar `flush`, apagar `db.sqlite3` ou arquivos de `media/` sem pedir confirmação.
- Commits pequenos, mensagem em português com a fase: `Fase 7: temporizador do quiz`.
- Mantenha comentários e docstrings em português, no estilo já usado no código.

## Estado atual (atualizar ao fim de cada sessão)

- Fases 1–4 entregues (Relatórios Técnicos 2 e 3). Fase 5 quase pronta: Home, Quem somos e A Turminha feitas; falta o layout final da página da obra (`obras/templates/obras/detalhe.html`). A Turminha aguarda aprovação da cliente.
- **28/09/2026 (via Cowork, sem VS Code — créditos baixos no Claude Code):** upload de PDF da "Atividade de apoio" implementado (acréscimo à Fase 6, ver README.md) — `Obra.atividade_pdf` (migration `0005_obra_atividade_pdf`), `obras/validators.py` (`validar_pdf`, 10 MB + assinatura `%PDF-`), `obras/signals.py` (limpeza do arquivo antigo/excluído, registrado em `ObrasConfig.ready()`), campo no `ObraForm`, view+rota protegida `obras:atividade_pdf` (`obra/<slug>/atividade.pdf`), botão de download em `detalhe.html` (convive com as perguntas e some na impressão). 13 testes novos em `obras/tests.py`, todos verdes (`check`, `makemigrations --check --dry-run` e `test`).
- **28/09/2026 (via Cowork):** correção do espaçamento entre parágrafos do texto da obra (`.obra-texto` em `base.css` — faltava `line-height`) e do bug de `<p>` aninhado em volta de `|linebreaks` em `detalhe.html` (corrigido). Inclusão de "Categoria da Obra" em `detalhe.html`, antes de "Tópicos para o professor" — rótulo em Boogaloo (`.obra-categoria__rotulo`), valor em Work Sans, no mesmo padrão visual de "Tópicos para o professor".
- **29/09/2026 (via Cowork):** conteúdo institucional editável — "Quem somos" e "A Turminha" deixam de ser templates fixos e passam a ser editáveis pela Equipe Editorial, sem depender do desenvolvedor (pedido da cliente). Modelos novos `PaginaQuemSomos`/`ValorQuemSomos`/`PaginaATurminha`/`PersonagemATurminha` (`obras/models.py`, singletons via `pk=1`), migration de schema `0006` e migration de dados `0007_seed_conteudo_institucional` (semeia o texto que já estava fixo nos templates + copia as imagens de `static/img/personagens/a_turminha/` para `media/institucional/`, e concede `change_paginaquemsomos`/`change_paginaaturminha` — e demais permissões das 4 tabelas — ao grupo "Equipe editorial"). Telas `/gerenciar/quem-somos/` e `/gerenciar/a-turminha/` (formulário + formset inline, mesmo padrão de `QuestaoFormSet`), com adicionar/remover/reordenar itens (Valores e Personagens) e troca de imagem por seção/personagem — decisão da cliente em 29/09/2026 (perguntado via `AskUserQuestion`: lista editável para Valores, imagens também editáveis). Links a partir de `/gerenciar/` (lista de obras) e botão "Editar esta página" nas próprias páginas públicas, condicionados à permissão. 11 testes novos em `obras/tests.py` (`ConteudoInstitucionalTests`), todos verdes junto com os 13 já existentes (24 no total).
- **Migrations pendentes no seu ambiente real:** as migrations `0005` (PDF), `0006` e `0007` (conteúdo institucional) foram geradas e testadas só num checkout espelhado neste ambiente Cowork — nunca puderam ser aplicadas direto na sua máquina. **Antes de usar essas funcionalidades**, copie `db.sqlite3` para `db.backup.sqlite3` e rode `python manage.py migrate obras`. A migration `0007` grava arquivos em `media/institucional/` na hora que roda (copiando de `static/img/personagens/a_turminha/`) — as páginas "Quem somos"/"A Turminha" devem ficar com a mesma aparência de antes logo depois.
- Problemas conhecidos:
  - Usuários criados por `createsuperuser`/Admin ficam sem `Perfil`, e `ResultadoQuiz` exige Perfil → criar signal `post_save` ou apontar a FK para `User`.
  - `.env.example` está no `.gitignore` (deveria ser versionado).
- Cobertura de testes: 24 testes automatizados em `obras/tests.py` (upload de PDF da atividade de apoio + conteúdo institucional editável). `contas` e `quiz` ainda sem cobertura.
- Próximas sessões (ver plano no projeto do Cowork): S0 higiene → S1 página da obra → ~~S2 PDF das atividades (Fase 6)~~ feito 28/09/2026 via Cowork → S3–S5 quiz e turmas com relatório por turma/aluno (Fase 7) → S6 comando `importar_obras` (Fase 8) → S7 homologação → S8 testes (Fase 9) → S9 produção (Fase 10).
- Pendências da cliente: lista das 30 obras; confirmar se os 12 contos clássicos no banco são só teste; hospedagem com banco e mídia persistentes.
