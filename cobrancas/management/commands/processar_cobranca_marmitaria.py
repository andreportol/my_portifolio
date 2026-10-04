from django.core.management.base import BaseCommand, CommandError
from cobrancas.billing import preparar_e_enviar_cobranca


class Command(BaseCommand):
    help = "Emite/reconcilia a mensalidade da Marmitaria e envia o lembrete pelo portfólio."

    def handle(self, *args, **options):
        try:
            resultado = preparar_e_enviar_cobranca()
        except Exception as exc:
            raise CommandError("Falha na cobrança central; consulte os logs e reconcilie no Asaas.") from exc
        self.stdout.write(resultado)
