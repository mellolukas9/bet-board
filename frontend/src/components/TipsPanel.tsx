"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, createTip, listTips } from "@/lib/api";
import type { BankrollRead, TipRead } from "@/types/api";

import { TipCard } from "./TipCard";

/**
 * Painel de tips: upload do print, fila de revisão e publicação.
 *
 * O print vai para `POST /bankrolls/{id}/tips`, que **grava** na banca aberta.
 * Toda tip nasce em revisão porque o `stake_units` só vem daqui.
 */
export function TipsPanel({ bankroll }: { bankroll: BankrollRead }) {
  const [tips, setTips] = useState<TipRead[]>([]);
  const [soRevisao, setSoRevisao] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const buscar = useCallback(
    () => listTips(bankroll.id, soRevisao ? { needsReview: true } : {}),
    [bankroll.id, soRevisao],
  );

  /**
   * Carga inicial e troca de filtro.
   *
   * Os `setState` só acontecem depois do `await` de propósito: chamá-los no
   * corpo síncrono do efeito dispara render em cascata, e o React 19 reprova
   * (`react-hooks/set-state-in-effect`). O `atual` descarta a resposta de um
   * filtro que já mudou.
   */
  useEffect(() => {
    let atual = true;

    void (async () => {
      try {
        const encontradas = await buscar();
        if (atual) {
          setTips(encontradas);
          setErro(null);
        }
      } catch (e) {
        if (atual) setErro(mensagemDe(e, "Falha ao carregar as tips"));
      } finally {
        if (atual) setCarregando(false);
      }
    })();

    return () => {
      atual = false;
    };
  }, [buscar]);

  async function carregar() {
    setCarregando(true);
    setErro(null);
    try {
      setTips(await buscar());
    } catch (e) {
      setErro(mensagemDe(e, "Falha ao carregar as tips"));
    } finally {
      setCarregando(false);
    }
  }

  async function subirPrint(file: File | undefined) {
    if (!file) return;

    setEnviando(true);
    setErro(null);
    try {
      const tip = await createTip(bankroll.id, file);
      // entra no topo: a listagem é mais recentes primeiro
      setTips((atuais) => [tip, ...atuais]);
    } catch (e) {
      setErro(mensagemDe(e, "Falha ao enviar o print"));
    } finally {
      setEnviando(false);
      // permite reenviar o mesmo arquivo (o input não dispara change com valor igual)
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  /** Troca a tip editada no lugar, sem recarregar a lista inteira. */
  function atualizar(tip: TipRead) {
    setTips((atuais) => atuais.map((t) => (t.id === tip.id ? tip : t)));
  }

  /** Tira da lista a tip descartada — o backend já a apagou. */
  function remover(tipId: number) {
    setTips((atuais) => atuais.filter((t) => t.id !== tipId));
  }

  return (
    <section>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-medium">Tips</h2>
          <p className="mt-1 text-sm text-muted">
            Suba o print, informe as unidades e publique nos canais.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setSoRevisao((v) => !v);
              setCarregando(true);
            }}
            className={`rounded-md border px-3 py-1.5 text-sm transition ${
              soRevisao
                ? "border-amber/40 bg-amber/10 text-amber"
                : "border-line text-muted hover:bg-white/5 hover:text-white"
            }`}
          >
            {soRevisao ? "Mostrando a fila" : "Fila de revisão"}
          </button>
          <button
            type="button"
            onClick={() => void carregar()}
            disabled={carregando}
            className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white disabled:opacity-40"
          >
            Atualizar
          </button>
        </div>
      </div>

      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          void subirPrint(e.dataTransfer.files[0]);
        }}
        onClick={() => inputRef.current?.click()}
        className="mt-5 cursor-pointer rounded-xl border border-dashed border-line px-6 py-10 text-center text-sm text-muted transition hover:border-accent/50 hover:bg-white/[.03] hover:text-white"
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          className="hidden"
          onChange={(e) => void subirPrint(e.target.files?.[0])}
        />
        {enviando ? "Lendo o print…" : "Clique ou arraste o print aqui"}
      </div>

      {erro && (
        <p className="mt-5 rounded-lg border border-red/30 bg-red/10 p-4 text-sm text-red">
          {erro}
        </p>
      )}

      <div className="mt-6 space-y-4">
        {carregando && tips.length === 0 && (
          <p className="text-sm text-muted">Carregando…</p>
        )}

        {!carregando && !enviando && tips.length === 0 && (
          <p className="rounded-xl border border-dashed border-line p-10 text-center text-sm text-muted">
            {soRevisao
              ? "Nenhuma tip esperando revisão."
              : "Nenhuma tip ainda. Suba um print para começar."}
          </p>
        )}

        {enviando && <LendoPrint />}

        {tips.map((tip) => (
          <TipCard
            key={tip.id}
            tip={tip}
            onChange={atualizar}
            onDescartar={remover}
          />
        ))}
      </div>
    </section>
  );
}

/**
 * Ocupa o lugar do card enquanto a IA lê o print.
 *
 * O contador existe porque a latência do provedor varia muito (medimos de 1,6s
 * a 48s no mesmo modelo): sem ele, uma leitura lenta parece travamento.
 *
 * O cronômetro mora aqui, e não no painel, porque o componente só existe
 * enquanto a leitura acontece — cada envio monta um novo, já começando do zero,
 * sem precisar de reset (que o React 19 reprovaria dentro do efeito).
 */
function LendoPrint() {
  const [segundos, setSegundos] = useState(0);

  useEffect(() => {
    const inicio = Date.now();
    const id = setInterval(
      () => setSegundos(Math.floor((Date.now() - inicio) / 1000)),
      500,
    );
    return () => clearInterval(id);
  }, []);

  return (
    <article className="rounded-xl border border-line bg-surface p-5">
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className="size-4 shrink-0 animate-spin rounded-full border-2 border-line border-t-accent"
        />
        <p role="status" className="text-sm font-medium">
          Lendo o print…{" "}
          <span className="tabular-nums text-muted">
            {segundos}s
          </span>
        </p>
      </div>

      <div aria-hidden className="mt-4 space-y-2">
        <div className="h-3 w-1/2 animate-pulse rounded bg-surface-3" />
        <div className="h-3 w-1/3 animate-pulse rounded bg-surface-3" />
      </div>

      {segundos >= 15 && (
        <p className="mt-4 text-sm text-amber">
          O provedor de visão está lento agora. A leitura continua — e se ele
          responder 503, o backend ainda tenta de novo antes de desistir.
        </p>
      )}
    </article>
  );
}

function mensagemDe(e: unknown, padrao: string): string {
  return e instanceof ApiError || e instanceof Error ? e.message : padrao;
}
