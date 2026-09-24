# Turma da Gurizadinha

Site com conteúdo de obras infantis ilustradas, criado para uso de professores como material didático. Contará inicialmente com 30 histórias publicadas; cada obra disponibiliza texto completo, tópicos/resumo para uso em sala de aula, atividades de apoio para impressão (sem versão interativa — a única parte interativa da plataforma é o quiz) e um quiz com temporizador, pontuação e relatório de desempenho para o professor.

Stack: **Python + Django 5.2 (LTS)**, banco **SQLite** em desenvolvimento, front-end em templates Django (HTML/CSS/JS).

## Estrutura do projeto

```
turmadagurizadinha/
├── config/                 # settings, urls, wsgi/asgi do projeto
├── contas/                  # Fase 4 ✅ — autocadastro, login (por e-mail) e logout,
│                              #   login obrigatório em todo o site, troca de senha
├── obras/                  # Models da Fase 4 ✅ (Obra, Questao, Alternativa) — front-end
│                              #   completo (Home, Página da Obra) ainda é Fase 5
├── quiz/                    # ResultadoQuiz da Fase 4 ✅ — Módulo de Quiz interativo
│                              #   (PerguntaQuiz, AlternativaQuiz, temporizador) é Fase 7
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

**Controle de acesso (Fase 4 — implementado):** toda a plataforma exige login — público em geral, alunos e professores incluídos, todos com autocadastro aberto (nome, e-mail, tipo, senha) pelo app `contas`. O login é feito pelo e-mail (é ele que fica salvo no campo `username` do `User`, por baixo dos panos) e o "tipo" (professor/aluno/outro) é autodeclarado no cadastro, sem verificação — serve só para eventuais ajustes de UI no futuro. O login obrigatório é feito pelo `LoginRequiredMiddleware` do próprio Django (novidade da 5.1+): toda view exige login, exceto as duas marcadas com `@login_not_required` (`contas:login` e `contas:cadastro`) — o Django Admin cuida do login dele mesmo, sem precisar de marcação. A equipe da cliente continua usando o Django Admin separadamente, com conta de staff (ver grupo "Equipe editorial" abaixo). Com isso, o relatório de desempenho do quiz deixou de ficar só na sessão do navegador: agora cada tentativa é gravada em banco, vinculada à conta do usuário logado (model `ResultadoQuiz`, no app `quiz` — a lógica de gravar o resultado em si é Fase 7, quando o quiz ficar interativo).

**Redefinição de senha por e-mail (acréscimo ao escopo, pós-Fase 4):** a plataforma ganhou o fluxo padrão de "Esqueci minha senha" — o mesmo usado pela maioria dos sites, com link "Esqueceu a senha?" na tela de login: a pessoa informa o e-mail, recebe um link de redefinição (token que expira sozinho e não pode ser reaproveitado depois de usado) e define uma nova senha, sem que o site nunca revele se aquele e-mail está ou não cadastrado. Falta uma providência da cliente para esse recurso funcionar de fato: **escolher e cadastrar um servidor de envio de e-mail (SMTP)**. Sem isso configurado, os e-mails só aparecem no terminal de quem está rodando o projeto (bom para testar o fluxo, mas ninguém recebe de verdade). Duas opções ficaram prontas, com instruções passo a passo no arquivo `.env.example` (na raiz do projeto): **Brevo** (brevo.com) — gratuito para até 300 e-mails por dia, sem pedir cartão de crédito, configuração simples em poucos minutos — ou **Gmail**, caso a cliente prefira usar uma conta já existente (exige ativar a verificação em duas etapas e gerar uma "senha de app" em myaccount.google.com/apppasswords). Qualquer que seja a escolha, as credenciais vão só no arquivo `.env` local de cada ambiente — nunca no repositório (ver `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` e demais variáveis no `.env.example`).

**Permissões da equipe da cliente no Admin (Fase 4 — implementado):** ao rodar `migrate`, é criado automaticamente um grupo "Equipe editorial" com permissão só para cadastrar/editar/excluir `Obra`, `Questao` e `Alternativa` — sem acesso a usuários, grupos ou aos resultados do quiz. Para dar acesso de conteúdo a alguém da equipe da cliente: crie a conta dela (pelo autocadastro do próprio site), marque `is_staff` para ela poder entrar no Admin e adicione-a ao grupo "Equipe editorial" — tudo isso pela tela de usuários do Django Admin (`/admin/auth/user/`).

**Cadastro de conteúdo fora do Admin (acréscimo ao escopo, pós-Fase 4):** para quem só vai cadastrar obra, o Django Admin é uma tela pensada para desenvolvedor (bastante técnica). Foi acrescentada uma tela própria, com a cara do próprio site, para isso: quem tem a permissão de cadastro (grupo "Equipe editorial" ou superusuário) vê um botão "Cadastrar obra" direto na Home e também um link "Gerenciar obras" no menu do usuário. De lá dá para criar/editar/excluir uma `Obra` (incluindo o upload da `capa`), cadastrar as perguntas ("Atividades de apoio") e as alternativas de cada uma, com o slug da URL gerado automaticamente a partir do título quando não for informado. O Django Admin continua existindo do mesmo jeito — esta é só uma porta de entrada mais simples para quem não precisa do resto do Admin. Quem não tem essa permissão nem vê o botão na Home; se tentar acessar a URL direto, recebe uma mensagem de acesso negado.

**Segurança e versão do Django (atualização):** o projeto foi atualizado do Django 5.1 (suporte de segurança encerrado em 31/12/2025) para o **Django 5.2 LTS** (suporte de segurança até abr/2028). O `SECRET_KEY` deixou de ter um valor fixo versionado no `settings.py`: agora ele é lido de um arquivo `.env` local (não versionado — carregado via `python-dotenv`), com `.env.example` servindo de modelo no repositório. Em desenvolvimento, se o `.env` não existir, o projeto ainda roda com uma chave gerada na hora (só localmente); em produção (`DEBUG=False`), a variável de ambiente passa a ser obrigatória — configurada diretamente no servidor na Fase 10, nunca no repositório.

**Ilustração da obra (decisão revista):** a ideia de várias ilustrações por obra (`IlustracaoObra`) foi **descartada** — a cliente confirmou que cada obra tem só uma imagem, a própria `capa` (campo já existente em `Obra`), então não há necessidade dessa tabela extra.

**App `avaliacoes` removido (esboço da cliente):** a cliente enviou um esboço das telas de Home e Página da Obra. A partir dele, ficou definido que a única parte interativa da plataforma é o quiz — não existe mais uma "avaliação interativa" separada. As perguntas com resposta (antes no app `avaliacoes`) viraram os models `Questao` e `Alternativa` dentro do próprio app `obras`, exibidos como uma seção "Atividades de apoio para impressão" na própria página da obra (sem gabarito na tela/impressão — `Alternativa.correta` já cobre isso, é regra de exibição). O app `avaliacoes` deixou de existir: removido de `LOCAL_APPS`, de `config/urls.py`, do link correspondente em `obras/templates/obras/detalhe.html` e da pasta do projeto.

**Outras confirmações do esboço:** a `Obra` ganhou um campo `texto_breve` (subtítulo/breve descrição, usado no card da Home e no topo da página da obra) ✅ implementado na Fase 4. O menu do usuário logado ("Controle de abas": Django Admin — só para a equipe da cliente —, Trocar senha e Sair) também já está na navbar ✅. Ficam para a Fase 5: a seção de apresentação da plataforma na Home com o logotipo (arquivo estático, sem campo no banco), e os itens "Quem somos" e "A Turminha" na navbar (páginas institucionais, com texto fixo no template por enquanto — sem model, a cliente pode pedir para tornar editável depois).

*(De passagem, o `tempo_limite_segundos` já estava confirmado como um tempo único para o quiz inteiro, não por pergunta — não é mais um ponto em aberto.)*

**Nota sobre o cronograma:** com as avaliações incorporadas à Fase 5, a **Fase 6 — Módulo de Avaliações**, como estava descrita, deixou de fazer sentido como etapa separada — seu conteúdo já está coberto pela Fase 5. Mantive a linha dela no checklist abaixo, mas marcada como incorporada, sem excluir ou renumerar as fases seguintes por conta própria — isso pode ter efeito no prazo/custo combinado com a cliente, então prefiro que essa decisão (remover de fato a fase, ajustar duração da Fase 5, ou manter como está) seja sua.

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
6. Aplique as migrações (cria as tabelas de `Obra`/`Questao`/`Alternativa`/`Perfil`/`ResultadoQuiz` e o grupo "Equipe editorial" — ver acima) e crie um super usuário para o Django Admin:
   ```powershell
   python manage.py migrate
   python manage.py createsuperuser
   ```
   > Se o seu banco (`db.sqlite3`) já existia de antes da Fase 4, rode `python manage.py migrate` mesmo assim — ele só aplica o que faltar.
7. Suba o servidor de desenvolvimento:
   ```powershell
   python manage.py runserver
   ```
   Acesse http://127.0.0.1:8000/ (site — vai pedir login) e http://127.0.0.1:8000/admin/ (admin, com o super usuário criado acima). Pela Home logada dá para cadastrar uma `Obra` de teste no Admin e ver ela aparecer.

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
- [x] **Fase 4 — Backend: Modelos, Admin e Controle de Acesso** (2 semanas): Modelos implementados e migrados (`Obra`, `Questao` e `Alternativa` — estas duas últimas movidas do extinto app `avaliacoes` para `obras` —, `Perfil` e `ResultadoQuiz`) ✅. Controle de acesso habilitado com login obrigatório em toda a plataforma (`LoginRequiredMiddleware`) e autocadastro aberto para professores, alunos e público em geral, login por e-mail, troca de senha, e o menu do usuário logado na navbar (Django Admin para staff, trocar senha, sair) ✅. Cadastro de conteúdo habilitado via Django Admin com permissões específicas para a equipe da cliente (grupo "Equipe editorial", criado automaticamente no `migrate`) ✅. Upload de ilustrações (`capa` da `Obra`) funcionando, validado com um arquivo de teste ✅. Front-end visual completo (grade de cards, layout da página da obra) fica para a Fase 5 — por ora as views já consultam o banco de verdade, só com estilo simples.
  - **Acréscimo pós-Fase 4:** tela própria de cadastro de conteúdo fora do Django Admin (`/gerenciar/`), acessível direto pela Home para quem tem permissão — ver nota "Cadastro de conteúdo fora do Admin" acima. Não estava no cronograma original; ficou registrado aqui para a cliente ter ciência.
- [ ] **Fase 5 — Front-end: Home e Página da Obra** (2 semanas): Home (apresentação da plataforma, logotipo, grade das obras), páginas institucionais "Quem somos" e "A Turminha" (texto fixo no template), e página da obra completa (texto, tópicos, atividades de apoio para impressão, acesso ao quiz) — conforme esboço da cliente.
- [ ] ~~**Fase 6 — Módulo de Avaliações**~~ (1,5 semana) — **incorporada à Fase 5**: não existe mais avaliação interativa separada (só o quiz é interativo); ver nota acima. Decisão sobre ajustar oficialmente o cronograma ainda pendente com você.
- [ ] **Fase 7 — Módulo de Quiz** (2 semanas)
- [ ] **Fase 8 — Carga das 30 Obras** (2 semanas, em paralelo)
- [ ] **Fase 9 — Testes e Ajustes** (1 semana)
- [ ] **Fase 10 — Publicação** (3 dias)
- [ ] **Fase 11 — Acompanhamento Pós-lançamento** (contínuo)

> Wireframes das telas principais (Home, Página da Obra, Quiz e Resultado do quiz — sem tela própria de Avaliação, incorporada à página da obra), diagrama do modelo de dados (`Obra`, `Questao`/`Alternativa` agora em `obras`, `Perfil`, `ResultadoQuiz`), estrutura de apps (incluindo `contas`, sem `avaliacoes`) e fluxo entre templates (com o portão de login) estão documentados em uma página única (artefato entregue no chat, atualizado). Pendência que segue em aberto: lista definitiva das 30 obras (depende da cliente) — o template de coleta de conteúdo para a cliente segue deixado para depois, por decisão do projeto.

## Próximos passos sugeridos

1. Rodar `pip install -r requirements.txt`, `python manage.py migrate` e `python manage.py createsuperuser`; confirmar que o site pede login, que dá para se cadastrar e que o Admin abre.
2. Cadastrar uma `Obra` de teste (com `capa`, `texto_breve`, `texto_completo`, `topicos_resumo` e uma `Questao`/`Alternativa`) pelo Admin ou pela nova tela "Gerenciar obras" (`/gerenciar/`) e conferir que ela aparece na Home e na página da obra.
3. Criar contas de staff para a equipe da cliente e adicioná-las ao grupo "Equipe editorial" (ver nota de permissões acima).
4. Fazer commit no Git das mudanças da Fase 4 e, se ainda não tiver feito, criar o repositório remoto no GitHub.
5. Definir a lista definitiva das 30 obras com a cliente e, quando fizer sentido, montar o template de coleta de conteúdo (deixado para depois).
6. Decidir com a cliente se a Fase 6 sai formalmente do cronograma (e se isso afeta prazo/custo) ou se fica só como nota de incorporação.
7. Avançar para a **Fase 5**: Home (apresentação, logotipo, grade das obras), páginas institucionais "Quem somos" e "A Turminha", e o layout completo da página da obra — com base no esboço da cliente e nos dados que já existem a partir da Fase 4.
