import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory, override_settings

from cobrancas.billing import garantir_cobranca_pix, confirmar_pagamento, estado_cobranca
from cobrancas.models import AssinaturaSistema, EventoWebhookAsaas
from cobrancas.views import webhook_asaas


@override_settings(COBRANCA_AUTOMATICA_ENABLED=True, ASAAS_API_KEY='test', ASAAS_CUSTOMER_ID='cus_test', ASAAS_WEBHOOK_TOKEN='secret', COBRANCA_PRIMEIRO_VENCIMENTO='2026-01-31', COBRANCA_VALOR_MENSAL=Decimal('200'), COBRANCA_DIAS_BLOQUEIO_GERENTE=2, COBRANCA_DIAS_BLOQUEIO_SITE=10)
class BillingTests(TestCase):
    def setUp(self):
        self.assinatura = AssinaturaSistema.objects.create(pk=1, vencimento_atual=date(2026, 1, 31), dia_vencimento=31, valor=Decimal('200'))
        self.factory = RequestFactory()

    def evento(self, event_id='evt_1', payment_id='pay_1', event_type='PAYMENT_RECEIVED'):
        request = self.factory.post('/financeiro/asaas/webhook/', data=json.dumps({'id':event_id, 'event':event_type, 'payment':{'id':payment_id, 'externalReference':'marmitaria-adriana-2026-01-31'}}), content_type='application/json', HTTP_ASAAS_ACCESS_TOKEN='secret')
        return webhook_asaas(request)

    def test_fevereiro_preserva_dia_31_para_marco(self):
        self.assinatura.asaas_payment_id = 'pay_1'
        self.assinatura.save()
        confirmar_pagamento('pay_1')
        self.assinatura.refresh_from_db()
        self.assertEqual(self.assinatura.vencimento_atual, date(2026, 2, 28))
        self.assinatura.asaas_payment_id = 'pay_2'
        self.assinatura.save()
        confirmar_pagamento('pay_2')
        self.assinatura.refresh_from_db()
        self.assertEqual(self.assinatura.vencimento_atual, date(2026, 3, 31))

    def test_limites_bloqueio(self):
        for dias, gerente, site in [(0,False,False),(1,False,False),(2,True,False),(9,True,False),(10,True,True)]:
            from datetime import timedelta
            with self.subTest(dias=dias):
                estado=estado_cobranca(date(2026,1,31)+timedelta(days=dias))
                self.assertEqual(estado['gerente_bloqueado'],gerente)
                self.assertEqual(estado['site_bloqueado'],site)

    def test_webhook_falhou_pode_ser_reenviado(self):
        self.assinatura.asaas_payment_id='pay_1'
        self.assinatura.save()
        with patch('cobrancas.views.confirmar_pagamento', side_effect=RuntimeError('falha temporária')):
            with self.assertRaises(RuntimeError): self.evento()
        self.assertFalse(EventoWebhookAsaas.objects.exists())
        self.assertEqual(self.evento().status_code,200)
        self.assinatura.refresh_from_db()
        self.assertEqual(self.assinatura.vencimento_atual,date(2026,2,28))
        self.assertEqual(self.evento().status_code,200)
        self.evento('evt_2',event_type='PAYMENT_CONFIRMED')
        self.assinatura.refresh_from_db()
        self.assertEqual(self.assinatura.vencimento_atual,date(2026,2,28))

    def test_webhook_antes_de_associacao_retorna_503_sem_gravar(self):
        self.assertEqual(self.evento().status_code,503)
        self.assertFalse(EventoWebhookAsaas.objects.exists())

    @patch('cobrancas.billing.AsaasClient')
    def test_repeticao_e_falha_no_qr_nao_reemitem(self, cls):
        client=cls.return_value
        client.buscar_cobranca.return_value=None
        client.criar_cobranca_pix.return_value={'id':'pay_1'}
        client.obter_pix.side_effect=[requests.Timeout(),{'payload':'pix'}]
        with self.assertRaises(requests.Timeout): garantir_cobranca_pix()
        self.assinatura.refresh_from_db()
        self.assertEqual(self.assinatura.asaas_payment_id,'pay_1')
        garantir_cobranca_pix()
        client.criar_cobranca_pix.assert_called_once()

    @patch('cobrancas.billing.AsaasClient')
    def test_timeout_post_reconcilia_sem_segundo_post(self, cls):
        client=cls.return_value
        client.buscar_cobranca.side_effect=[None,{'id':'pay_1','value':200,'status':'PENDING'}]
        client.criar_cobranca_pix.side_effect=requests.Timeout()
        client.obter_pix.return_value={'payload':'pix'}
        with self.assertRaises(requests.Timeout): garantir_cobranca_pix()
        garantir_cobranca_pix()
        client.criar_cobranca_pix.assert_called_once()
        self.assinatura.refresh_from_db()
        self.assertFalse(self.assinatura.emissao_pendente)

    @patch('cobrancas.billing.AsaasClient')
    def test_emissao_incerta_sem_resultado_nao_emite_de_novo(self, cls):
        from cobrancas.asaas import AsaasError
        self.assinatura.emissao_pendente=True
        self.assinatura.save()
        cls.return_value.buscar_cobranca.return_value=None
        with self.assertRaises(AsaasError): garantir_cobranca_pix()
        cls.return_value.criar_cobranca_pix.assert_not_called()

    def test_ano_bissexto_e_virada_do_ano(self):
        from cobrancas.billing import _proximo_mes
        self.assertEqual(_proximo_mes(date(2028,1,31),31),date(2028,2,29))
        self.assertEqual(_proximo_mes(date(2028,2,29),31),date(2028,3,31))
        self.assertEqual(_proximo_mes(date(2026,12,31),31),date(2027,1,31))

    @patch('cobrancas.billing.AsaasClient')
    def test_cobranca_recuperada_paga_avanca_sem_emitir_ou_mostrar_pix(self, cls):
        client=cls.return_value
        client.buscar_cobranca.return_value={'id':'pay_1','value':200,'status':'RECEIVED'}
        assinatura,pix=garantir_cobranca_pix()
        self.assertIsNone(pix)
        self.assertEqual(assinatura.vencimento_atual,date(2026,2,28))
        client.criar_cobranca_pix.assert_not_called()
        client.obter_pix.assert_not_called()

    @patch('cobrancas.billing.AsaasClient')
    def test_valor_divergente_nao_cria_cobranca_adicional(self, cls):
        from cobrancas.asaas import AsaasError
        cls.return_value.buscar_cobranca.return_value={'id':'pay_1','value':150,'status':'PENDING'}
        with self.assertRaises(AsaasError): garantir_cobranca_pix()
        cls.return_value.criar_cobranca_pix.assert_not_called()

    def test_webhook_exige_token_e_json_valido(self):
        request=self.factory.post('/financeiro/asaas/webhook/',data='{}',content_type='application/json')
        self.assertEqual(webhook_asaas(request).status_code,403)
        for data in ['null','[]','{"id":"evt_1","payment":[]}','{"id":"evt_1","event":"PAYMENT_RECEIVED","payment":{}}']:
            request=self.factory.post('/financeiro/asaas/webhook/',data=data,content_type='application/json',HTTP_ASAAS_ACCESS_TOKEN='secret')
            self.assertEqual(webhook_asaas(request).status_code,400)
        self.assertFalse(EventoWebhookAsaas.objects.exists())

    @patch('cobrancas.asaas.requests.request')
    def test_rejeicao_por_cpf_ausente_permite_nova_tentativa_apos_correcao(self, request):
        from cobrancas.asaas import AsaasError
        from unittest.mock import Mock
        def resposta(status, dados):
            response = Mock(status_code=status, ok=status == 200)
            response.json.return_value = dados
            return response
        request.side_effect = [
            resposta(200, {'data': []}),
            resposta(400, {'errors': [{'code': 'invalid_object', 'description': 'CPF/CNPJ ausente'}]}),
            resposta(200, {'data': []}),
            resposta(200, {'id': 'pay_1'}),
            resposta(200, {'payload': 'pix_1'}),
        ]
        with self.assertRaises(AsaasError):
            garantir_cobranca_pix()
        self.assinatura.refresh_from_db()
        self.assertFalse(self.assinatura.emissao_pendente)
        self.assertEqual(self.assinatura.asaas_payment_id, '')
        assinatura, pix = garantir_cobranca_pix()
        self.assertEqual(assinatura.asaas_payment_id, 'pay_1')
        self.assertEqual(pix['payload'], 'pix_1')

    @patch('cobrancas.billing.AsaasClient')
    def test_erro_incerto_nao_libera_reserva_nem_reemite(self, cls):
        from cobrancas.asaas import AsaasError
        client = cls.return_value
        client.buscar_cobranca.return_value = None
        for erro in [requests.Timeout(), AsaasError('Erro do servidor', status_code=500, errors=[{'code': 'internal_error'}]),
                     AsaasError('Proxy 400', status_code=400)]:
            with self.subTest(erro=type(erro).__name__, status=getattr(erro, 'status_code', None)):
                self.assinatura.emissao_pendente = False
                self.assinatura.save()
                client.criar_cobranca_pix.reset_mock()
                client.criar_cobranca_pix.side_effect = erro
                with self.assertRaises(type(erro)):
                    garantir_cobranca_pix()
                self.assinatura.refresh_from_db()
                self.assertTrue(self.assinatura.emissao_pendente)
                with self.assertRaises(AsaasError):
                    garantir_cobranca_pix()
                client.criar_cobranca_pix.assert_called_once()


@override_settings(COBRANCA_AUTOMATICA_ENABLED=True, ASAAS_API_KEY='test',
    ASAAS_CUSTOMER_ID='cus_test', COBRANCA_MARMITARIA_TOKEN='read-token',
    COBRANCA_PRIMEIRO_VENCIMENTO='2026-10-10', COBRANCA_VALOR_MENSAL=Decimal('200'))
class CentralApiTests(TestCase):
    def setUp(self):
        self.assinatura = AssinaturaSistema.objects.create(pk=1,
            vencimento_atual=date(2026, 10, 10), dia_vencimento=10, valor=Decimal('200'))
        self.url = '/cobrancas/api/marmitaria/estado/'

    def test_exige_token_e_nao_permite_escrever_datas(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.get(self.url, HTTP_X_COBRANCA_TOKEN='wrong').status_code, 403)
        response = self.client.get(self.url, HTTP_X_COBRANCA_TOKEN='read-token')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['assinatura']['vencimento_atual'], '2026-10-10')
        self.assertNotIn('ASAAS_API_KEY', response.content.decode())
        self.assertEqual(response['Cache-Control'], 'no-store')
        for method in ['post', 'put', 'patch', 'delete']:
            response = getattr(self.client, method)(self.url,
                data=json.dumps({'vencimento_atual': '2099-01-01', 'valor': '0.01'}),
                content_type='application/json', HTTP_X_COBRANCA_TOKEN='read-token')
            self.assertEqual(response.status_code, 405)
        self.assinatura.refresh_from_db()
        self.assertEqual(self.assinatura.vencimento_atual, date(2026, 10, 10))

    @patch('cobrancas.views.garantir_cobranca_pix')
    def test_pix_e_consultado_somente_depois_da_autenticacao(self, garantir):
        url = '/cobrancas/api/marmitaria/pix/'
        self.assertEqual(self.client.get(url).status_code, 403)
        garantir.assert_not_called()
        garantir.return_value = (self.assinatura, {'payload': 'pix'})
        response = self.client.get(url, HTTP_X_COBRANCA_TOKEN='read-token')
        self.assertEqual(response.json()['pix'], {'payload': 'pix'})

    @override_settings(ASAAS_API_KEY='')
    def test_configuracao_incompleta_nao_responde_liberacao(self):
        self.assertEqual(self.client.get(self.url, HTTP_X_COBRANCA_TOKEN='read-token').status_code, 503)

    def test_admin_comum_do_portfolio_nao_edita_assinatura(self):
        user = get_user_model().objects.create_user(username='staff', password='test', is_staff=True)
        self.client.force_login(user)
        response = self.client.post(f'/admin/cobrancas/assinaturasistema/{self.assinatura.pk}/change/',
            {'vencimento_atual': '2099-01-01', 'dia_vencimento': 1, 'valor': '0.01'})
        self.assertEqual(response.status_code, 403)

    def test_vendedor_edita_no_portfolio_quando_nao_ha_emissao(self):
        user = get_user_model().objects.create_superuser(username='vendedor', password='test', email='test@example.com')
        self.client.force_login(user)
        url = f'/admin/cobrancas/assinaturasistema/{self.assinatura.pk}/change/'
        response = self.client.post(url, {'vencimento_atual': '2026-10-15', 'dia_vencimento': 15, 'valor': '250.00'})
        self.assertEqual(response.status_code, 302)
        self.assinatura.refresh_from_db()
        self.assertEqual(self.assinatura.vencimento_atual, date(2026, 10, 15))
        self.assertEqual(self.assinatura.valor, Decimal('250'))
        self.assinatura.asaas_payment_id = 'pay_1'
        self.assinatura.save()
        self.client.post(url, {'vencimento_atual': '2099-01-01', 'dia_vencimento': 1, 'valor': '0.01'})
        self.assinatura.refresh_from_db()
        self.assertEqual(self.assinatura.vencimento_atual, date(2026, 10, 15))
        self.assertEqual(self.assinatura.valor, Decimal('250'))


class ImportacaoTests(TestCase):
    def _arquivo(self, dados):
        import tempfile
        from pathlib import Path
        arquivo = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        arquivo.close()
        path = Path(arquivo.name)
        self.addCleanup(path.unlink, missing_ok=True)
        path.write_text(json.dumps(dados), encoding='utf-8')
        return str(path)

    def _dados(self):
        return [
            {'model': 'financeiro.assinaturasistema', 'pk': 1, 'fields': {
                'vencimento_atual': '2026-01-31', 'dia_vencimento': 31, 'valor': '200.00',
                'asaas_payment_id': 'pay_anterior', 'emissao_pendente': True,
                'pix_copia_cola': 'pix_anterior', 'lembrete_enviado_em': '2026-01-28T12:00:00Z',
                'pago_em': '2025-12-31T12:00:00Z', 'criado_em': '2025-12-01T12:00:00Z',
                'atualizado_em': '2026-01-28T12:00:00Z', 'pix_expira_em': None,
            }},
            {'model': 'financeiro.eventowebhookasaas', 'pk': 1, 'fields': {
                'event_id': 'evt_anterior', 'event_type': 'PAYMENT_RECEIVED',
                'recebido_em': '2025-12-31T12:00:00Z', 'payload': {'id': 'evt_anterior'},
            }},
        ]

    @patch('cobrancas.asaas.requests.request')
    def test_preserva_cobranca_e_historico_sem_contatar_asaas(self, request):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        arquivo = self._arquivo(self._dados())
        call_command('importar_cobranca_marmitaria', arquivo)
        assinatura = AssinaturaSistema.objects.get(pk=1)
        self.assertEqual(assinatura.vencimento_atual, date(2026, 1, 31))
        self.assertEqual(assinatura.asaas_payment_id, 'pay_anterior')
        self.assertTrue(assinatura.emissao_pendente)
        self.assertEqual(assinatura.pix_copia_cola, 'pix_anterior')
        self.assertEqual(assinatura.lembrete_enviado_em.day, 28)
        self.assertTrue(EventoWebhookAsaas.objects.filter(event_id='evt_anterior').exists())
        with self.assertRaises(CommandError):
            call_command('importar_cobranca_marmitaria', arquivo)
        self.assertEqual(EventoWebhookAsaas.objects.count(), 1)
        request.assert_not_called()

    def test_falha_no_evento_reverte_assinatura_importada(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        dados = self._dados()
        dados[1]['fields']['event_type'] = ''
        with self.assertRaises(CommandError):
            call_command('importar_cobranca_marmitaria', self._arquivo(dados))
        self.assertFalse(AssinaturaSistema.objects.exists())
        self.assertFalse(EventoWebhookAsaas.objects.exists())

    def test_nao_importa_modelos_estranhos(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        dados = self._dados()
        dados.append({'model': 'auth.user', 'pk': 1, 'fields': {}})
        with self.assertRaises(CommandError):
            call_command('importar_cobranca_marmitaria', self._arquivo(dados))
        self.assertFalse(AssinaturaSistema.objects.exists())


@override_settings(ASAAS_CUSTOMER_ID='cus_test')
class CorrecaoAsaasTests(TestCase):
    def test_paid_charge_is_not_modified(self):
        from cobrancas.asaas import AsaasClient, AsaasError
        with patch.object(AsaasClient, '_request', return_value={
                'customer': 'cus_test', 'billingType': 'PIX', 'status': 'RECEIVED'}) as request:
            with self.assertRaises(AsaasError):
                AsaasClient().corrigir_cobranca_pix('pay_test', Decimal('250'), date(2026, 10, 20))
            self.assertEqual(request.call_count, 1)

    def test_pending_charge_updates_same_id_and_reference(self):
        from cobrancas.asaas import AsaasClient
        with patch.object(AsaasClient, '_request', side_effect=[
            {'customer': 'cus_test', 'billingType': 'PIX', 'status': 'PENDING'},
            {'data': []},
            {'id': 'pay_test', 'value': 250, 'dueDate': '2026-10-20',
             'externalReference': 'marmitaria-adriana-2026-10-20'},
        ]) as request:
            AsaasClient().corrigir_cobranca_pix('pay_test', Decimal('250'), date(2026, 10, 20))
            self.assertEqual(request.call_args.args, ('PUT', '/payments/pay_test'))
            self.assertEqual(request.call_args.kwargs['json']['value'], 250)
