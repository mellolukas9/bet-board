"use client";

import { useState } from "react";

import { ApiError, deleteTip, patchTip, publishTip } from "@/lib/api";
import type { Channel, MessageStatus, TipRead, TipUpdate } from "@/types/api";

/** Campos que o backend exige para publicar (REQUIRED_TO_PUBLISH). */
const OBRIGATORIOS = ["event", "market", "odd", "stake_units"] as const;

const EDITAVEIS = [
  ["event", "Evento", "Flamengo x Palmeiras"],
  ["market", "Mercado", "Over 2.5 gols"],
  ["odd", "Odd", "1.85"],
  ["stake_units", "Unidades", "2"],
  ["source", "Casa", "Bet365"],
  ["stake", "Stake (R$)", "150.00"],
  ["link", "Link da aposta", "https://bet365.com/..."],
] as const;

type Campo = (typeof EDITAVEIS)[number][0];

/** Rótulo de tela para cada campo — o aviso não pode falar "stake_units". */
const ROTULOS: Record<string, string> = Object.fromEntries(
  EDITAVEIS.map(([campo, rotulo]) => [campo, rotulo.toLowerCase()]),
);

/** Casas que o grupo usa. A IA lê o nome do print, mas aqui é lista fechada. */
const CASAS = ["Bet365", "Betano"] as const;

/**
 * Opções do dropdown de casa.
 *
 * Inclui o que a IA leu quando for algo fora da lista — senão abrir a tip já
 * trocaria silenciosamente a casa extraída pela primeira do dropdown.
 */
function opcoesDeCasa(atual: string): readonly string[] {
  return atual && !CASAS.includes(atual as (typeof CASAS)[number])
    ? [...CASAS, atual]
    : CASAS;
}

/** O que falta para a tip poder ser publicada. */
function faltando(tip: TipRead): string[] {
  return OBRIGATORIOS.filter((campo) => tip[campo] === null);
}

function jaPublicada(tip: TipRead): boolean {
  return tip.messages.some((log) => log.status === "sent");
}

function rotuloCanal(canal: Channel, status: MessageStatus): string {
  const nome = canal === "telegram" ? "Telegram" : "WhatsApp";
  return status === "sent" ? `${nome}: enviada` : `${nome}: falhou`;
}

function mensagemDe(e: unknown, padrao: string): string {
  return e instanceof ApiError || e instanceof Error ? e.message : padrao;
}

/**
 * Uma tip na lista: revisão dos campos e publicação.
 *
 * O `stake_units` é o campo que importa — é ele que destrava o publish, e a IA
 * nunca o preenche (o print só traz reais).
 */
export function TipCard({
  tip,
  onChange,
  onDescartar,
}: {
  tip: TipRead;
  onChange: (tip: TipRead) => void;
  onDescartar: (tipId: number) => void;
}) {
  const [rascunho, setRascunho] = useState<Partial<Record<Campo, string>>>({});
  const [salvando, setSalvando] = useState(false);
  const [publicando, setPublicando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [descartando, setDescartando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [enviada, setEnviada] = useState<{
    message: string;
    channels: Partial<Record<Channel, MessageStatus>>;
  } | null>(null);

  const pendentes = faltando(tip);
  const publicavel = pendentes.length === 0;
  const publicada = jaPublicada(tip);

  // Compara o valor, não a presença da chave: digitar e desfazer voltava a
  // contar como alteração, e o botão dizia "Salvar" sem ter o que salvar.
  const alterados = Object.entries(rascunho).filter(
    ([campo, texto]) => texto !== (tip[campo as Campo] ?? ""),
  );
  const temRascunho = alterados.length > 0;

  /** Valor exibido: o que o admin digitou, ou o que veio do banco. */
  function valor(campo: Campo): string {
    return rascunho[campo] ?? tip[campo] ?? "";
  }

  async function salvar() {
    if (alterados.length === 0) {
      setRascunho({});
      return;
    }

    setSalvando(true);
    setErro(null);
    try {
      // campo apagado vira null explícito — é como o backend limpa o valor
      const patch: TipUpdate = Object.fromEntries(
        alterados.map(([campo, texto]) => [campo, texto.trim() || null]),
      );
      onChange(await patchTip(tip.id, patch));
      setRascunho({});
    } catch (e) {
      setErro(mensagemDe(e, "Falha ao salvar a correção"));
    } finally {
      setSalvando(false);
    }
  }

  async function descartar() {
    setDescartando(true);
    setErro(null);
    try {
      await deleteTip(tip.id);
      onDescartar(tip.id);
    } catch (e) {
      setErro(mensagemDe(e, "Falha ao descartar"));
      setDescartando(false);
      setConfirmando(false);
    }
    // sem finally: em caso de sucesso o card sai da lista e não há o que atualizar
  }

  async function publicar() {
    setPublicando(true);
    setErro(null);
    try {
      const resultado = await publishTip(tip.id);
      onChange(resultado.tip);
      setEnviada({ message: resultado.message, channels: resultado.channels });
    } catch (e) {
      setErro(mensagemDe(e, "Falha ao publicar"));
    } finally {
      setPublicando(false);
    }
  }

  const canais: [Channel, MessageStatus][] = enviada
    ? (Object.entries(enviada.channels) as [Channel, MessageStatus][])
    : tip.messages.map((log) => [log.channel, log.status]);

  return (
    <article className="rounded-xl border border-line bg-surface p-5">
      <header className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-medium">
            {tip.event ?? (
              <span className="text-muted">sem evento</span>
            )}
          </h3>
          <p className="mt-0.5 truncate text-sm text-muted">
            #{tip.id}
            {tip.market ? ` · ${tip.market}` : ""}
            {tip.odd ? ` · odd ${tip.odd}` : ""}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              publicada
                ? "bg-green/15 text-green"
                : tip.needs_review
                  ? "bg-amber/15 text-amber"
                  : "bg-accent/15 text-accent"
            }`}
          >
            {publicada ? "publicada" : tip.needs_review ? "em revisão" : "pronta"}
          </span>

          {/* tip publicada não tem X: o backend recusa apagar o que já foi
              para o grupo, então oferecer o botão só daria erro na cara */}
          {!publicada && !confirmando && (
            <button
              type="button"
              onClick={() => setConfirmando(true)}
              aria-label={`Descartar a tip ${tip.id}`}
              title="Descartar"
              className="rounded-md px-2 py-1 text-sm leading-none text-muted transition hover:bg-red/10 hover:text-red"
            >
              ✕
            </button>
          )}
        </div>
      </header>

      {/* confirmação inline: um confirm() do navegador travaria a página */}
      {confirmando && (
        <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg border border-red/30 bg-red/10 p-3">
          <p className="text-sm text-red">
            Descartar esta tip? Não dá para desfazer.
          </p>
          <div className="ml-auto flex gap-2">
            <button
              type="button"
              onClick={() => setConfirmando(false)}
              disabled={descartando}
              className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white disabled:opacity-40"
            >
              Manter
            </button>
            <button
              type="button"
              onClick={() => void descartar()}
              disabled={descartando}
              className="rounded-lg bg-red px-3 py-1.5 text-sm font-semibold text-[#2a0612] transition hover:brightness-110 disabled:opacity-40"
            >
              {descartando ? "Descartando…" : "Descartar"}
            </button>
          </div>
        </div>
      )}

      {tip.extraction_error && (
        <p className="mt-4 rounded-lg border border-amber/30 bg-amber/10 p-3 text-sm text-amber">
          Leitura falhou: {tip.extraction_error}
        </p>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {EDITAVEIS.map(([campo, label, exemplo]) => {
          const obrigatorio = (OBRIGATORIOS as readonly string[]).includes(campo);
          return (
            <label
              key={campo}
              // o link é longo demais para meia largura
              className={`block text-sm ${campo === "link" ? "sm:col-span-2" : ""}`}
            >
              <span className="text-muted">
                {label}
                {obrigatorio && tip[campo] === null && (
                  <span className="ml-1 text-amber">*</span>
                )}
              </span>
              {campo === "source" ? (
                <select
                  value={valor(campo)}
                  disabled={publicada}
                  onChange={(e) =>
                    setRascunho((atual) => ({ ...atual, [campo]: e.target.value }))
                  }
                  className="mt-1 w-full rounded-lg border border-line bg-surface-2 px-2.5 py-1.5 text-sm outline-none transition focus:border-accent/60 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <option value="">não informada</option>
                  {opcoesDeCasa(valor(campo)).map((casa) => (
                    <option key={casa} value={casa}>
                      {casa}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  value={valor(campo)}
                  placeholder={exemplo}
                  type={campo === "link" ? "url" : "text"}
                  inputMode={campo === "link" ? "url" : undefined}
                  spellCheck={campo === "link" ? false : undefined}
                  disabled={publicada}
                  onChange={(e) =>
                    setRascunho((atual) => ({ ...atual, [campo]: e.target.value }))
                  }
                  className="mt-1 w-full rounded-lg border border-line bg-surface-2 px-2.5 py-1.5 text-sm outline-none transition focus:border-accent/60 disabled:cursor-not-allowed disabled:opacity-60"
                />
              )}
            </label>
          );
        })}
      </div>

      {!publicavel && !publicada && (
        <p className="mt-3 text-sm text-amber">
          Falta preencher para publicar:{" "}
          {pendentes.map((campo) => ROTULOS[campo] ?? campo).join(", ")}.
        </p>
      )}

      {erro && (
        <p className="mt-3 rounded-lg border border-red/30 bg-red/10 p-3 text-sm text-red">
          {erro}
        </p>
      )}

      {/* Enviada é ponto final: campos travados, sem salvar e sem republicar,
          para o card não sugerir edição que não muda mais a mensagem do grupo.
          Uma tentativa que só falhou não conta — aí o card segue editável. */}
      {!publicada && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {/* Antes o botão ficava cinza e clicável-mas-não quando não havia o
              que salvar, e lido de fora parecia quebrado. Agora ele só existe
              quando há alteração; sem ela, o lugar dele diz que está salvo. */}
          {temRascunho ? (
            <button
              type="button"
              onClick={() => void salvar()}
              disabled={salvando}
              className="rounded-lg border border-accent/50 bg-accent/15 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-accent/25 disabled:opacity-40"
            >
              {salvando ? "Salvando…" : `Salvar ${alterados.length} alteração${alterados.length > 1 ? "ões" : ""}`}
            </button>
          ) : (
            <span className="px-1 text-sm text-muted">✓ salvo</span>
          )}

          <button
            type="button"
            onClick={() => void publicar()}
            disabled={!publicavel || publicando || temRascunho}
            className="rounded-lg bg-green px-3 py-1.5 text-sm font-semibold text-[#062018] transition hover:brightness-110 disabled:opacity-40"
          >
            {publicando ? "Publicando…" : "Publicar"}
          </button>

          {temRascunho && (
            <span className="text-xs text-amber">
              salve antes de publicar
            </span>
          )}
        </div>
      )}

      {canais.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {canais.map(([canal, status]) => (
            <span
              key={canal}
              className={`rounded-full px-2.5 py-1 text-xs ${
                status === "sent"
                  ? "bg-green/15 text-green"
                  : "bg-red/15 text-red"
              }`}
            >
              {rotuloCanal(canal, status)}
            </span>
          ))}
        </div>
      )}

      {/* o motivo da falha fica no message_log; é ele que diz o que corrigir */}
      {tip.messages
        .filter((log) => log.error)
        .map((log) => (
          <p
            key={log.id}
            className="mt-2 rounded-lg border border-red/30 bg-red/10 p-3 text-xs text-red"
          >
            {log.channel}: {log.error}
          </p>
        ))}

      {enviada && (
        <pre className="mt-4 whitespace-pre-wrap rounded-lg border border-line bg-surface-2 p-4 font-sans text-sm">
          {enviada.message}
        </pre>
      )}
    </article>
  );
}
