# Deploy — Vercel + Render + Neon

Três serviços, porque nenhum deles faz bem o trabalho dos outros:

| Peça | Onde | Por quê |
|---|---|---|
| Painel (Next.js) | **Vercel** | É o caso de uso dela; deploy a cada push. |
| API (FastAPI) | **Render** | Roda o Dockerfile que já existe, sem limite de tempo por requisição. |
| Banco (Postgres) | **Neon** | Postgres gerenciado, com plano gratuito que não expira. |

> **Por que a API não vai para a Vercel.** As funções de Python dela são
> serverless: têm teto de tempo por requisição e não guardam conexão. A leitura
> do print chama a IA de visão e pode levar 30s, com até 3 tentativas; e o
> `alembic upgrade head` precisa de um processo que sobe uma vez, não de uma
> função que nasce e morre por chamada.

---

## 1. Banco na Neon

1. <https://neon.tech> → **New Project**, região mais perto do Render
   (Oregon/us-west se você escolher `oregon` no `render.yaml`).
2. Copie a **connection string** que ela mostra. Vai ser parecida com:

   ```
   postgresql://usuario:senha@ep-algo-123.us-west-2.aws.neon.tech/neondb?sslmode=require
   ```

3. Guarde. Ela é o `DATABASE_URL` do passo seguinte.

> **Não precisa trocar o `postgresql://` por `postgresql+psycopg://`.** O
> backend normaliza o prefixo sozinho — é o erro de deploy mais fácil de
> cometer, então ele foi resolvido no código (`app/config.py`).

> **O `?sslmode=require` é obrigatório** e já vem na string da Neon. Não tire.

---

## 2. API no Render

O repositório traz um [`render.yaml`](./render.yaml) pronto.

1. <https://render.com> → **New** → **Blueprint** → aponte para o repositório.
2. Ele lê o `render.yaml` e pede as variáveis que não estão no git:

   | Variável | O que pôr |
   |---|---|
   | `DATABASE_URL` | a string da Neon, inteira |
   | `CORS_ORIGINS` | o domínio do painel na Vercel (você ainda não tem — ponha `https://localhost` e corrija no passo 4) |
   | `SUPERUSER_USERNAME` | o seu usuário de administrador |
   | `SUPERUSER_PASSWORD` | a senha dele, com 8+ caracteres |
   | `VISION_API_KEY` | a chave do Gemini ([AI Studio](https://aistudio.google.com/apikey)) |

3. Deploy. No primeiro start ele roda as migrations e cria a sua conta de
   administrador.
4. Confira: `https://bet-board-api.onrender.com/health` deve responder
   `{"status":"ok", ..., "database":"up"}`.

> **O plano gratuito hiberna** depois de ~15 minutos sem tráfego. A primeira
> requisição depois disso leva uns 30–50s para acordar o serviço. Para um amigo
> testar, tudo bem; para cliente pagante, o plano pago resolve.

### Depois do primeiro deploy

Apague `SUPERUSER_PASSWORD` das variáveis do Render. Ela já cumpriu o papel —
a conta existe, e o bootstrap **não** troca a senha de quem já existe. Deixá-la
lá só mantém uma senha em texto no painel do host.

---

## 3. Painel na Vercel

1. <https://vercel.com> → **Add New** → **Project** → importe o repositório.
2. **Root Directory: `frontend`.** É o passo que mais gente esquece — sem isso
   a Vercel tenta buildar a raiz do monorepo e não acha o `package.json` do
   Next.
3. Framework: Next.js (ela detecta sozinha).
4. Variáveis de ambiente:

   | Variável | Valor |
   |---|---|
   | `NEXT_PUBLIC_API_BASE_URL` | `https://bet-board-api.onrender.com` |
   | `API_BASE_URL_INTERNAL` | `https://bet-board-api.onrender.com` |

   As duas apontam para o mesmo lugar aqui. Elas existem separadas porque no
   Docker local o navegador fala com `localhost:8000` e o servidor do Next fala
   com `backend:8000`, dentro da rede do Compose.

   > `NEXT_PUBLIC_API_BASE_URL` é embutida **no build**. Mudar depois exige um
   > novo deploy, não só um restart.

5. Deploy. Anote o domínio (`https://algo.vercel.app`).

---

## 4. Fechar o CORS

Volte ao Render e corrija `CORS_ORIGINS` para o domínio real da Vercel:

```
https://bet-board.vercel.app
```

Aceita mais de um, separados por vírgula:

```
https://bet-board.vercel.app,https://painel.seudominio.com
```

Salve — o Render reinicia sozinho.

> **Deploys de preview da Vercel não vão funcionar** com essa configuração:
> cada branch ganha um domínio diferente, e nenhum está na lista. Para testar
> uma branch, ou você adiciona aquele domínio ao `CORS_ORIGINS`, ou testa em
> produção mesmo. Liberar `*` não é opção: o painel manda o token no header.

---

## 5. Conferir

```bash
API=https://bet-board-api.onrender.com

# a API está de pé e enxerga o banco?
curl -s $API/health

# o login funciona? (usuário e senha do SUPERUSER_*)
curl -s -X POST $API/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"SEU_USUARIO","password":"SUA_SENHA"}'
```

No painel: abra o domínio da Vercel, entre, e confirme que **Administração**
aparece na lateral. É por ali que você cria a conta do seu amigo.

---

## Criando a conta do seu amigo

Pelo painel, em **Administração**:

1. Usuário, nome e a primeira banca dele.
2. A senha já vem gerada — copie antes de sair da tela, ela não aparece de novo.
3. Entregue usuário e senha.

Ele entra, vai em **Configurações** da banca, conecta o Telegram dele pelo
assistente e liga a página pública quando quiser.

---

## Variáveis, resumidas

**Render (API)**

```
DATABASE_URL=postgresql://…neon.tech/neondb?sslmode=require
CORS_ORIGINS=https://bet-board.vercel.app
AUTH_SECRET_KEY=<gerada pelo Render>
AUTH_TOKEN_TTL_MINUTES=720
SUPERUSER_USERNAME=lucas          # apague a senha depois do 1º deploy
SUPERUSER_PASSWORD=…
VISION_PROVIDER=gemini
VISION_API_KEY=…
VISION_MODEL=models/gemini-3.5-flash-lite
ENVIRONMENT=prod
```

**Vercel (painel)**

```
NEXT_PUBLIC_API_BASE_URL=https://bet-board-api.onrender.com
API_BASE_URL_INTERNAL=https://bet-board-api.onrender.com
```

**Não vão para lugar nenhum:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` e
`WHATSAPP_WEBHOOK_URL`. Cada cliente configura o canal dele pelo painel, e o
valor fica no banco, por banca.

---

## Quando algo não sobe

| Sintoma | Causa quase sempre |
|---|---|
| `/health` diz `database: "down"` | `DATABASE_URL` errada, ou faltou `?sslmode=require` |
| Painel diz "Não foi possível alcançar o backend" | `NEXT_PUBLIC_API_BASE_URL` errada — e lembre que ela é embutida no build |
| Login falha com erro de CORS no console | `CORS_ORIGINS` não tem o domínio exato da Vercel (com `https://`, sem barra no fim) |
| Primeira requisição do dia demora 40s | O plano gratuito do Render hibernou. É isso mesmo. |
| `/admin` responde "página não encontrada" | A conta não é administradora. Confira `SUPERUSER_USERNAME` nos logs do primeiro deploy. |
| Deploy sobe mas as tabelas não existem | O `start.sh` não rodou — confira se o `CMD` do Dockerfile foi sobrescrito no painel do Render. |
