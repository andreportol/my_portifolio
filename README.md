# My_Portifolio

Portfólio em Django 4.2 com formulário de contato integrado ao provedor de e-mail Resend (via API HTTP). Inclui páginas de projetos, biografia e contato, pronto para deploy na Railway ou execução local.

## Stack
- Python 3.11+ (desenvolvido/testado com 3.13)
- Django 4.2
- Resend (envio de e-mail)
- Whitenoise (arquivos estáticos em produção)

## Pré-requisitos
- Python e `pip`
- Virtualenv (recomendado)
- Conta no Resend para obter `RESEND_API_KEY`

## Configuração
1) Crie e ative o ambiente virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
2) Instale dependências:
   ```bash
   pip install -r requirements.txt
   ```
3) Crie um arquivo `.env` na raiz com base no `.env.example`:
   ```
   SECRET_KEY=change-me
   DEBUG=True
   GESTAO_OFICINA_LICENSE_SECRET=change-me-too
   CSRF_TRUSTED_ORIGINS=https://example.up.railway.app
   RESEND_API_KEY=your_resend_api_key
   EMAIL_FROM=onboarding@resend.dev
   CONTACT_EMAIL=destino@example.com
   ```
   - `EMAIL_FROM` pode ser um remetente verificado no Resend; caso contrário, use o fallback `onboarding@resend.dev`.
   - `CONTACT_EMAIL` é para onde o formulário envia as mensagens.
4) Rode migrações:
   ```bash
   python manage.py migrate
   ```

## Executando localmente
```bash
python manage.py runserver 8001
```
Abra http://localhost:8001/ e teste o formulário em `/contato/`.

Se a porta `8000` estiver ocupada por outro programa no Windows, use uma porta livre como `8001`.

## Acesso
- O link `Entrar` leva para `/entrar/`.
- O login autentica por e-mail e senha.
- Para testar localmente, crie um usuário Django com `python manage.py createsuperuser` e use o e-mail cadastrado para entrar.

## Gerador de licença
- O fluxo da página `/licencas/gestao-oficina/` usa o mesmo gerador do CLI `generate_license.py`.
- Exemplo de uso:
  ```bash
  python generate_license.py --machine-id 5e517465b1c11bb1998e21e3cfd5355c0859fbb745fbb179310615bde15f7780
  ```
- A saída segue o formato `GOF1.<payload base64url>.<assinatura>`.
- O payload inclui `app` e `machine_id`.
- O segredo de assinatura precisa ser o mesmo no CLI e na web: `GESTAO_OFICINA_LICENSE_SECRET`.
- Se você precisar compatibilidade com outro gerador, defina o mesmo valor no `.env` em todos os ambientes.
- A verificação da chave confere `GOF1`, assinatura, `app == "GestaoOficina"` e `machine_id`.
- A tela pede só o `ID da máquina`.

## Envio de e-mail (Resend)
- O formulário de contato usa o serviço em `core/services/email_service.py`, com HTML contendo Nome, Telefone, E-mail e Assunto.
- Para testar via shell:
  ```bash
  python manage.py shell
  >>> from core.services.email_service import enviar_email_contato
  >>> enviar_email_contato("Teste", "11999999999", "user@example.com", "Assunto de teste")
  ```

## Deploy na Railway
- Defina no painel:
  - `SECRET_KEY`
  - `DEBUG=False`
  - `CSRF_TRUSTED_ORIGINS=https://seu-projeto.up.railway.app`
  - `RESEND_API_KEY`
  - `EMAIL_FROM` (opcional, se quiser usar remetente próprio verificado)
  - `CONTACT_EMAIL`
- Comando de migração sugerido: `railway run python manage.py migrate`

## Notas
- Configurações SMTP antigas não são necessárias para o formulário (Resend é usado por padrão).
- Mensagens de sucesso/erro aparecem junto ao cartão do formulário para melhor visibilidade.
