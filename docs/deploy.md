# Deploy no Render

O `render.yaml` na raiz cria três recursos: a API (`fila-zero-api`, imagem Docker), o front (`fila-zero-web`, site estático) e o banco (`fila-zero-db`, PostgreSQL). Depois de configurado, cada push na `main` que passar nos testes do GitHub Actions dispara o deploy da API.

## 1. Criar os serviços (uma vez)

1. Entre em [dashboard.render.com](https://dashboard.render.com) com a conta do GitHub.
2. **New → Blueprint** e escolha o repositório `fila-zero-ubs`. Como ele é privado, o Render pede acesso a ele no GitHub: libere só esse repositório.
3. O Render lê o `render.yaml` e pede três valores:

| Variável | Serviço | O que colocar |
| --- | --- | --- |
| `SEED_SENHA` | API | Senha dos usuários de demonstração (`cidadao@filazero.dev` e `gestora@filazero.dev`). Use uma senha nova, não a `filazero-demo` do ambiente local |
| `CORS_ORIGENS` | API | Endereço do front, por exemplo `https://fila-zero-web.onrender.com` |
| `VITE_API_URL` | Front | Endereço da API, por exemplo `https://fila-zero-api.onrender.com` |

Os endereços só aparecem depois da criação. Se o nome sugerido estiver ocupado, o Render acrescenta um sufixo: confira os endereços reais, corrija as duas variáveis em **Environment** e faça um novo deploy dos dois serviços.

`JWT_SECRET` e `PSEUDONIMO_SAL` são gerados pelo Render e ficam só lá.

4. **Apply**. Ao terminar, `https://<sua-api>.onrender.com/health` deve responder `{"status": "ok", ...}`.

## 2. Ligar o deploy automático

1. No Render, abra `fila-zero-api` → **Settings** → **Deploy Hook** e copie a URL.
2. No GitHub, abra o repositório → **Settings → Secrets and variables → Actions → New repository secret**.
3. Nome `RENDER_DEPLOY_HOOK_URL`, valor a URL copiada.

A partir daí, o job `deploy` do CI chama essa URL depois de `qualidade` e `build` passarem. O front tem deploy automático próprio no Render a cada push na `main`.

## O que muda em relação ao ambiente local

- **Sem broker MQTT:** o cartão "Sala de espera agora" mostra "sem sensor". A gestora pode enviar leituras por `POST /sala`, ou um broker público pode ser configurado em `MQTT_HOST`.
- **Sem dashboard Streamlit:** ele lê o data lake local e não está no blueprint. Para a demonstração, use `docker compose up`.
- **Plano gratuito:** a API dorme depois de um período sem acesso, e a primeira requisição depois disso leva perto de um minuto. O banco gratuito tem prazo de validade; confira os limites atuais na [página de preços do Render](https://render.com/pricing).
- **Triagem com LLM:** só liga se você adicionar `ANTHROPIC_API_KEY` em **Environment** da API. Sem ela, vale a triagem por regras.
