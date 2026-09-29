from pathlib import Path

from django.apps import apps as apps_reais
from django.conf import settings
from django.contrib.auth.management import create_permissions
from django.core.files import File
from django.db import migrations

NOME_GRUPO = "Equipe editorial"

# Permissões das 4 novas tabelas — segue o padrão da migration 0002
# (add/change/delete/view por model), concedidas ao mesmo grupo.
CODENAMES_NOVOS = [
    "add_paginaquemsomos", "change_paginaquemsomos", "delete_paginaquemsomos", "view_paginaquemsomos",
    "add_valorquemsomos", "change_valorquemsomos", "delete_valorquemsomos", "view_valorquemsomos",
    "add_paginaaturminha", "change_paginaaturminha", "delete_paginaaturminha", "view_paginaaturminha",
    "add_personagematurminha", "change_personagematurminha", "delete_personagematurminha", "view_personagematurminha",
]

# Textos atuais, copiados de obras/templates/obras/quem_somos.html e
# a_turminha.html tal como estavam ANTES desta migração (conteúdo fixo
# desde a Fase 5, a partir do Manual de Marca "Turma da Gurizadinha").
# A partir desta migração o texto passa a viver no banco e vira
# editável pela equipe editorial em /gerenciar/quem-somos/ e
# /gerenciar/a-turminha/ — aqui só garantimos que a página continua
# com a aparência de antes logo após o deploy.
HISTORIA_TEXTO = (
    "O clube de assinatura de livros infantis é Gaúcho do coração do Rio Grande, "
    "nasceu na cidade de Agudo com a missão de transformar a leitura em um "
    "acessório fundamental da indumentária da gurizadinha.\n\n"
    "Das páginas dos livros, laçamos o motivo que une todas as gerações em uma "
    "roda de leitura: o prazer do conhecimento. Dividir histórias, alimentar a "
    "curiosidade, explorar o nosso pago e os mundos de imaginação, proporcionar "
    "essas experiências é o que motiva a nossa lida diária.\n\n"
    'Nosso propósito é conseguir um longo e sonoro "BAH" a cada kit aberto. Um '
    '"bah" daqueles que significam alegria, surpresa e empolgação em aprender '
    "algo novo, em ter o livro na mão.\n\n"
    "Como um bom gauchinho, somos apegados aos nossos costumes e temos muito "
    "orgulho em explaná-los ao mundo. Nas próximas páginas estão os nossos "
    "norteadores, as verdades que guiam o nosso trabalho."
)

MISSAO_TEXTO = (
    "Transformar a leitura em um acessório fundamental na indumentária da "
    "gurizadinha, gerando conhecimento e desenvolvimento educacional através de "
    "experiências criativas e lúdicas."
)

VISAO_TEXTO = (
    "Nos próximos 3 anos, ser reconhecido nacionalmente como o clube de leitura "
    "que incentiva o amor pelo livro e pela cultura gaúcha, levando conhecimento "
    "e criatividade à morada de 3.500 pequenos leitores."
)

VALORES = [
    ("Aprender é tri", "criatividade",
     "Buscamos gerar conhecimento e experiência, estimulando a criatividade e o "
     "pensamento crítico provocado por boas histórias."),
    ("De pai para filho", "família",
     "É um prazer aprochegar todas as gerações em uma roda de livro que vira "
     "costume e conhecimento."),
    ("De vereda", "logística",
     "Agilidade e eficiência para suprir as necessidades do cliente em todas as "
     "etapas, do pedido ao pós-venda."),
    ("Um exemplo loco de especial", "consciência",
     "O respeito guia as nossas escolhas, dos títulos adequados à diversidade de "
     "leitores até os recursos utilizados na produção e distribuição dos nossos "
     "materiais."),
    ("Gurizadinha daqui", "bairrismo",
     "Temos orgulho de aproximar as crianças e a cultura gaúcha por meio do "
     "apelo lúdico da leitura."),
    ("Não te atucana", "transparência",
     "Comprometidos e transparentes. Prezamos pela clareza nas ações e o "
     "contato direto com o cliente."),
]

TURMINHA_INTRO = (
    "Foram criados 4 personagens para o Clube da Gurizadinha. As ilustrações "
    "devem ser utilizadas sempre que possível, interagindo com letterings, "
    "imagens, etc."
)

PERSONAGENS = [
    ("Guri", "guri.png", (
        "Guri é o mascote da turma, um cusquinho comunitário que vive no bairro "
        "da Gurizadinha. Foi cuidando do Guri que todo mundo se conheceu, e hoje "
        "eles são inseparáveis.\n\n"
        "O Guri adora enterrar tesouros, às vezes ele esconde coisas importantes "
        "e o Cícero tem que procurar. Sempre colado no Germano, o Guri apronta "
        "com a Catarina e sai correndo do entrevero."
    )),
    ("Cícero", "cicero.png", (
        "Metido a sabichão, o Cícero conhece todas as lendas e costumes do Sul. "
        "Gosta de contar histórias para a Gurizadinha e é especialista em achar "
        "coisas perdidas – o Guri até tenta, mas ele sempre encontra os tesouros "
        "enterrados.\n\n"
        "O Cícero é alérgico a formigas, mas com os outros animais ele se dá "
        "muito bem, o quero-quero até pousa perto dele quando as lendas "
        "gauchescas são a história da vez."
    )),
    ("Germano", "germano.png", (
        "Germano é o líder da Gurizadinha, ele é um gauchinho de apartamento que "
        "adora tomar mate e passear com o Guri. O Germano não tem irmãos, mas "
        "cuida da Gurizadinha como se fossem uma família.\n\n"
        "Um tanto medroso, fica sempre atucanado quando suja suas alpargatas, "
        "não gosta de fazer coisas perigosas e fica um pouco assustado com a "
        "marra da Catarina."
    )),
    ("Catarina", "catarina.png", (
        "Catarina é uma gringa invocadinha. Apesar do seu tamanho e lacinho "
        "fofo, ela fica de cara quando inticam com a Gurizadinha, bate suas "
        "esporas e defende até os maiores.\n\n"
        "De pala no figurino e livro na mão, é fácil reconhecer de que pago ela "
        "vem. Tem um monte de irmãos, mas é com a Gurizadinha que ela acha tri "
        "brincar."
    )),
]

# Imagens de origem: já existem em static/img/personagens/a_turminha/
# (mesmas usadas hoje pelos templates fixos). Copiadas para dentro de
# cada ImageField para que o MEDIA_ROOT tenha um arquivo de verdade —
# assim a página continua com a mesma aparência logo após o deploy.
ORIGEM_IMAGENS = Path(settings.BASE_DIR) / "static" / "img" / "personagens" / "a_turminha"


def anexar_imagem(campo_imagem, nome_arquivo, novo_nome):
    origem = ORIGEM_IMAGENS / nome_arquivo
    if not origem.exists():
        return
    with open(origem, "rb") as f:
        campo_imagem.save(novo_nome, File(f), save=False)


def seed_conteudo(apps, schema_editor):
    # As Permission "add/change/delete/view_<model>" só existem depois
    # do sinal post_migrate (dispara só ao final de TODAS as migrações
    # deste comando) — força a criação agora, como na migration 0002.
    create_permissions(apps_reais.get_app_config("obras"), verbosity=0)

    PaginaQuemSomos = apps.get_model("obras", "PaginaQuemSomos")
    ValorQuemSomos = apps.get_model("obras", "ValorQuemSomos")
    PaginaATurminha = apps.get_model("obras", "PaginaATurminha")
    PersonagemATurminha = apps.get_model("obras", "PersonagemATurminha")

    pagina_qs = PaginaQuemSomos(
        pk=1,
        historia_texto=HISTORIA_TEXTO,
        missao_texto=MISSAO_TEXTO,
        visao_texto=VISAO_TEXTO,
    )
    anexar_imagem(pagina_qs.historia_imagem, "guri.png", "historia-guri.png")
    anexar_imagem(pagina_qs.missao_imagem, "germano.png", "missao-germano.png")
    anexar_imagem(pagina_qs.visao_imagem, "catarina.png", "visao-catarina.png")
    anexar_imagem(pagina_qs.valores_imagem, "cicero.png", "valores-cicero.png")
    pagina_qs.save()

    for i, (titulo, tema, texto) in enumerate(VALORES):
        ValorQuemSomos.objects.create(
            pagina=pagina_qs, titulo=titulo, tema=tema, texto=texto, ordem=i,
        )

    pagina_at = PaginaATurminha(pk=1, texto_introducao=TURMINHA_INTRO)
    anexar_imagem(pagina_at.imagem_grupo, "grupo.png", "grupo.png")
    pagina_at.save()

    for i, (nome, arquivo, texto) in enumerate(PERSONAGENS):
        personagem = PersonagemATurminha(pagina=pagina_at, nome=nome, texto=texto, ordem=i)
        anexar_imagem(personagem.imagem, arquivo, arquivo)
        personagem.save()

    # Grupo "Equipe editorial" ganha as novas permissões — .add() em vez
    # de .set() para preservar as permissões de obra/questao/alternativa
    # já concedidas pela migration 0002.
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupo, _ = Group.objects.get_or_create(name=NOME_GRUPO)
    permissoes = Permission.objects.filter(
        content_type__app_label="obras", codename__in=CODENAMES_NOVOS
    )
    grupo.permissions.add(*permissoes)


def remover_conteudo(apps, schema_editor):
    PaginaQuemSomos = apps.get_model("obras", "PaginaQuemSomos")
    PaginaATurminha = apps.get_model("obras", "PaginaATurminha")
    PaginaQuemSomos.objects.all().delete()
    PaginaATurminha.objects.all().delete()

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    try:
        grupo = Group.objects.get(name=NOME_GRUPO)
    except Group.DoesNotExist:
        return
    permissoes = Permission.objects.filter(
        content_type__app_label="obras", codename__in=CODENAMES_NOVOS
    )
    grupo.permissions.remove(*permissoes)


class Migration(migrations.Migration):

    dependencies = [
        ("obras", "0006_paginaaturminha_paginaquemsomos_personagematurminha_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_conteudo, remover_conteudo),
    ]
