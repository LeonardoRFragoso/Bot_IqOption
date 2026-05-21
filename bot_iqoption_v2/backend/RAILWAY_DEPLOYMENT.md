# Deployment no Railway

## Pré-requisitos

1. Conta no Railway (https://railway.app)
2. Railway CLI instalado: `npm install -g @railway/cli`
3. Git configurado

## Passos para Deploy

### 1. Conectar ao Railway

```bash
railway login
```

### 2. Inicializar o Projeto no Railway

```bash
cd bot_iqoption_v2/backend
railway init
```

Selecione:
- Nome do projeto: `bot-iqoption-backend`
- Ambiente: `production`

### 3. Adicionar Banco de Dados PostgreSQL

```bash
railway add
```

Selecione `PostgreSQL` e confirme. O Railway criará automaticamente a variável `DATABASE_URL`.

### 4. Configurar Variáveis de Ambiente

```bash
railway variables set SECRET_KEY="seu-secret-key-aqui"
railway variables set DEBUG=False
railway variables set ALLOWED_HOSTS="seu-dominio.railway.app,seu-dominio.com"
railway variables set MERCADOPAGO_PUBLIC_KEY="sua-chave-publica"
railway variables set MERCADOPAGO_ACCESS_TOKEN="seu-access-token"
railway variables set MERCADOPAGO_NOTIFICATION_URL="https://seu-dominio.railway.app/api/billing/webhook/"
railway variables set FRONTEND_URL="https://seu-frontend.com"
railway variables set PLATFORM_ADMIN_EMAIL="seu-email@example.com"
railway variables set CORS_ALLOWED_ORIGINS="https://seu-frontend.com,https://www.seu-frontend.com"
```

### 5. Deploy

```bash
railway up
```

Ou via GitHub (recomendado):

1. Faça push do código para GitHub
2. No painel do Railway, conecte seu repositório
3. Configure o branch para deploy automático

## Verificar Status

```bash
railway status
railway logs
```

## Troubleshooting

### Erro: ModuleNotFoundError: No module named 'pkg_resources'

**Solução:** Certifique-se de que `setuptools` está no `requirements.txt`

### Erro: ModuleNotFoundError: No module named 'dj_database_url'

**Solução:** Certifique-se de que `dj-database-url` está no `requirements.txt`

### Erro: Database connection failed

**Solução:** Verifique se a variável `DATABASE_URL` foi criada automaticamente pelo Railway ao adicionar PostgreSQL

## Variáveis de Ambiente Necessárias

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `SECRET_KEY` | Chave secreta do Django | `your-secret-key-here` |
| `DEBUG` | Modo debug (deve ser False em produção) | `False` |
| `ALLOWED_HOSTS` | Hosts permitidos | `seu-dominio.railway.app` |
| `DATABASE_URL` | URL do banco de dados (criada automaticamente) | `postgresql://...` |
| `MERCADOPAGO_PUBLIC_KEY` | Chave pública do Mercado Pago | `APP_USR-...` |
| `MERCADOPAGO_ACCESS_TOKEN` | Token de acesso do Mercado Pago | `APP_USR-...` |
| `MERCADOPAGO_NOTIFICATION_URL` | URL para webhooks do Mercado Pago | `https://seu-dominio.railway.app/api/billing/webhook/` |
| `FRONTEND_URL` | URL do frontend | `https://seu-frontend.com` |
| `PLATFORM_ADMIN_EMAIL` | Email do admin da plataforma | `seu-email@example.com` |
| `CORS_ALLOWED_ORIGINS` | Origens CORS permitidas | `https://seu-frontend.com` |

## Monitoramento

- Logs: `railway logs -f` (tempo real)
- Métricas: Acesse o painel do Railway
- Alertas: Configure notificações no painel

## Rollback

```bash
railway rollback
```

## Mais Informações

- Documentação Railway: https://docs.railway.app
- Django Deployment: https://docs.djangoproject.com/en/4.2/howto/deployment/
