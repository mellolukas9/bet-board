"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { BankrollChart } from "@/components/BankrollChart";
import { BetList, emJogo } from "@/components/BetList";
import { StatCards } from "@/components/StatCards";
import { ApiError, getStats, listTips } from "@/lib/api";
import { formatUnits } from "@/lib/bets";
import type { BankrollRead, BankrollStats, TipRead } from "@/types/api";

/** Recortes de período do painel. `dias: null` = a banca inteira. */
const PERIODOS = [
  { chave: "tudo", rotulo: "Tudo", dias: null },
  { chave: "30d", rotulo: "30 dias", dias: 30 },
  { chave: "7d", rotulo: "7 dias", dias: 7 },
  { chave: "hoje", rotulo: "Hoje", dias: 0 },
] as const;

type Periodo = (typeof PERIODOS)[number]["chave"];

/** A tela da banca, já com a moldura em volta. */
export function Dashboard({ slug }: { slug: string }) {
  return (
    <AppShell slug={slug} secao="banca">
      {(bankroll) => <Banca bankroll={bankroll} />}
    </AppShell>
  );
}

/**
 * O painel de uma banca.
 *
 * Os agregados vêm do `GET /bankrolls/{id}/stats` (o backend enxerga a banca
 * inteira); a lista vem do `/tips` da mesma banca e é filtrada por período
 * aqui — o filtro de data mora só no `/stats`, no backend.
 */
function Banca({ bankroll }: { bankroll: BankrollRead }) {
  const [periodo, setPeriodo] = useState<Periodo>("tudo");
  const [stats, setStats] = useState<BankrollStats | null>(null);
  const [tips, setTips] = useState<TipRead[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const since = desde(periodo);

  const buscar = useCallback(async () => {
    const [novasStats, novasTips] = await Promise.all([
      getStats(bankroll.id, since ? { since } : {}),
      listTips(bankroll.id, { limit: 200 }),
    ]);
    return {
      stats: novasStats,
      tips: since
        ? novasTips.filter((t) => t.created_at.slice(0, 10) >= since)
        : novasTips,
    };
  }, [bankroll.id, since]);

  /**
   * Carga inicial e troca de período.
   *
   * Os `setState` só rodam depois do `await`: no corpo síncrono do efeito o
   * React 19 reprova (`react-hooks/set-state-in-effect`). O `atual` descarta a
   * resposta de um período que já mudou.
   */
  useEffect(() => {
    let atual = true;

    void (async () => {
      try {
        const dados = await buscar();
        if (!atual) return;
        setStats(dados.stats);
        setTips(dados.tips);
        setErro(null);
      } catch (e) {
        if (atual) setErro(mensagemDe(e));
      } finally {
        if (atual) setCarregando(false);
      }
    })();

    return () => {
      atual = false;
    };
  }, [buscar]);

  async function recarregar() {
    setCarregando(true);
    try {
      const dados = await buscar();
      setStats(dados.stats);
      setTips(dados.tips);
      setErro(null);
    } catch (e) {
      setErro(mensagemDe(e));
    } finally {
      setCarregando(false);
    }
  }

  /**
   * Uma tip mudou de resultado: troca ela na lista e reconsulta os agregados.
   *
   * Recalcular os cartões no cliente pareceria mais rápido, mas eles somam a
   * banca toda — e a tela só tem a página carregada.
   */
  function aoMudar(tip: TipRead) {
    setTips((atuais) => atuais.map((t) => (t.id === tip.id ? tip : t)));
    void getStats(bankroll.id, since ? { since } : {})
      .then(setStats)
      .catch(() => {
        /* o número fica um instante velho; o próximo Atualizar corrige */
      });
  }

  const pendentes = tips.filter((t) => t.status === "pending").length;

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1.5">
          {PERIODOS.map((p) => (
            <button
              key={p.chave}
              type="button"
              onClick={() => {
                setPeriodo(p.chave);
                setCarregando(true);
              }}
              className={`rounded-lg px-3 py-1.5 text-sm transition ${
                periodo === p.chave
                  ? "bg-accent/20 font-medium text-white ring-1 ring-inset ring-accent/40"
                  : "border border-line text-muted hover:bg-white/5 hover:text-white"
              }`}
            >
              {p.rotulo}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          {pendentes > 0 && (
            <span className="text-xs text-muted">
              {formatUnits(emJogo(tips))} em jogo em {pendentes}{" "}
              {pendentes === 1 ? "aposta" : "apostas"}
            </span>
          )}
          <button
            type="button"
            onClick={() => void recarregar()}
            disabled={carregando}
            className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white disabled:opacity-40"
          >
            {carregando ? "Atualizando…" : "Atualizar"}
          </button>
        </div>
      </div>

      {erro && (
        <p
          role="alert"
          className="rounded-xl border border-red/30 bg-red/10 p-4 text-sm text-red"
        >
          {erro}
        </p>
      )}

      <BankrollChart series={stats?.series ?? []} carregando={carregando} />
      <StatCards stats={stats} />

      {stats && stats.needs_review > 0 && (
        <Link
          href={`/banca/${bankroll.slug}/tips`}
          className="flex items-center justify-between gap-3 rounded-xl border border-amber/30 bg-amber/10 px-4 py-3 text-sm transition hover:bg-amber/15"
        >
          <span>
            <strong className="text-amber">{stats.needs_review}</strong>{" "}
            {stats.needs_review === 1 ? "tip espera" : "tips esperam"} revisão
            — sem as unidades elas não vão para o grupo.
          </span>
          <span className="shrink-0 text-xs text-muted">Revisar →</span>
        </Link>
      )}

      <BetList tips={tips} onChange={aoMudar} carregando={carregando} />
    </div>
  );
}

/** Data inicial do período, no formato que o `/stats` espera (AAAA-MM-DD). */
function desde(periodo: Periodo): string | null {
  const dias = PERIODOS.find((p) => p.chave === periodo)?.dias;
  if (dias === null || dias === undefined) return null;

  const data = new Date();
  data.setDate(data.getDate() - dias);
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  return `${data.getFullYear()}-${mes}-${String(data.getDate()).padStart(2, "0")}`;
}

function mensagemDe(e: unknown): string {
  return e instanceof ApiError || e instanceof Error
    ? e.message
    : "Falha ao carregar o painel";
}
