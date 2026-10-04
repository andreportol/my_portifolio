# Cobrança mensal controlada pelo portfólio

O vendedor controla a mensalidade no projeto `My_Portifolio`, app `cobrancas`. A conta e a chave API do Asaas ficam exclusivamente nesse projeto. A marmitaria consulta o estado e o Pix por uma API autenticada; não envia valor, vencimento, confirmação de pagamento ou instrução de liberação.

## Responsabilidades

- **Portfólio:** mantém a assinatura de ID 1, valor, vencimento, dia contratado, confirmação de pagamento, política de bloqueio, emissão/reconciliação do Pix e lembrete por e-mail.
- **Marmitaria:** mostra o Pix e aplica os bloqueios retornados pelo portfólio. Não possui modelos ou telas administrativas de assinatura e webhook. As tabelas antigas são preservadas exclusivamente para transferência do histórico e não controlam a aplicação.
- **Asaas:** recebe a emissão e envia a confirmação ao webhook do portfólio. A conta é do vendedor e a marmitaria é o cliente `cus_...`.

No Admin do **portfólio**, somente um superusuário pode administrar a assinatura. Enquanto houver pagamento emitido ou emissão pendente, valor, vencimento e dia contratado ficam protegidos também nessa interface: mudanças exigem reconciliar a cobrança no Asaas primeiro. Eventos do webhook não podem ser editados ou excluídos no Admin.

A API da marmitaria não oferece alteração: aceita apenas GET, autenticado por `X-Cobranca-Token`. O token permite consultar esta assinatura; não concede acesso ao Admin do portfólio nem à chave Asaas. Use HTTPS em produção. HTTP é aceito pelo cliente apenas em DEBUG com `localhost` ou `127.0.0.1`.

## Configuração do portfólio

Instale as dependências atualizadas e execute `python manage.py migrate`. Configure:

| Variável | Uso / exemplo |
| --- | --- |
| `DATABASE_URL` | PostgreSQL persistente em produção; necessário para bloqueio de linha na emissão |
| `COBRANCA_AUTOMATICA_ENABLED` | `True` após preparar a migração e a configuração |
| `COBRANCA_MARMITARIA_TOKEN` | Segredo exclusivo compartilhado com a marmitaria |
| `COBRANCA_VALOR_MENSAL` | Valor inicial, por exemplo `200.00`; não sobrescreve assinatura existente |
| `COBRANCA_PRIMEIRO_VENCIMENTO` | Data inicial AAAA-MM-DD; não sobrescreve assinatura existente |
| `COBRANCA_DIAS_ANTECEDENCIA` | `3` |
| `COBRANCA_DIAS_BLOQUEIO_GERENTE` | `2` |
| `COBRANCA_DIAS_BLOQUEIO_SITE` | `10` |
| `COBRANCA_TIME_ZONE` | `America/Campo_Grande` por padrão |
| `COBRANCA_GERENTE_EMAIL` | E-mail do pagador; o portfólio não consulta os usuários da marmitaria |
| `COBRANCA_DESCRICAO` | `Mensalidade do sistema Marmitaria Adriana` |
| `ASAAS_API_URL` | Sandbox: `https://api-sandbox.asaas.com/v3` |
| `ASAAS_API_KEY` | Credencial do vendedor, somente no portfólio |
| `ASAAS_CUSTOMER_ID` | Cliente `cus_...` da marmitaria |
| `ASAAS_WEBHOOK_TOKEN` | Segredo exclusivo para o webhook Asaas, diferente do token de consulta |
| `ASAAS_REQUEST_TIMEOUT` | `20` |
| `ASAAS_USER_AGENT` | Identificação da aplicação |

Configure SMTP no portfólio (`EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`). Sem `COBRANCA_GERENTE_EMAIL`, a emissão ocorre, mas o lembrete não é enviado. O backend console serve apenas para testes.

Configure o webhook Asaas para `https://DOMINIO-PORTFOLIO/cobrancas/asaas/webhook/`, eventos `PAYMENT_RECEIVED` e `PAYMENT_CONFIRMED`, com `ASAAS_WEBHOOK_TOKEN` no header `asaas-access-token`.

Agende **no portfólio**, diariamente, `python manage.py processar_cobranca_marmitaria`. Para executar às 8h de Campo Grande/Cuiabá, use `0 12 * * *` em um agendador configurado em UTC. Use apenas um agendador. Esse comando emite/reconcilia e envia o lembrete; a consulta de Pix também pode iniciar a emissão no portfólio.

## Configuração da marmitaria

```dotenv
COBRANCA_AUTOMATICA_ENABLED=True
COBRANCA_PORTFOLIO_URL=https://DOMINIO-PORTFOLIO
COBRANCA_PORTFOLIO_TOKEN=mesmo-segredo-de-COBRANCA_MARMITARIA_TOKEN
COBRANCA_PORTFOLIO_TIMEOUT=5
```

Remova da marmitaria as credenciais `ASAAS_*` e as antigas configurações de valor, vencimento, prazos e e-mail da mensalidade. Elas não são mais utilizadas. `PIX_CHAVE` continua sendo usada nos pedidos e é independente da mensalidade.

O agendamento Celery local da mensalidade foi removido. Tarefas antigas já enfileiradas não emitem nem enviam lembretes. O webhook antigo da marmitaria retorna HTTP 410 e não modifica registros.

**Disponibilidade:** quando a integração está habilitada e o portfólio não pode ser consultado, ou retorna dados inválidos, a marmitaria retorna HTTP 503 com a mensagem pública de problemas técnicos. Não usa vencimentos locais como alternativa de liberação. Admin permanece acessível para suporte. Desativar a integração é uma configuração de infraestrutura do vendedor, não uma opção no Admin da marmitaria.

## Transferência de uma assinatura existente

Faça a transferência em uma janela de manutenção, antes de ativar o novo agendador. Não mantenha os dois emissores rodando ao mesmo tempo.

1. Faça backup dos bancos. Pare o agendador/worker antigo e aguarde as emissões em andamento terminarem. Confira o vencimento e a cobrança corrente no Asaas.
2. Na marmitaria atualizada, exporte o histórico preservado nas tabelas antigas (o comando funciona também após a migração que remove os modelos ativos):

   ```bash
   python manage.py exportar_cobranca_legada --output cobranca-marmitaria.json
   ```

3. No portfólio, com as migrações aplicadas, cobrança desabilitada e tabelas de cobrança vazias:

   ```bash
   python manage.py importar_cobranca_marmitaria cobranca-marmitaria.json
   ```

   O comando preserva o vencimento corrente, dia contratado, valor, ID de pagamento, reserva de emissão, Pix, lembrete, data de pagamento e eventos já processados. Não acessa o Asaas. Recusa modelos diferentes, assinatura diferente de ID 1 e destino com dados; falhas revertem a importação inteira. Proteja o arquivo de transferência e retire-o após validar o backup e a importação.

4. Mova as credenciais e prazos para o portfólio, informe o e-mail do pagador, configure os tokens e atualize o webhook no Asaas. Habilite o controle no portfólio e confira `/cobrancas/api/marmitaria/estado/` com o token de consulta.
5. Publique a marmitaria com as configurações de consulta. Confirme que o Pix e o vencimento vêm do portfólio. Só então ative o agendador central e retire as credenciais Asaas da marmitaria.
6. Valide emissão, e-mail, pagamento e webhook no sandbox antes de produção. Não inicialize uma nova assinatura com uma data futura se já existe uma mensalidade pendente.

Para uma instalação sem assinatura anterior, cadastre a assinatura de ID 1 no Admin do portfólio ou configure o valor e o primeiro vencimento para inicializá-la.

## Ciclo e proteção contra duplicação

O dia contratado é preservado: 31/01 → 28/02 (29 em ano bissexto) → 31/03. O pagamento avança um mês a partir do vencimento contratado, não da data em que o cliente pagou.

Com vencimento em 10/10: gerente bloqueado a partir de 12/10 e site público a partir de 20/10, conforme os prazos do portfólio. Superusuários mantêm acesso administrativo. A página pública apresenta apenas **“Estamos com problemas técnicos. Tente novamente mais tarde.”**.

Antes da emissão, o portfólio consulta o Asaas por cliente, Pix e `externalReference` determinística do vencimento (`marmitaria-adriana-AAAA-MM-DD`). A referência foi preservada para recuperar cobranças anteriores à transferência. Valores divergentes ou múltiplas cobranças exigem reconciliação.

A reserva `emissao_pendente` é persistida antes do POST. Após resposta incerta, novas tentativas apenas procuram a cobrança existente: não fazem outro POST. Não limpe essa reserva sem verificar o Asaas. O pagamento é persistido antes de buscar o QR Code. Evento e confirmação são gravados na mesma transação; eventos repetidos não avançam duas vezes o ciclo. Um webhook recebido antes da associação retorna 503 para reenvio. Cobranças recuperadas já pagas avançam o ciclo sem reapresentar Pix pago.

A integração emite mensalidades avulsas via `/payments`, sem criar `/subscriptions`. O cliente paga o Pix manualmente.

Referências oficiais: [Criar cobrança](https://docs.asaas.com/reference/criar-nova-cobranca), [Eventos de cobrança](https://docs.asaas.com/docs/webhook-para-cobrancas), [Sandbox](https://docs.asaas.com/docs/sandbox).
