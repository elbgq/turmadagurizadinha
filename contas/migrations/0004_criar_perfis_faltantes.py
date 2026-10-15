from django.db import migrations


def criar_perfis_faltantes(apps, schema_editor):
    """
    Cria Perfil (tipo "outro") para usuários que ficaram sem — criados por
    `createsuperuser` ou no Admin antes do sinal de contas/signals.py.
    """
    User = apps.get_model("auth", "User")
    Perfil = apps.get_model("contas", "Perfil")
    for user in User.objects.filter(perfil__isnull=True):
        Perfil.objects.create(user=user)


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0003_delete_configuracaosite"),
    ]

    operations = [
        migrations.RunPython(criar_perfis_faltantes, migrations.RunPython.noop),
    ]
