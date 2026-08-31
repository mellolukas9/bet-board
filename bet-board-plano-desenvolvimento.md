# Bet Board — Plano de Desenvolvimento

Documento-guia para construir o projeto com **Claude Code**, do zero à entrega final.
Cada fase tem passos sequenciados e um critério de "pronto". Execute uma fase por vez.

> **Como usar com Claude Code:** aponte o Claude Code para este arquivo como contexto do projeto. Peça para executar um passo por vez ("faça o Passo 1.2"), revise o resultado, rode os testes, e só então avance. Não peça a fase inteira de uma vez — o ganho de qualidade vem de iterar em blocos pequenos e testáveis.

---

## Objetivo

Ferramenta de **administração de grupos de tips esportivas** para o dono do grupo (não o apostador final). Automatiza o ciclo: leitura da tip em print → mensagem padronizada → validação de resultado (RED/GREEN) → gestão de assinantes → consolidação de resultados.

**Público-alvo:** tipster / administrador do grupo (B2B2C).

---

## Arquitetura: backend + frontend

O projeto é um **monorepo** com dois lados bem separados, que se comunicam por API REST:

- **`backend/`** — API FastAPI (Python): pipeline de leitura das tips, validação, mensageria, regras de negócio, banco. É o cérebro; funciona sozinho mesmo sem frontend (as mensagens saem pro Telegram/WhatsApp).
- **`frontend/`** — Painel do admin (Next.js/React): onde o dono do grupo revisa tips, trata casos de falha de leitura, gere assinantes/pagamentos e vê os resultados consolidados. Consome a API do backend.

O frontend **cresce fase a fase** junto com o backend, não fica todo pro final.

---

## Princípios do projeto

- **Entregar em fases.** A Fase 1 (MVP) precisa funcionar ponta a ponta antes de qualquer outra coisa.
- **Backend independente do frontend.** A API deve funcionar sozinha; o frontend é uma camada de operação por cima.
- **Modelo de dados desenhado desde já para as fases futuras** — evita migração dolorosa depois.
- **Integrações abstraídas atrás de interfaces** (visão, mensageria, validação) — trocar de provedor não deve quebrar o resto.
- **Tudo testável.** Cada serviço tem teste; o pipeline tem um teste de ponta a ponta com prints reais.
- **Configuração via variáveis de ambiente**, nunca hardcoded. Segredos no `.env` (fora do git).

---

## Stack

**Backend**
- Python 3.12 + **FastAPI**
- Contas no banco; sessão em JWT (PyJWT) e senha em PBKDF2 (`hashlib`)
- **PostgreSQL** + SQLAlchemy 2.x + Alembic (migrations)
- Pydantic v2 (validação)
- IA de visão (Claude / GPT-4o / Gemini) via HTTP — abstraída atrás de interface
- Mensageria: Telegram Bot API (começo) + WhatsApp via n8n/Evolution
- pytest (testes)

**Frontend**
- **Next.js (App Router) + React + TypeScript**
- Tailwind CSS (estilização)
- Cliente HTTP consumindo a API do backend (`lib/api`)
- Login por conta; `proxy.ts` (o antigo `middleware.ts`) barra quem não entrou
- Página pública renderizada no servidor (é um link compartilhado)

**Infra**
- Docker Compose orquestrando Postgres + backend + frontend
- Gerência de dependências: uv ou Poetry (backend), npm/pnpm (frontend)

---

## Estrutura de pastas (alvo)

```
bet-board/
├── backend/
│   ├── app/
│   │   ├── main.py               # entrypoint FastAPI
│   │   ├── config.py             # settings via env (Pydantic Settings)
│   │   ├── api/routes/           # rotas
│   │   ├── schemas/              # Pydantic (entrada/saída)
│   │   ├── models/               # SQLAlchemy (tabelas)
│   │   ├── services/
│   │   │   ├── vision/           # extração da tip a partir do print
│   │   │   ├── messaging/        # telegram, whatsapp
│   │   │   └── validation/       # RED/GREEN (Fase 2)
│   │   ├── db/                   # session, base, init
│   │   └── core/                 # utils, logging, auth
│   ├── tests/
│   │   └── fixtures/prints/      # prints reais de tips p/ teste
│   ├── alembic/                  # migrations
│   ├── Dockerfile
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── app/                  # páginas (App Router)
│   │   ├── components/           # componentes de UI
│   │   ├── lib/                  # cliente da API, helpers
│   │   └── types/                # tipos TypeScript (espelham os schemas)
│   ├── Dockerfile
│   └── package.json
│
├── docker-compose.yml            # postgres + backend + frontend
├── .env.example
└── README.md
```

---

## Modelo de dados

Desenhado na Fase 1 já contemplando as fases 2–3.

**`user`** (multi-cliente, 31/08)
- `id` (PK), `username` (único), `password_hash` (PBKDF2), `name`, `is_active`,
  `last_login_at`, `created_at`

**`bankroll`** (multi-cliente, 31/08)
- `id` (PK), `user_id` (FK)
- `name`, `slug` (único — é a URL pública `/b/<slug>`), `description`
- `is_public` — a página pública só abre com isto ligado; nasce desligado
- `telegram_bot_token`, `telegram_chat_id`, `whatsapp_webhook_url` — os canais
  saíram do `.env` e passaram a ser por banca

**`tip`**
- `id` (PK)
- `bankroll_id` (FK) — de quem é a tip e em qual canal ela sai
- `source` — casa de aposta / origem
- `event` — evento/partida
- `market` — mercado apostado
- `odd` — cotação (decimal)
- `stake` — valor apostado
- `stake_units` — stake em unidades (**decidido: o grupo trabalha em unidades**)
- `currency` — moeda (default BRL)
- `raw_image_ref` — referência do print original
- `status` — enum: `pending` | `green` | `red` | `void`
- `extracted_at` — quando a IA leu
- `resolved_at` — quando o resultado foi definido (Fase 2)
- `result_raw` — payload bruto da fonte de resultado (Fase 2)
- `created_at`

**`message_log`**
- `id` (PK), `tip_id` (FK), `channel` (`telegram`|`whatsapp`), `sent_at`, `status`

> **Decisão de 31/08 — multi-cliente.** O sistema deixou de atender um tipster
> por deploy. A hierarquia é `user` → `bankroll` → `tip`, e a **banca** é a
> unidade que importa: ela tem o canal, as tips e a página pública. Um tipster
> pode ter VIP e Free com canais diferentes.
>
> - **Não há cadastro aberto**: as contas nascem por
>   `python -m app.cli create-user`. Abrir depois não muda o modelo.
> - **`/b/<slug>` é público e mostra tudo em unidades** — nunca em reais, para
>   não expor o tamanho da banca de quem publica.
> - **O cliente configura o próprio Telegram** pelo painel, com um assistente
>   que diagnostica o que falta (`getMe`/`getChat`/`getChatMember`) em vez de
>   deixar o erro aparecer no primeiro envio.

**`subscriber`** (Fase 3)
- `id`, `name`, `contact`, `plan`, `status`, `subscription_start`, `subscription_end`

**`payment`** (Fase 3)
- `id`, `subscriber_id` (FK), `amount`, `method`, `period`, `paid_at`

---

## Fase 0 — Setup (fundação)

**Backend**
- [x] Inicializar `backend/` com `pyproject.toml` (venv + pip; `uv`/Poetry não estavam instalados)
- [x] Criar estrutura de pastas do backend
- [x] Configurar `config.py` com Pydantic Settings lendo do `.env`
- [x] Subir FastAPI mínimo com rota `GET /health`
- [x] Configurar SQLAlchemy (base, session) e Alembic
- [x] Configurar pytest e escrever teste do `/health`
- [x] Configurar logging estruturado em `core/`

**Frontend**
- [x] Inicializar `frontend/` com Next.js (App Router) + TypeScript + Tailwind
- [x] Criar `lib/api` (cliente HTTP apontando pro backend)
- [x] Página inicial mínima que consome `GET /health` e mostra "backend online"

**Infra**
- [x] `.env.example` (chaves de API, URL do banco, tokens — sem valores reais)
- [x] `docker-compose.yml` com Postgres + backend + frontend

**Pronto quando:** `docker compose up` sobe os três serviços, `GET /health` responde 200, a home do frontend mostra o backend online, e `pytest` passa.

> **✅ Concluída.** Os três serviços sobem, `/health` responde `{"status":"ok","database":"up"}`,
> a home renderiza "Backend online / Banco: conectado" e `pytest` passa (3 testes).
> Decisões tomadas no caminho:
> - **Postgres exposto na porta 5433** do host (a 5432 estava ocupada por outro projeto).
>   Dentro do Compose os serviços seguem usando `db:5432`.
> - **Duas URLs de API no frontend:** `NEXT_PUBLIC_API_BASE_URL` (navegador) e
>   `API_BASE_URL_INTERNAL` (servidor Next → `http://backend:8000` no Compose).
> - `/health` reporta o estado do banco **separado** do status da API, para distinguir
>   "backend fora" de "banco fora".

---

## Fase 1 — MVP: OCR + Mensagem Padronizada

O coração do produto. Leitura do print → tip estruturada → mensagem padronizada → envio. Frontend entra como painel de revisão.

### Backend

**1.1 Modelo e schema da Tip**
- [x] Model SQLAlchemy `tip` + `message_log` conforme o modelo de dados
- [x] Migration Alembic dessas tabelas (testada nos dois sentidos)
- [x] Schemas Pydantic: `TipExtracted` (saída da IA) e `TipRead`

> Extensões ao modelo de dados original, para sustentar a fila de revisão manual
> exigida no passo 1.7: os campos da tip são **nullable** (um print ilegível vira
> tip mesmo assim) e há `needs_review` + `extraction_error`.

**1.2 Serviço de visão (extração da tip)**
- [x] Interface `VisionExtractor` (`extract(image, media_type) -> TipExtracted`)
- [x] Provedor concreto — SDK oficial da Anthropic com **structured outputs**
      (resposta já validada no schema; mais confiável que parsear JSON solto)
- [x] Prompt estruturado retornando **JSON fixo**: `source, event, market, odd, stake, currency`
- [x] Tratar falhas: print ilegível / campo faltando → marca para revisão manual, não quebra o fluxo
- [ ] Coletar 15–20 prints reais em `tests/fixtures/prints/` — **depende do Lucas**
- [x] Teste medindo taxa de acerto nos fixtures (`pytest -m vision`), pronto para receber os prints
- [x] CLI para testar prints avulsos: `python -m app.cli extract print.png`

**1.3 Formatação da mensagem padrão**
- [x] Template único (ex: `🎯 Tip | Casa: {source} | {event} | {market} @ {odd} | R$ {stake} | Status: {status}`)
- [x] `format_tip_message(tip) -> str` + teste

> Campo que a IA não achou é **omitido** da mensagem, em vez de sair como
> "None" no grupo. Formatação no padrão brasileiro (`1.234,50`, odd com vírgula).

**1.4 Mensageria — Telegram**
- [x] Interface `MessageSender`
- [x] `TelegramSender` (Bot API) enviando para o canal de destino
- [x] Registrar envio em `message_log` + teste
- [ ] Envio real — **depende de `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`**

> `dispatch_tip_message()` manda por todos os canais e grava uma linha em
> `message_log` por canal: falha de um não impede os outros. Não faz commit —
> a transação é de quem chama (a 1.5).
> Canal sem credencial é omitido pelo factory, não quebra o pipeline.

**1.5 Entrada e orquestração**
- [x] `POST /tips` recebe imagem → `VisionExtractor` → persiste `tip` (`pending`)
- [x] `POST /tips/{id}/publish` formata → `TelegramSender` → `message_log`
- [x] `GET /tips` lista tips (filtros `status` e `needs_review`)
- [x] `PATCH /tips/{id}` para corrigir manualmente uma tip mal lida
- [x] Teste de ponta a ponta (`backend/tests/test_tips_api.py`)

> Envio e persistência viraram **duas rotas**, não uma. O stake sai em unidades
> ("2u") e quem informa as unidades é o admin no `PATCH` — o print da casa só
> mostra reais. Então a tip nasce em revisão e só depois é publicável.

**1.6 WhatsApp (via n8n / Evolution)**
- [ ] `WhatsAppSender` disparando webhook para o n8n
- [ ] Permitir envio nos dois canais em paralelo + teste

### Frontend

**1.7 Painel de tips**
- [x] Login por conta (`POST /auth/login`), com contas no banco
- [x] Tela de listagem de tips (consome `GET /tips`), com status visível
- [x] **Fila de revisão manual:** tips que falharam na leitura, com formulário para corrigir/completar (usa `PATCH /tips/{id}`)
- [x] Feedback visual de envio (enviada / falha) por canal
- [x] **Marcação manual de green/red/void** pelo admin (`POST /tips/{id}/result`)
- [x] Banca consolidada: curva de evolução + cartões (`GET /bankrolls/{id}/stats`)
- [x] **Multi-cliente:** `user` + `bankroll`, tips por banca, isolamento entre contas
- [x] **Página pública** por banca (`/b/<slug>`), em unidades
- [x] **Configuração do Telegram pelo cliente**, com detecção de canal e diagnóstico

> **Decisão de 31/08: nada de API esportiva neste momento.** O resultado quem
> informa é o admin, na própria lista da banca. Isso puxou para a Fase 1 duas
> coisas que o plano original tinha na 2 e na 4 — a marcação de resultado e o
> consolidado — porque sem elas o painel não fecha o ciclo da tip. O que a
> Fase 2 ainda precisa entregar é a **automação** disso, e o `result_raw` já
> guarda `source: "manual"` para as duas origens conviverem.

**Pronto quando:** mandar um print resulta, ponta a ponta, em (a) tip estruturada no banco, (b) mensagem padronizada no Telegram e WhatsApp, (c) registro em `message_log`; e o admin consegue **ver as tips e corrigir as mal lidas pelo painel**. Rodar em paralelo real por alguns dias, comparando com o trabalho manual.

---

## Fase 2 — Validação automática RED/GREEN

### Backend
- [ ] Escolher API esportiva (ex: API-Football, TheOddsAPI) — **validar cobertura dos seus mercados antes de codar**
- [ ] Interface `ResultValidator` (`validate(tip) -> status`)
- [ ] Validador via API esportiva + **fallback com IA** para mercados sem cobertura
- [ ] Rotina que pega tips `pending` e resolve após o evento (atualiza `status`, `resolved_at`, `result_raw`)
- [ ] Notificar resultado (GREEN/RED) no canal via mensageria existente
- [ ] Amostragem de validação humana para medir confiabilidade + testes

### Frontend
- [x] Coluna/badge de resultado (GREEN/RED/void) na listagem de tips — **feito na 1.7**
- [x] Ação manual de "forçar resultado" — **feito na 1.7**, e hoje é o único caminho

**Pronto quando:** tips pendentes são resolvidas automaticamente com confiabilidade medida e aceitável, notificadas no canal, e visíveis no painel.

---

## Fase 3 — Administração de pagamento de usuários

### Backend
- [ ] Models `subscriber` e `payment` + migrations
- [ ] CRUD de assinantes
- [ ] Integração com gateway (Mercado Pago / Asaas / Stripe) para assinatura recorrente
- [ ] Webhook de confirmação de pagamento → atualiza status/vigência do assinante
- [ ] Testes

### Frontend
- [ ] Tela de gestão de assinantes (lista, status ativo/inativo, vigência)
- [ ] Tela de pagamentos (histórico, situação por assinante)

> A base de multi-cliente da 1.7 já entregou metade da fundação desta fase:
> `user` existe, as contas são isoladas e cada banca tem os seus dados. O que
> falta é o **assinante do grupo** (que não tem login) e o pagamento.

**Pronto quando:** um assinante paga, o sistema registra e controla a vigência, e o admin gere tudo pelo painel.

---

## Fase 4 — Dashboard de consolidação de resultados

### Backend
- [ ] Endpoints de agregação: taxa de acerto (GREEN%), lucro/prejuízo, histórico por período
- [ ] Testes dos cálculos de agregação

### Frontend
- [x] Dashboard com os indicadores consolidados (GREEN%, P/L, evolução no tempo) — **antecipado na 1.7**
- [x] Filtros por período (Tudo / 30 dias / 7 dias / Hoje)
- [ ] Visão pública de prova de performance (hoje o painel exige login)

**Pronto quando:** o admin vê resultados consolidados e confiáveis num painel completo.

---

## Riscos e considerações

- **Confiabilidade da fonte de dados (maior risco técnico):** a validação RED/GREEN depende de API esportiva confiável. Cobre bem futebol/esportes tradicionais; mercados exóticos podem exigir IA + validação humana por amostragem. É a peça que sustenta a credibilidade — teste cedo.
- **Mensageria:** WhatsApp via API não oficial é mais barato mas tem risco de bloqueio. Telegram é o começo mais seguro.
- **Regulação:** o setor de apostas é regulamentado no Brasil desde 2025, com regras de publicidade e advertências obrigatórias. Irrelevante para MVP/portfólio, mas essencial antes de comercializar.

---

## Comandos úteis (preencher no setup)

```bash
# subir tudo (postgres + backend + frontend)
docker compose up -d

# backend — migrations
cd backend && alembic upgrade head
alembic revision --autogenerate -m "descrição"

# backend — testes e API local
pytest
uvicorn app.main:app --reload

# frontend — dev local
cd frontend && npm run dev
```

---

## Nomenclatura

"Bet Board" é o nome de trabalho/repositório. Já existe um app *BetBoard* nas stores — se o projeto virar produto comercial, considerar um nome livre como **TipBoard** (que descreve melhor: é sobre gerir *tips*).
