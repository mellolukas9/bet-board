"use client";

import { useState } from "react";

import { ApiError, detectTelegramChats, patchBankroll, testTelegram } from "@/lib/api";
import type { BankrollRead, ChatDetectado, TelegramDiagnostico } from "@/types/api";

/**
 * Assistente de conexão com o Telegram.
 *
 * A ordem dos passos não é decoração: configurar um bot de canal falha sempre
 * nos mesmos três lugares — token errado, bot fora do canal, e bot dentro do
 * canal mas sem ser administrador. Cada passo aqui fecha um deles, e o
 * diagnóstico do backend diz qual falta em português, em vez de deixar o
 * cliente descobrir no primeiro envio.
 *
 * O passo 3 existe porque canal privado não mostra o `chat_id` em lugar nenhum
 * do aplicativo: o bot lista as conversas que viu e a pessoa só escolhe.
 */
export function TelegramWizard({
  bankroll,
  onChange,
}: {
  bankroll: BankrollRead;
  onChange: (bankroll: BankrollRead) => void;
}) {
  const [token, setToken] = useState("");
  const [chatId, setChatId] = useState(bankroll.telegram_chat_id ?? "");
  const [chats, setChats] = useState<ChatDetectado[] | null>(null);
  const [dica, setDica] = useState<string | null>(null);
  const [diagnostico, setDiagnostico] = useState<TelegramDiagnostico | null>(null);
  const [ocupado, setOcupado] = useState<"detectar" | "testar" | "salvar" | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [salvo, setSalvo] = useState(false);

  /** Token digitado agora; vazio quer dizer "usa o que já está salvo". */
  const tokenAtual = token.trim() || undefined;
  const temToken = Boolean(tokenAtual) || bankroll.telegram_configured;

  async function detectar() {
    setOcupado("detectar");
    setErro(null);
    try {
      const resposta = await detectTelegramChats(bankroll.id, tokenAtual);
      setChats(resposta.chats);
      setDica(resposta.dica);
    } catch (e) {
      setErro(mensagem(e, "Falha ao procurar os canais"));
    } finally {
      setOcupado(null);
    }
  }

  async function testar() {
    setOcupado("testar");
    setErro(null);
    try {
      setDiagnostico(
        await testTelegram(bankroll.id, {
          bot_token: tokenAtual,
          chat_id: chatId.trim() || undefined,
        }),
      );
    } catch (e) {
      setErro(mensagem(e, "Falha ao testar a conexão"));
    } finally {
      setOcupado(null);
    }
  }

  async function salvar() {
    setOcupado("salvar");
    setErro(null);
    try {
      const mudancas: { telegram_bot_token?: string; telegram_chat_id: string } = {
        telegram_chat_id: chatId.trim(),
      };
      // token em branco significa "mantém o que está salvo", não "apaga"
      if (tokenAtual) mudancas.telegram_bot_token = tokenAtual;

      onChange(await patchBankroll(bankroll.id, mudancas));
      setToken("");
      setSalvo(true);
    } catch (e) {
      setErro(mensagem(e, "Falha ao salvar"));
    } finally {
      setOcupado(null);
    }
  }

  async function desconectar() {
    setOcupado("salvar");
    setErro(null);
    try {
      onChange(
        await patchBankroll(bankroll.id, {
          telegram_bot_token: "",
          telegram_chat_id: "",
        }),
      );
      setToken("");
      setChatId("");
      setDiagnostico(null);
      setChats(null);
    } catch (e) {
      setErro(mensagem(e, "Falha ao desconectar"));
    } finally {
      setOcupado(null);
    }
  }

  return (
    <section className="rounded-xl border border-line bg-surface">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
        <div>
          <h2 className="text-sm font-medium">Telegram</h2>
          <p className="mt-0.5 text-xs text-muted">
            O canal onde as tips desta banca são publicadas.
          </p>
        </div>
        <Situacao bankroll={bankroll} diagnostico={diagnostico} />
      </header>

      <div className="space-y-6 p-5">
        <Passo
          numero={1}
          titulo="Crie o bot no Telegram"
          pronto={bankroll.telegram_configured || Boolean(tokenAtual)}
        >
          <ol className="list-inside list-decimal space-y-1 text-sm text-muted">
            <li>
              Abra o Telegram e converse com{" "}
              <a
                href="https://t.me/BotFather"
                target="_blank"
                rel="noreferrer noopener"
                className="text-accent underline underline-offset-2"
              >
                @BotFather
              </a>
            </li>
            <li>
              Mande <code className="rounded bg-surface-3 px-1 font-mono">/newbot</code> e
              escolha um nome e um usuário para o bot
            </li>
            <li>
              Ele responde com uma linha parecida com{" "}
              <code className="rounded bg-surface-3 px-1 font-mono text-[11px]">
                1234567890:AAH...
              </code>{" "}
              — esse é o token
            </li>
          </ol>

          <label className="mt-3 block text-xs font-medium text-muted" htmlFor="token">
            Token do bot
          </label>
          <input
            id="token"
            value={token}
            onChange={(e) => {
              setToken(e.target.value);
              setSalvo(false);
            }}
            placeholder={
              bankroll.telegram_bot_token_hint ?? "1234567890:AAHexemploDeToken"
            }
            autoComplete="off"
            spellCheck={false}
            className="mt-1.5 w-full rounded-lg border border-line bg-surface-2 px-3 py-2 font-mono text-sm outline-none transition focus:border-accent/60"
          />
          {bankroll.telegram_configured && !tokenAtual && (
            <p className="mt-1.5 text-xs text-muted">
              Já há um token salvo ({bankroll.telegram_bot_token_hint}). Deixe em
              branco para mantê-lo.
            </p>
          )}
        </Passo>

        <Passo
          numero={2}
          titulo="Ponha o bot no canal, como administrador"
          pronto={diagnostico?.bot_e_admin ?? false}
        >
          <ol className="list-inside list-decimal space-y-1 text-sm text-muted">
            <li>Abra o seu canal no Telegram</li>
            <li>
              Vá em <strong className="text-foreground/90">Administradores</strong> →{" "}
              <strong className="text-foreground/90">Adicionar administrador</strong>
            </li>
            <li>
              Procure o bot pelo usuário dele
              {diagnostico?.bot_username && (
                <>
                  {" "}
                  (<span className="font-mono">@{diagnostico.bot_username}</span>)
                </>
              )}{" "}
              e adicione
            </li>
            <li>
              Deixe a permissão{" "}
              <strong className="text-foreground/90">Publicar mensagens</strong> ligada
            </li>
          </ol>
          <p className="mt-2 rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs text-muted">
            Em canal, bot comum não posta. Sem ser administrador, o envio volta
            com <span className="font-mono">need administrator rights</span>.
          </p>
        </Passo>

        <Passo
          numero={3}
          titulo="Escolha o canal"
          pronto={Boolean(chatId.trim())}
        >
          <p className="text-sm text-muted">
            Mande qualquer mensagem no canal e clique em detectar — o bot só
            enxerga os canais em que já viu movimento.
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void detectar()}
              disabled={!temToken || ocupado !== null}
              className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white disabled:opacity-40"
            >
              {ocupado === "detectar" ? "Procurando…" : "Detectar canais"}
            </button>
            {!temToken && (
              <span className="self-center text-xs text-muted">
                informe o token primeiro
              </span>
            )}
          </div>

          {chats !== null && chats.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {chats.map((chat) => (
                <li key={chat.chat_id}>
                  <button
                    type="button"
                    onClick={() => {
                      setChatId(chat.chat_id);
                      setSalvo(false);
                    }}
                    className={`flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left text-sm transition ${
                      chatId === chat.chat_id
                        ? "border-accent/50 bg-accent/10"
                        : "border-line hover:bg-white/5"
                    }`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate">{chat.title}</span>
                      <span className="text-xs text-muted">{chat.type}</span>
                    </span>
                    <span className="shrink-0 font-mono text-xs text-muted">
                      {chat.chat_id}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {dica && chats?.length === 0 && (
            <p className="mt-3 rounded-lg border border-amber/30 bg-amber/10 px-3 py-2 text-xs text-amber">
              {dica}
            </p>
          )}

          <label className="mt-3 block text-xs font-medium text-muted" htmlFor="chat">
            ID do canal
          </label>
          <input
            id="chat"
            value={chatId}
            onChange={(e) => {
              setChatId(e.target.value);
              setSalvo(false);
            }}
            placeholder="-1001234567890"
            autoComplete="off"
            spellCheck={false}
            className="mt-1.5 w-full rounded-lg border border-line bg-surface-2 px-3 py-2 font-mono text-sm outline-none transition focus:border-accent/60"
          />
        </Passo>

        {diagnostico && <Resultado diagnostico={diagnostico} />}

        {erro && (
          <p
            role="alert"
            className="rounded-lg border border-red/30 bg-red/10 px-3 py-2 text-sm text-red"
          >
            {erro}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
          <button
            type="button"
            onClick={() => void testar()}
            disabled={!temToken || ocupado !== null}
            className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white disabled:opacity-40"
          >
            {ocupado === "testar" ? "Testando…" : "Testar conexão"}
          </button>

          <button
            type="button"
            onClick={() => void salvar()}
            disabled={ocupado !== null || (!tokenAtual && !chatId.trim())}
            className="rounded-lg bg-green px-3 py-1.5 text-sm font-semibold text-[#062018] transition hover:brightness-110 disabled:opacity-40"
          >
            {ocupado === "salvar" ? "Salvando…" : "Salvar"}
          </button>

          {salvo && <span className="text-xs text-green">salvo</span>}

          {bankroll.telegram_configured && (
            <button
              type="button"
              onClick={() => void desconectar()}
              disabled={ocupado !== null}
              className="ml-auto rounded-lg px-3 py-1.5 text-sm text-muted transition hover:bg-red/10 hover:text-red disabled:opacity-40"
            >
              Desconectar
            </button>
          )}
        </div>
      </div>
    </section>
  );
}

function Passo({
  numero,
  titulo,
  pronto,
  children,
}: {
  numero: number;
  titulo: string;
  pronto: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-3">
      <span
        aria-hidden
        className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full text-xs font-semibold ${
          pronto ? "bg-green/20 text-green" : "bg-surface-3 text-muted"
        }`}
      >
        {pronto ? "✓" : numero}
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="text-sm font-medium">{titulo}</h3>
        <div className="mt-2">{children}</div>
      </div>
    </div>
  );
}

/** Selo do cabeçalho: o que o último teste disse, ou o que está salvo. */
function Situacao({
  bankroll,
  diagnostico,
}: {
  bankroll: BankrollRead;
  diagnostico: TelegramDiagnostico | null;
}) {
  if (diagnostico?.ok) {
    return <Selo tom="green">conectado</Selo>;
  }
  if (diagnostico) {
    return <Selo tom="red">falta configurar</Selo>;
  }
  return bankroll.telegram_configured ? (
    <Selo tom="neutro">salvo — teste para confirmar</Selo>
  ) : (
    <Selo tom="neutro">não configurado</Selo>
  );
}

function Selo({
  tom,
  children,
}: {
  tom: "green" | "red" | "neutro";
  children: React.ReactNode;
}) {
  const cor =
    tom === "green"
      ? "bg-green/15 text-green"
      : tom === "red"
        ? "bg-red/15 text-red"
        : "bg-white/5 text-muted";
  return <span className={`rounded-full px-2.5 py-1 text-xs ${cor}`}>{children}</span>;
}

function Resultado({ diagnostico }: { diagnostico: TelegramDiagnostico }) {
  if (diagnostico.ok) {
    return (
      <div className="rounded-lg border border-green/30 bg-green/10 px-4 py-3 text-sm">
        <p className="font-medium text-green">Tudo certo.</p>
        <p className="mt-1 text-muted">
          O bot <span className="font-mono">@{diagnostico.bot_username}</span> pode
          publicar em <strong className="text-foreground/90">{diagnostico.canal_titulo}</strong>.
          As tips desta banca vão sair por aí.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-amber/30 bg-amber/10 px-4 py-3 text-sm">
      <p className="font-medium text-amber">Falta um passo:</p>
      <ul className="mt-1.5 list-inside list-disc space-y-1 text-muted">
        {diagnostico.problemas.map((problema) => (
          <li key={problema}>{problema}</li>
        ))}
      </ul>
    </div>
  );
}

function mensagem(e: unknown, padrao: string): string {
  return e instanceof ApiError || e instanceof Error ? e.message : padrao;
}
