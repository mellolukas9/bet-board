# Próximos passos — retomar depois de 31/08/2026

Documento de retomada. Sessão anterior: 31/08/2026 (três entregas no mesmo dia).
O plano completo continua em [`bet-board-plano-desenvolvimento.md`](./bet-board-plano-desenvolvimento.md).
Para publicar, ver [`DEPLOY.md`](./DEPLOY.md).

---

## ⚠️ O deploy está preparado, não feito

Você pediu para **não commitar ainda**, e a Vercel faz deploy a partir do
GitHub. Então o que existe é tudo o que dá para fazer sem git:

- [`render.yaml`](./render.yaml) — blueprint do backend, pronto para importar
- [`backend/start.sh`](./backend/start.sh) — migra o banco e sobe na `$PORT`
- [`DEPLOY.md`](./DEPLOY.md) — passo a passo de Vercel + Render + Neon
- duas armadilhas de deploy resolvidas no código: a URL da Neon vem como
  `postgresql://` (o backend troca o driver sozinho) e o `CORS_ORIGINS` aceita
  lista por vírgula, não só JSON

**O que falta, e só você pode fazer:** commitar o código e dar push. Hoje o
repositório `mellolukas9/bet-board` tem **só o README** versionado — todo o
resto está fora do git. Quando quiser, eu faço os commits.

---

## Onde paramos

**O sistema virou multi-cliente.** Deixou de atender um tipster por deploy: cada
cliente tem conta, bancas, canal do Telegram próprio e uma página pública de
resultados. O painel (1.7) está inteiro.

| Passo | Estado |
|---|---|
| 1.1 Models + migrations | ✅ |
| 1.2 Serviço de visão (**Gemini**) + CLI | ✅ código |
| 1.2 Prints reais nos fixtures | ⬜ **depende de você** |
| 1.3 Formatação da mensagem padrão (em unidades) | ✅ |
| 1.4 Telegram + `message_log` | ✅ |
| 1.4 Envio real | 🟢 **destravado** (ver abaixo) |
| 1.5 Rotas de tip | ✅ |
| 1.6 WhatsApp via n8n | ⬜ |
| 1.7 Painel: login, banca, resultado manual, revisão | ✅ |
| 1.7+ Multi-cliente, página pública, config do Telegram | ✅ |
| 1.7+ Painel de administração (`/admin`) | ✅ |
| Deploy Vercel + Render + Neon | 🟡 **preparado; falta o git** |

Verificado nesta sessão: **241 testes passando**, `ruff check` limpo,
`tsc --noEmit` e `eslint` limpos, `next build` passando, migration aplicada no
**Postgres de verdade** sem perder dado, e o painel rodado no navegador de ponta
a ponta.

---

## 🟢 O envio para o Telegram está destravado

O que travava desde 27/08 era permissão no canal. **Não trava mais.** O botão
*Testar conexão* (Configurações → Telegram) perguntou ao Telegram e respondeu:

> Tudo certo. O bot `@betboard_tips_bot` pode publicar em **Bet Board Tips**.

Ou seja: o bot já é administrador com "Publicar mensagens". O teste de ponta a
ponta que faltava é subir um print na aba **Tips**, informar as unidades e
clicar em **Publicar** — a mensagem deve sair no canal.

---

## O que mudou na terceira entrega

### Painel de administração (`/admin`)

Separado do painel do tipster, porque o assunto é outro: lá você opera uma
banca, aqui você administra quem tem conta. Criar conta (com a primeira banca e
uma senha gerada), desativar, reativar, trocar senha, promover e apagar.

O papel é o `is_superuser` na tabela `user`. A migration `d5b2c8e1a730`
**promoveu a conta que já existia** — numa instalação de um cliente só ela era
as duas coisas, e tirar o acesso de quem já usava seria uma regressão.

Duas travas: você não desativa, rebaixa nem apaga a própria conta (o clique
trancaria você para fora, e só o banco resolveria); e apagar conta com banca é
recusado — desativar tira o acesso sem perder o histórico.

### O endereço público agora segue o nome

Era editável à parte, o que deixava `/b/vip-pecanha` numa banca chamada "Free".
Agora o `slug` é derivado do nome no backend, o campo na tela é somente-leitura,
e enquanto você digita o nome a prévia mostra o link que vai valer — em âmbar
quando o link atual vai parar de funcionar.

A API não aceita mais `slug` no corpo: a regra mora num lugar só.

### O interruptor da página pública

Estava quebrado quando ligado: a bolinha era empurrada com `translate-x` dentro
de um flex sem largura fixa, e o botão crescia junto — apareciam duas bolas.
Agora a pista tem largura fixa e a bolinha é posicionada dentro dela.

### A página pública ficou maior

Mais largura (`max-w-6xl`), gráfico de 320–384px de altura, cartões e linhas com
texto maior. O gráfico virou um componente com altura configurável, então o
painel interno continua compacto.

---

## O que mudou na segunda entrega

### 1. `user` → `bankroll` → `tip`

```
user (o tipster)
 └── bankroll "Vip Peçanha"     /b/vip-pecanha
     ├── token do bot + canal do Telegram
     └── tips
 └── bankroll "Free"            /b/free-pecanha
     ├── outro canal
     └── tips
```

A **banca** é a unidade que importa: tem o canal, as tips e a URL pública. Um
tipster pode ter VIP e Free sem misturar resultado nenhum.

Isolamento: banca (ou tip) de outra conta responde **404**, nunca 403 — um 403
já confirmaria que ela existe. Tem teste para cada rota.

### 2. Contas, criadas por você

Não há cadastro aberto. A conta de um cliente nasce assim:

```bash
docker compose exec backend python -m app.cli create-user \
    --username pecanha --name "Peçanha" --bankroll "Vip Peçanha"
```

Ele pergunta a senha (sem ecoar) e imprime o endereço público da banca. Também
há `list-users` e `set-password --username X`.

Rodando fora do Docker, o prefixo é `cd backend && .venv/Scripts/python -m app.cli`.

### 3. Página pública — `/b/<slug>`

O link que o cliente manda para os assinantes. Gráfico, cartões e a lista de
apostas, **tudo em unidades**.

O que **não** sai por ali: valor em reais, print original, erro de leitura, log
de envio. Os schemas da rota pública (`app/schemas/public.py`) são outros, não um
recorte dos internos — então um campo novo em `TipRead` não vaza por descuido.
Há teste que varre o corpo da resposta atrás de `R$` e do nome do arquivo.

A banca **nasce privada**; enquanto não for publicada, `/b/<slug>` responde 404
para todo mundo. Liga e desliga em Configurações.

> A sua banca ficou **pública** em <http://localhost:3000/b/minha-banca> porque
> foi assim que testei a tela. Desligue em Configurações se não quiser.

### 4. O cliente configura o próprio Telegram

Em **Configurações → Telegram**, um assistente de três passos. A ordem não é
decoração: configurar bot de canal falha sempre nos mesmos três lugares.

| Passo | Fecha qual erro |
|---|---|
| 1. Criar o bot no @BotFather e colar o token | `401 Unauthorized` |
| 2. Pôr o bot no canal **como administrador** | `400 chat not found` |
| 3. Escolher o canal (botão **Detectar canais**) | `need administrator rights` |

O passo 3 resolve a parte mais chata: canal privado não mostra o `chat_id` em
lugar nenhum do aplicativo. O botão lista as conversas que o bot já viu — mande
uma mensagem no canal antes — e a pessoa só clica na certa.

**Testar conexão** pergunta ao Telegram (`getMe`, `getChat`, `getChatMember`)
antes de qualquer envio e diz em português o que falta, em vez de deixar o erro
aparecer na hora em que a tip devia sair.

O token do bot **nunca volta inteiro** da API — só uma pista
(`8741270881:…s8j8`), o suficiente para reconhecer qual bot está ali.

### 5. O `.env` encolheu

Saíram dele: `ADMIN_*` (contas agora no banco) e `TELEGRAM_*` /
`WHATSAPP_WEBHOOK_URL` (canais agora por banca). As seis variáveis continuam no
`.env.example` **só** porque a migration `c3a1d5e7f204` as lê uma vez, para
migrar quem vinha da versão de um cliente só.

Foi exatamente o que aconteceu com o seu banco: a migration criou a conta
`admin` com a sua senha, criou a banca "Minha banca" com o seu canal do Telegram
e moveu as 3 tips para ela. Nada se perdeu.

---

## Subir o ambiente

```bash
cd C:\Projects\bet-board
docker compose up -d --build
```

> ⚠️ **Use `--build`.** Sem ele o Compose reaproveita a imagem em cache e ignora
> as mudanças em `backend/app`, `backend/alembic` e no frontend.

> ⚠️ O Postgres do Bet Board está na porta **5433** do host, não 5432 — a 5432
> já é usada pelo `regista-postgres` de outro projeto seu. Não mexa nele.

> ⚠️ Se a porta 3000 estiver ocupada, procure um `next dev` esquecido:
> `netstat -ano | grep :3000` e encerre o PID.

Abra <http://localhost:3000> e entre com `admin` / a senha do `.env`.

---

## ⚠️ Troque a senha de desenvolvimento

Continua valendo: `ADMIN_PASSWORD=betboard` no `.env` virou a senha da conta
`admin` no banco. Troque:

```bash
docker compose exec backend python -m app.cli set-password --username admin
```

Depois disso pode apagar `ADMIN_PASSWORD` do `.env` — ele não é mais lido por
nada (só pela migration, que já rodou).

---

## A API hoje

| Rota | O que faz | Login? |
|---|---|---|
| `GET /health` | estado da API e do banco | público |
| `POST /auth/login` | usuário+senha → token | público |
| `GET /auth/me` | a conta e as bancas dela | sim |
| `GET /public/bankrolls/{slug}` | **a página pública**, em unidades | público |
| `GET/POST /bankrolls` | lista e cria bancas | sim |
| `GET/PATCH/DELETE /bankrolls/{id}` | detalhe, configuração, remoção | sim |
| `POST /bankrolls/{id}/telegram/test` | diagnostica token, canal e permissão | sim |
| `POST /bankrolls/{id}/telegram/detect` | lista os canais que o bot enxerga | sim |
| `GET/POST /bankrolls/{id}/tips` | lista as tips e sobe um print | sim |
| `GET /bankrolls/{id}/stats` | consolidado + série do gráfico | sim |
| `POST /tips/preview` | lê o print e devolve tip + mensagem, **sem gravar** | sim |
| `GET/PATCH/DELETE /tips/{id}` | detalhe, correção, descarte | sim |
| `POST /tips/{id}/result` | **green / red / void / pending** | sim |
| `POST /tips/{id}/publish` | formata, envia no canal **da banca** e loga | sim |
| `GET/POST /admin/users` | lista e cria contas | **administrador** |
| `PATCH/DELETE /admin/users/{id}` | ativa, desativa, promove, troca senha, apaga | **administrador** |

Regras que valem lembrar:

1. **`POST /bankrolls/{id}/tips` nunca perde o print.** Provedor fora do ar ou
   print ilegível viram tip com `extraction_error` e `needs_review`, não 502.
2. **`publish` recusa (409)** quando falta `event`, `market`, `odd` ou
   `stake_units`; quando a tip já foi publicada (`{"force": true}` republica); e
   quando a banca não tem canal configurado.
3. **Canal que falha não derruba a requisição.** A resposta traz
   `channels: {"telegram": "failed"}` e o motivo fica no `message_log`.
4. **`needs_review` é recalculado no `PATCH`.** Para segurar a tip na fila mesmo
   completa, mande `needs_review: true`.
5. **Marcar resultado não exige revisão.** Tip sem unidades pode virar green —
   ela só não soma lucro nenhum (o `/stats` a conta como 0, não como erro).
6. **Apagar banca com tip é recusado (409).** Histórico não some num clique.

---

## Próximos passos, em ordem de valor

1. **Publicar uma tip de ponta a ponta.** O canal está conectado e testado; o
   que falta é subir um print, informar as unidades e clicar em Publicar.
2. **Trocar a senha do `admin`** (ver acima).
3. **1.6 — WhatsApp:** o `WhatsAppSender` já existe e tem teste; falta a caixa
   do webhook em Configurações (hoje o campo existe na API, não na tela) e
   apontar para o n8n.
4. **1.2 — prints reais** em `backend/tests/fixtures/prints/` (meta: 15–20), para
   `pytest -m vision` medir a taxa de acerto.
5. **Fase 3 — assinantes e pagamentos.** Metade da fundação já existe: `user`,
   isolamento por conta, banca com dados próprios. Falta o *assinante do grupo*
   (que não faz login) e o gateway.

### Ideias que ficaram de fora de propósito

- **Papéis dentro da conta do cliente** (dono × operador). Existe um papel só no
  sistema: ou a conta é de um cliente, ou administra tudo. Vale a pena quando
  algum cliente pedir para dar acesso a alguém da equipe dele.
- **Cadastro aberto.** O modelo aceita, é só uma tela — mas aí entram e-mail,
  confirmação e conta falsa. Enquanto você conhece cada cliente, criar pela CLI
  é mais barato.
- **Cifrar o token do bot no banco.** Ele fica em texto. Quem alcança o banco
  normalmente alcança o `.env` do mesmo jeito, então a chave ao lado do dado
  protegeria pouco. Em compensação a API nunca devolve o token inteiro.
- **Domínio próprio por cliente** (`pecanha.betboard.com`). O `slug` já é único
  no sistema todo, então dá para migrar sem mexer nos dados.

---

## Comandos de referência

```bash
# testes (sem custo de API)
cd backend && .venv/Scripts/python -m pytest -m "not vision"

# lint
cd backend && .venv/Scripts/ruff check .

# contas
docker compose exec backend python -m app.cli list-users
docker compose exec backend python -m app.cli create-user --username X --bankroll "Nome"
docker compose exec backend python -m app.cli set-password --username X

# frontend — typecheck, lint e build
cd frontend && npx tsc --noEmit && npx eslint && npm run build

# migrations
docker compose exec backend alembic current
cd backend && .venv/Scripts/alembic revision --autogenerate -m "descrição"

# derrubar o stack
docker compose stop
```

---

## Mapa do que foi escrito

Backend (★ = novo nesta sessão):

```
backend/app/models/user.py                     ★ User, Bankroll
backend/app/models/tip.py                        Tip (agora com bankroll_id ★)
backend/app/services/users.py                  ★ contas, senha, autenticação
backend/app/services/bankrolls.py              ★ bancas, slug, endereço público
backend/app/services/telegram_setup.py         ★ diagnóstico e detecção de canal
backend/app/services/stats.py                    lucro, ROI, acerto, série diária
backend/app/services/tips.py                     ciclo da tip + set_result
backend/app/core/security.py                     PBKDF2 + JWT
backend/app/api/deps.py                          usuário logado + posse da banca ★
backend/app/api/routes/auth.py                   login e /auth/me
backend/app/api/routes/bankrolls.py            ★ CRUD + assistente do Telegram
backend/app/api/routes/public.py               ★ a página pública
backend/app/api/routes/tips.py                   rotas de tip (aninhadas ★)
backend/app/api/routes/stats.py                  consolidado por banca
backend/app/schemas/public.py                  ★ schemas SEM valores em reais
backend/app/cli.py                               extract, create-user ★, list-users ★
backend/alembic/versions/c3a1d5e7f204_*.py     ★ tabelas novas + migração dos dados
```

Frontend:

```
frontend/src/proxy.ts                            porteiro (isenta /b/* ★)
frontend/src/lib/api.ts                          cliente HTTP
frontend/src/lib/bets.ts                         lucro/ganho por tip, formatação
frontend/src/app/b/[slug]/page.tsx             ★ página pública (no servidor)
frontend/src/app/banca/[slug]/…                ★ banca, tips, config
frontend/src/app/bancas/page.tsx               ★ lista e criação de bancas
frontend/src/components/AppShell.tsx             lateral com as bancas ★
frontend/src/components/TelegramWizard.tsx     ★ o assistente de 3 passos
frontend/src/components/ConfigPage.tsx         ★ nome, endereço, público, canais
frontend/src/components/PublicBankrollPage.tsx ★ a tela que o assinante vê
frontend/src/components/BancasPage.tsx         ★
frontend/src/components/Dashboard.tsx            a tela da banca
frontend/src/components/BetList.tsx              lista agrupada + green/red
frontend/src/components/BankrollChart.tsx        gráfico SVG
```

Decisões de projeto que fogem do plano original:

1. **Campos da tip são nullable**, mais `needs_review` e `extraction_error` —
   sem isso não dá para distinguir "tip lida, aguardando resultado" de "não
   consegui ler o print".
2. **Os 7 campos são obrigatórios-porém-anuláveis no schema mandado à IA** — ela
   precisa se pronunciar sobre cada um (com `null`) em vez de omitir em silêncio.
3. **`/tips/preview` não persiste** — existe para calibrar extração e texto.
4. **Provedor de visão trocado para Gemini**; o Anthropic segue funcionando.
5. **Publicar é um passo separado de criar**, porque o stake em unidades vem da
   revisão.
6. **Retry só em 503/429** do provedor de visão, com backoff e jitter.
7. **Os testes rodam em SQLite na memória**, um banco por teste. O
   `expire_all()` a cada request imita a sessão nova de produção.
8. **Resultado é manual nesta fase.** `result_raw.source = "manual"` deixa a
   porta aberta para a automação da Fase 2 conviver com o conferido à mão.
9. **`connect_timeout` só é passado em Postgres** — é opção do psycopg, e com
   ela fixa a API não subia em SQLite.
10. **★ A banca, não a conta, é a unidade do sistema.** É ela que tem canal,
    tips e URL. Um tipster com VIP e Free não precisa de duas contas.
11. **★ Sem cadastro aberto.** Contas nascem pela CLI: nada de e-mail, SMTP ou
    conta falsa. Abrir depois não muda o modelo.
12. **★ A rota pública tem schemas próprios**, não um recorte dos internos —
    é o que impede um campo novo de vazar valor em reais por descuido.
13. **★ Banca de outra conta é 404, não 403.** Um 403 confirma a existência.
14. **★ O token do bot entra e não sai.** A API devolve só uma pista mascarada.
15. **★ O diagnóstico do Telegram não é exceção, é resposta.** Token errado e
    canal inexistente são o que estamos procurando — virar erro obrigaria o
    chamador a tratar o caminho normal como falha.
