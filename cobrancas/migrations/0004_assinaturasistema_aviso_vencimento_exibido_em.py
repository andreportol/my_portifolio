from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cobrancas', '0003_assinaturasistema_vencimento_pix'),
    ]

    operations = [
        migrations.AddField(
            model_name='assinaturasistema',
            name='aviso_vencimento_exibido_em',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='assinaturasistema',
            name='aviso_vencimento_exibido_superuser_em',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
    ]
