# Deployment no Vercel

## Pré-requisitos

1. Conta no Vercel (https://vercel.com)
2. Projeto conectado ao GitHub
3. Backend rodando no Railway (ou outro servidor)

## Passos para Deploy

### 1. Conectar Repositório ao Vercel

1. Acesse https://vercel.com/new
2. Selecione "Import Git Repository"
3. Conecte seu repositório GitHub
4. Selecione o projeto `Bot_IqOption`

### 2. Configurar Build Settings

Na página de configuração do projeto:

- **Framework Preset**: Vite
- **Build Command**: `npm run build:prod`
- **Output Directory**: `dist`
- **Install Command**: `npm install`

### 3. Configurar Variáveis de Ambiente

No painel do Vercel, vá para **Settings > Environment Variables** e adicione:

```
VITE_API_BASE_URL=https://seu-backend-url.railway.app/api
VITE_WS_BASE_URL=wss://seu-backend-url.railway.app
```

**Nota**: Se o backend está no Railway, use:
```
VITE_API_BASE_URL=https://bot-iqoption-backend.railway.app/api
VITE_WS_BASE_URL=wss://bot-iqoption-backend.railway.app
```

### 4. Deploy

O Vercel fará deploy automaticamente quando você fazer push para a branch principal (main/master).

Ou clique em "Deploy" no painel do Vercel.

## Configuração de Domínio Customizado

1. No painel do Vercel, vá para **Settings > Domains**
2. Adicione seu domínio customizado
3. Configure os registros DNS conforme instruído

## Variáveis de Ambiente por Ambiente

### Development (`.env.development`)
```
VITE_API_BASE_URL=http://127.0.0.1:8000/api
VITE_WS_BASE_URL=ws://127.0.0.1:8000
```

### Production (`.env.production`)
```
VITE_API_BASE_URL=https://seu-backend-url.railway.app/api
VITE_WS_BASE_URL=wss://seu-backend-url.railway.app
```

## Monitoramento

- **Logs de Build**: Acesse o painel do Vercel > Deployments
- **Logs de Runtime**: Acesse o painel do Vercel > Logs
- **Analytics**: Acesse o painel do Vercel > Analytics

## Troubleshooting

### Erro: "Cannot find module"

**Solução**: Execute `npm install` localmente e verifique se todas as dependências estão no `package.json`

### Erro: "API requests failing"

**Solução**: Verifique se as variáveis `VITE_API_BASE_URL` e `VITE_WS_BASE_URL` estão corretas no painel do Vercel

### Erro: "CORS error"

**Solução**: Verifique se o backend tem CORS configurado corretamente para o domínio do Vercel

### Erro: "WebSocket connection failed"

**Solução**: Certifique-se de que:
1. O backend suporta WebSocket (Daphne/Channels)
2. A URL do WebSocket está correta (wss:// para HTTPS)
3. O firewall não está bloqueando WebSocket

## Rollback

1. Acesse o painel do Vercel > Deployments
2. Clique no deployment anterior
3. Clique em "Promote to Production"

## Mais Informações

- Documentação Vercel: https://vercel.com/docs
- Vite Documentation: https://vitejs.dev
- React Router: https://reactrouter.com

## Checklist de Deploy

- [ ] Variáveis de ambiente configuradas no Vercel
- [ ] Backend rodando e acessível
- [ ] CORS configurado no backend
- [ ] WebSocket configurado no backend
- [ ] Domínio customizado (opcional)
- [ ] SSL/TLS ativado (automático no Vercel)
- [ ] Monitoramento configurado
