# Bet Board

Ferramenta de administração de grupos de tips esportivas. Automatiza o ciclo:
print da tip → mensagem padronizada → validação RED/GREEN → gestão de assinantes
→ consolidação de resultados.

O plano completo está em [`bet-board-plano-desenvolvimento.md`](./bet-board-plano-desenvolvimento.md).
Para publicar (Vercel + Render + Neon), ver [`DEPLOY.md`](./DEPLOY.md).

**Status:** Fase 1 concluída, menos o WhatsApp (1.6). O sistema é
**multi-cliente**: cada tipster tem a sua conta, as suas bancas, o seu canal do
Telegram e uma página pública de resultados.

## Estrutura

```
backend/    API FastAPI (Python 3.12) — pipeline, regras de negócio, banco
frontend/   Painel do admin (Next.js + TypeScript + Tailwind)
```

## Rodando com Docker

```bash
cp .env.example .env     # preencha os segredos
docker compose up -d
```

- API: http://localhost:8000 (docs em `/docs`)
- Painel: http://localhost:3000 (pede login — veja abaixo)

O backend roda `alembic upgrade head` no start, então o banco já sobe migrado.

## Rodando local (sem Docker)

**Backend** — requer Python 3.12:

```bash
cd backend
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pytest
.venv/Scripts/uvicorn app.main:app --reload
```

Precisa de um Postgres acessível na `DATABASE_URL`. Sem ele a API sobe normalmente
e o `/health` reporta `database: "down"`.

**Frontend** — requer Node 20+:

```bash
cd frontend
npm install
npm run dev
```

A URL do backend vem de `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`).
Para sobrescrever local, crie `frontend/.env.local` — o Next não lê o `.env` da raiz.

O build usa `output: "standalone"` (imagem Docker enxuta), então `npm run start` não
funciona. Para rodar o build de produção local: `node .next/standalone/server.js`.

## Conta → banca → tips

```
user (o tipster)
 └── bankroll "Vip Peçanha"     /b/vip-pecanha
     ├── token do bot + canal do Telegram
     └── tips
 └── bankroll "Free"            /b/free-pecanha
     ├── outro canal
     └── tips
```

A **banca** é a unidade que importa: ela tem o canal de envio, as tips e a
página pública. Um mesmo tipster pode ter VIP e Free sem misturar resultado
nenhum, e um servidor atende vários clientes.

### Dois papéis

| Papel | O que faz | Onde |
|---|---|---|
| **Cliente** (tipster) | administra as bancas dele | `/banca/<slug>` |
| **Administrador do sistema** | cria e desativa as contas | `/admin` |

Para quem não é administrador, `/admin` responde "não encontrada" — um 403
confirmaria que existe um painel a mais.

### Criando a conta de um cliente

Pelo painel, em **Administração**: usuário, nome, a primeira banca e uma senha
já gerada (copie antes de sair da tela — ela não aparece de novo).

Pela CLI, quando não há painel à mão — é como nasce o **primeiro**
administrador:

```bash
cd backend
.venv/Scripts/python -m app.cli create-user --username lucas --superuser
.venv/Scripts/python -m app.cli create-user --username pecanha     --name "Peçanha" --bankroll "Vip Peçanha"
```

O comando pergunta a senha (sem ecoar) e imprime o endereço público da banca.
Outros comandos:

```bash
.venv/Scripts/python -m app.cli list-users                    # contas e bancas
.venv/Scripts/python -m app.cli promote --username lucas      # vira administrador
.venv/Scripts/python -m app.cli set-password --username pecanha
```

Em deploy remoto, onde nem sempre há shell, `SUPERUSER_USERNAME` e
`SUPERUSER_PASSWORD` no ambiente criam (ou promovem) essa conta no start da
API, uma vez. Ver [`DEPLOY.md`](./DEPLOY.md).

No Docker, troque o prefixo por `docker compose exec backend python -m app.cli`.

O `AUTH_SECRET_KEY` do `.env` assina o token da sessão; gere um com
`python -c "import secrets; print(secrets.token_urlsafe(48))"`. Vazio, cada
restart da API derruba as sessões.

O login devolve um JWT que o painel guarda num cookie e manda no
`Authorization: Bearer`. **Todas** as rotas de `/bankrolls` e `/tips` exigem
ele; só `/health`, `/auth/login` e `/public/bankrolls/{slug}` são públicos.
Banca de outra conta responde **404**, não 403 — um 403 confirmaria que ela
existe.

### A sessão cai sozinha

Ela tem dois prazos, e o token carrega os dois:

| Prazo | Padrão | O que é |
|---|---|---|
| `AUTH_IDLE_TIMEOUT_MINUTES` | 10 min | inatividade: é o `exp` do token |
| `AUTH_TOKEN_TTL_MINUTES` | 12 h | teto: por mais ativa que a pessoa esteja |

O token vale poucos minutos e o painel o renova pelo `POST /auth/refresh`
enquanto a pessoa mexe na tela. Quem larga o painel aberto não renova nada, e o
token expira **no servidor** — a sessão não depende de o navegador se comportar.
A renovação carrega o teto adiante em vez de recalculá-lo, senão uma aba aberta
renovaria para sempre.

Um minuto antes de cair, a tela avisa e oferece "continuar conectado": a revisão
de uma tip é um formulário meio preenchido, e ninguém deveria descobrir o prazo
perdendo o que digitou. Caiu, o login explica o motivo em vez de aparecer do
nada.

## O painel

Por banca, três telas:

- **Banca** (`/banca/<slug>`) — a curva em unidades, os cartões (apostas,
  lucro, ROI, acerto) e a lista de apostas agrupada por mês e dia, cada grupo
  com o seu saldo. É aqui que se marca o resultado. Cada número tem um "?" ao
  lado com a explicação em uma frase — ROI e "unidade" são jargão de quem já
  opera banca, e o painel é usado por quem está começando.
- **Tips** (`/banca/<slug>/tips`) — sobe o print, corrige o que a IA leu
  errado, informa as unidades e publica no canal.
- **Configurações** (`/banca/<slug>/config`) — nome, endereço público,
  liga/desliga a página pública e conecta o Telegram.

## A página pública

`/b/<slug>` é o link que o tipster manda para os assinantes. Ela mostra o
gráfico, os cartões e a lista de apostas — **tudo em unidades**.

Os filtros de **período** (tudo / 90 / 30 / 7 dias) e de **resultado** (ganhas,
perdidas, encerradas, em aberto) são links, não botões: a página é renderizada
no servidor, e o recorte escolhido fica na URL — dá para mandar
`/b/vip-pecanha?periodo=30d` para alguém. O período vale para os números **e**
para a lista; o resultado recorta só a lista, porque cartões de um resultado
escolhido a dedo sempre diriam 100% de acerto.

O `<slug>` **sai do nome da banca**, sempre: "Vip Peçanha" vira
`/b/vip-pecanha`. Não há campo de endereço editável — ter os dois separados
deixaria `/b/vip-pecanha` numa banca chamada "Free". Renomear a banca move o
link junto, e o painel avisa que o endereço antigo para de funcionar. O valor em
reais, o print original, o erro de leitura e o log de envio não saem por ali:
os schemas da rota pública (`app/schemas/public.py`) são outros, não um recorte
dos internos, então um campo novo não vaza por descuido.

A banca **nasce privada**. Enquanto não for publicada, `/b/<slug>` responde 404
para todo mundo.

## Conectando o Telegram (o que o cliente faz sozinho)

Em **Configurações → Telegram** há um assistente de três passos, porque
configurar um bot de canal falha sempre nos mesmos três lugares:

1. **Criar o bot** — conversar com [@BotFather](https://t.me/BotFather), mandar
   `/newbot`, colar o token que ele responde.
2. **Pôr o bot no canal como administrador**, com "Publicar mensagens" ligada.
   Em canal, bot comum não posta: sem isso o envio volta com
   `need administrator rights`.
3. **Escolher o canal** — canal privado não mostra o `chat_id` em lugar nenhum
   do aplicativo, então o botão **Detectar canais** lista as conversas que o
   bot já viu (mande uma mensagem no canal antes) e a pessoa só clica na certa.

O botão **Testar conexão** pergunta ao Telegram antes de qualquer envio
(`getMe`, `getChat`, `getChatMember`) e diz em português o que falta — em vez
de deixar o cliente descobrir na hora em que a tip devia sair.

O token do bot **nunca volta inteiro** da API: o painel recebe só uma pista
(`8741270881:…s8j8`) para a pessoa reconhecer qual bot está ali.

### O resultado é marcado à mão

**Não há API esportiva nesta fase.** Na lista da Banca, cada aposta pendente
tem quatro botões na faixa da direita:

| Botão | O que faz |
|---|---|
| ✓ | green — a aposta ganhou |
| ✕ | red — a aposta perdeu |
| ∅ | void — anulada, o stake volta e não conta no ROI |
| ⇄ | cashout — encerrada antes do fim, pelo valor que a casa ofereceu |

Clicar na faixa de uma aposta já resolvida abre o **desfazer** (volta para
pendente). O resultado é gravado com `source: "manual"` no `result_raw`, para a
validação automática da Fase 2 conseguir se distinguir do que foi conferido à
mão.

#### O encerramento antecipado (cash out)

Encerrar **não é** green nem red: o valor devolvido tanto pode estar acima do
apostado (lucro) quanto abaixo (prejuízo), e juntá-lo aos outros dois faria a
taxa de acerto mentir nos dois sentidos. Por isso ele é um status próprio.

O ⇄ abre um campo pedindo **por quanto a aposta foi encerrada, em reais** — é
como a casa oferece o cash out, na tela em que a pessoa acabou de clicar. As
unidades saem da proporção com o valor apostado: encerrar 150 reais (2u) por 180
devolve 2,4u, ou seja +0,4u na banca. A prévia mostra essa conta antes de
gravar.

É por isso que o **valor da aposta em reais virou campo obrigatório** para
publicar (junto de evento, mercado, odd e unidades): é ele que ancora as
unidades. Sem ele o encerramento não teria como virar unidade, e a tip entraria
na banca valendo zero. A IA costuma lê-lo do print; quando não lê, o campo fica
marcado como faltando, como qualquer outro.

Na taxa de acerto, um encerramento com saldo positivo conta como acerto — sair
da aposta ganhando dinheiro é um acerto para quem seguiu a tip.

## Testando a leitura de prints

Coloque a chave da API de visão no `.env` da raiz:

```
VISION_PROVIDER=gemini
VISION_API_KEY=...
VISION_MODEL=models/gemini-3.5-flash-lite
```

A chave do Gemini sai do [Google AI Studio](https://aistudio.google.com/apikey).

Para usar o Claude, troque o provedor e o modelo — o resto do código não muda:

```
VISION_PROVIDER=anthropic
VISION_API_KEY=sk-ant-...
VISION_MODEL=claude-haiku-4-5-20251001
```

A chave sai do [console da Anthropic](https://console.anthropic.com/settings/keys).
`VISION_MEDIA_RESOLUTION` só vale para o Gemini; no Anthropic ele é ignorado.

Jogue prints no CLI e veja a extração na hora:

```bash
cd backend
.venv/Scripts/python -m app.cli extract caminho/do/print.png
.venv/Scripts/python -m app.cli extract tests/fixtures/prints/*.png --json
```

Campos marcados com `!` não foram encontrados no print — na API, uma tip nesse
estado entra na fila de revisão manual em vez de quebrar o fluxo.

Para medir a taxa de acerto sobre a base de prints
(veja [`backend/tests/fixtures/prints/README.md`](./backend/tests/fixtures/prints/README.md)):

```bash
pytest -m vision      # chama a API de verdade e custa dinheiro
pytest -m "not vision"  # o resto da suíte, sem custo
```

## Migrations

```bash
cd backend
.venv/Scripts/alembic revision --autogenerate -m "descrição"
.venv/Scripts/alembic upgrade head
```

> A migration `c3a1d5e7f204` criou `user` e `bankroll` e moveu as tips
> existentes: quem vinha da versão de um cliente só não perde login nem
> histórico. Ela lê `ADMIN_*` e `TELEGRAM_*` do ambiente **uma vez** e passa
> esses valores para a primeira banca.

Models novos precisam ser importados em `app/models/__init__.py` para entrar no
autogenerate.

## Configuração

Tudo via variáveis de ambiente — veja [`.env.example`](./.env.example).
O `.env` fica fora do git.
