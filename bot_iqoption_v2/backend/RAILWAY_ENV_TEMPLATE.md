# Variáveis de Ambiente para Railway

## Configuração Completa do .env para Railway

Copie e cole estas variáveis no painel do Railway (Settings > Environment Variables):

```
# === DJANGO ===
SECRET_KEY=sua-chave-secreta-super-segura-aqui-minimo-50-caracteres
DEBUG=False
ALLOWED_HOSTS=seu-dominio.railway.app,seu-dominio.com

# === DATABASE ===
# Esta variável é criada AUTOMATICAMENTE pelo Railway ao adicionar PostgreSQL
# NÃO precisa adicionar manualmente
# DATABASE_URL será algo como: postgresql://user:password@host:port/dbname

# === MERCADO PAGO ===
MERCADOPAGO_PUBLIC_KEY=APP_USR-e80c1a1d-aed8-441e-9265-6008e06da230
MERCADOPAGO_ACCESS_TOKEN=APP_USR-190324321334513-101219-9276719d370b181f22b61100e2bbf27d-175427787
MERCADOPAGO_CLIENT_ID=190324321334513
MERCADOPAGO_CLIENT_SECRET=AC1963p797Uhrx7pI9EXmD8b87uaXOH

# === WEBHOOKS ===
MERCADOPAGO_NOTIFICATION_URL=https://seu-dominio.railway.app/api/billing/webhook/

# === ASSINATURA ===
SUBSCRIPTION_PRICE=19.90
PLATFORM_ADMIN_EMAIL=seu-email@example.com

# === FRONTEND ===
FRONTEND_URL=https://seu-frontend.vercel.app
CORS_ALLOWED_ORIGINS=https://seu-frontend.vercel.app,https://www.seu-frontend.vercel.app
```

## Passo a Passo para Configurar no Railway

### 1. Acessar o Painel do Railway
- Vá para https://railway.app
- Selecione seu projeto `bot-iqoption-backend`
- Clique em **Settings**

### 2. Adicionar Variáveis de Ambiente
- Clique em **Environment Variables**
- Clique em **Add Variable**
- Adicione cada variável conforme o template acima

### 3. Variáveis Automáticas do Railway
Quando você adiciona PostgreSQL ao projeto, o Railway cria automaticamente:
- `DATABASE_URL` - URL de conexão com o banco de dados
- `DATABASE_PUBLIC_URL` - URL pública (opcional)

**NÃO adicione manualmente** - o Railway cria automaticamente!

### 4. Gerar SECRET_KEY
Se precisar gerar uma nova SECRET_KEY, execute localmente:

```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

Ou use um gerador online: https://djecrety.ir/

### 5. Forçar Rebuild
Após adicionar as variáveis:
1. Vá para **Deployments**
2. Clique no último deployment
3. Clique em **Redeploy**

Ou faça um novo commit e push para GitHub.

## Verificar se as Variáveis Estão Corretas

No painel do Railway, vá para **Logs** e procure por:
- ✅ "Listening on TCP address 0.0.0.0:PORT" - Backend rodando
- ❌ "ModuleNotFoundError" - Problema com dependências
- ❌ "OperationalError" - Problema com banco de dados

## Troubleshooting

### Erro: "ModuleNotFoundError: No module named 'pkg_resources'"
**Solução**: 
1. Verifique se `setuptools` está em `requirements.txt`
2. Faça um novo push para forçar rebuild do Docker
3. Aguarde o rebuild completar

### Erro: "OperationalError: could not connect to server"
**Solução**:
1. Verifique se PostgreSQL foi adicionado ao projeto
2. Verifique se `DATABASE_URL` está nas variáveis de ambiente
3. Aguarde alguns segundos para o banco ficar pronto

### Erro: "CORS error"
**Solução**:
1. Verifique se `CORS_ALLOWED_ORIGINS` está correto
2. Certifique-se de que a URL do frontend está exata (com https://)

## Ambiente de Desenvolvimento vs Produção

### Development (.env local)
```
SECRET_KEY=django-insecure-dev-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
DATABASE_URL=sqlite:///db.sqlite3
```

### Production (Railway)
```
SECRET_KEY=sua-chave-super-segura
DEBUG=False
ALLOWED_HOSTS=seu-dominio.railway.app
DATABASE_URL=postgresql://...  # Automático
```

## Checklist Final

- [ ] `SECRET_KEY` configurada
- [ ] `DEBUG=False`
- [ ] `ALLOWED_HOSTS` com seu domínio
- [ ] PostgreSQL adicionado (DATABASE_URL automático)
- [ ] Credenciais do Mercado Pago
- [ ] URLs de webhook e frontend corretas
- [ ] CORS_ALLOWED_ORIGINS configurado
- [ ] Rebuild do Docker completado
- [ ] Logs mostram "Listening on TCP address"
