import json
from pathlib import Path

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cobrancas.models import AssinaturaSistema, EventoWebhookAsaas


class Command(BaseCommand):
    help = "Importa uma única vez o dumpdata da assinatura e eventos da marmitaria. Não acessa o Asaas."

    def add_arguments(self, parser):
        parser.add_argument('arquivo', type=Path)

    def handle(self, *args, **options):
        try:
            dados = json.loads(options['arquivo'].read_text(encoding='utf-8-sig'))
            if not isinstance(dados, list):
                raise ValueError('O arquivo deve ser uma lista dumpdata.')
            permitidos = {'financeiro.assinaturasistema', 'financeiro.eventowebhookasaas'}
            for item in dados:
                if item['model'] not in permitidos:
                    raise ValueError('O arquivo contém modelos não permitidos.')
                if item['model'] == 'financeiro.assinaturasistema' and item['pk'] != 1:
                    raise ValueError('Somente a assinatura de ID 1 pode ser importada.')
                item['model'] = item['model'].replace('financeiro.', 'cobrancas.', 1)
            assinaturas = [item for item in dados if item['model'] == 'cobrancas.assinaturasistema']
            if len(assinaturas) != 1:
                raise ValueError('O arquivo precisa conter exatamente uma assinatura.')
            objetos = list(serializers.deserialize('json', json.dumps(dados)))
            with transaction.atomic():
                if AssinaturaSistema.objects.exists() or EventoWebhookAsaas.objects.exists():
                    raise ValueError('O destino já possui dados de cobrança; importação cancelada.')
                for registro in objetos:
                    registro.object.full_clean()
                    registro.save()
        except Exception as exc:
            raise CommandError('Importação cancelada: confira o arquivo e utilize um destino vazio.') from exc
        self.stdout.write(self.style.SUCCESS('Assinatura e eventos importados; nenhuma cobrança foi emitida.'))
