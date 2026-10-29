from django.db import migrations

SLUG_OBRA = "lenda-da-erva-mate"

# Quiz de exemplo da "Lenda da Erva-Mate" (Fase 7, plano aprovado em
# 29/10/2026), no lugar dos exemplos de Porto Alegre do documento da
# cliente de 28/10/2026 — 6 perguntas tiradas do texto da obra. Cada
# item: (enunciado, [(alternativa, correta)], explicação). Sem imagem
# própria: até a cliente enviar as ilustrações, cada pergunta usa a
# imagem da página da obra (PerguntaQuiz.imagem_exibida).
PERGUNTAS = [
    (
        "Por que a tribo dos índios Guaranis resolveu ir embora daquele lugar?",
        [
            ("Porque chegou um inverno muito rigoroso.", False),
            ("Porque a caça daquele lugar já não os sustentava mais.", True),
            ("Porque foram expulsos por outra tribo.", False),
        ],
        "Os Guaranis perceberam que a caça já não os sustentava e partiram. Só um "
        "índio bem velho ficou, pois sua saúde não lhe dava forças para uma nova viagem.",
    ),
    (
        "Por que Yari ficou no lugar junto com o pai?",
        [
            ("Porque tinha medo da viagem.", False),
            ("Porque o pai mandou que ela ficasse.", False),
            ("Para cuidar da saúde do pai.", True),
        ],
        "Mesmo com o descontentamento do pai, Yari insistiu em ficar para cuidar dele. "
        "Ela caçava, plantava e cuidava da cabana.",
    ),
    (
        "Quem era, de verdade, o viajante loiro de olhos azuis que apareceu na floresta?",
        [
            ("Um caçador perdido.", False),
            ("Um enviado de Tupã.", True),
            ("Um índio de outra tribo.", False),
            ("Um comerciante de ervas.", False),
        ],
        "Depois de ser bem acolhido pela pequena família, o homem confessou que era "
        "enviado de Tupã, o Senhor do Trovão e criador do universo para os tupi-guaranis.",
    ),
    (
        "Como o enviado de Tupã ensinou a preparar a erva Caá?",
        [
            ("Cozida numa panela, junto com a comida.", False),
            ("Em infusão numa cabaça, sorvida quente com um canudo de taquara.", True),
            ("Com as folhas mastigadas cruas.", False),
        ],
        "A erva era preparada numa cabaça (o mesmo que porongo, material da cuia de "
        "chimarrão) e sorvida quente com um canudo de taquara. É a origem do nosso chimarrão.",
    ),
    (
        "O que passou a significar oferecer o chá de erva-mate a quem chegava na cabana?",
        [
            ("Um sinal de hospitalidade.", True),
            ("Um sinal de despedida.", False),
            ("Um pedido de ajuda.", False),
        ],
        "Sempre que alguém chegava, Yari e o pai ofereciam o chá na cabaça, e isso se "
        "tornou sinal de hospitalidade, como a roda de chimarrão até hoje.",
    ),
    (
        "Como Yari ficou conhecida no final da lenda?",
        [
            ("Rainha da Floresta.", False),
            ("Yari-Caá, a deusa da erva-mate.", True),
            ("Guardiã do Trovão.", False),
        ],
        "Yari plantou os galhos da erva para multiplicá-la e virou a deusa da "
        "erva-mate, conhecida como Yari-Caá.",
    ),
]


def criar_perguntas(apps, schema_editor):
    # Só semeia se a obra existir e ainda não tiver quiz — num banco novo
    # (ou num ambiente sem a obra) a migration não faz nada, e não
    # sobrescreve perguntas que a equipe editorial já tenha cadastrado.
    Obra = apps.get_model("obras", "Obra")
    PerguntaQuiz = apps.get_model("quiz", "PerguntaQuiz")
    AlternativaQuiz = apps.get_model("quiz", "AlternativaQuiz")
    obra = Obra.objects.filter(slug=SLUG_OBRA).first()
    if obra is None or PerguntaQuiz.objects.filter(obra=obra).exists():
        return
    for ordem, (enunciado, alternativas, explicacao) in enumerate(PERGUNTAS, start=1):
        pergunta = PerguntaQuiz.objects.create(
            obra=obra, ordem=ordem, enunciado=enunciado, explicacao=explicacao
        )
        for ordem_alt, (texto, correta) in enumerate(alternativas, start=1):
            AlternativaQuiz.objects.create(
                pergunta=pergunta, texto=texto, correta=correta, ordem=ordem_alt
            )


def remover_perguntas(apps, schema_editor):
    PerguntaQuiz = apps.get_model("quiz", "PerguntaQuiz")
    PerguntaQuiz.objects.filter(
        obra__slug=SLUG_OBRA, enunciado__in=[p[0] for p in PERGUNTAS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("obras", "0008_termo_glossario_resumo_pdf"),
        ("quiz", "0003_permissoes_equipe_editorial"),
    ]

    operations = [
        migrations.RunPython(criar_perguntas, remover_perguntas),
    ]
