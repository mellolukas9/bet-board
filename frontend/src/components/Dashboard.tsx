"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Ajuda } from "@/components/Ajuda";
import { useBanca } from "@/components/AppShell";
import { BankrollChart } from "@/components/BankrollChart";
import { BetList, emJogo } from "@/components/BetList";
import { StatCards } from "@/components/StatCards";
import { ApiError, getStats, listTips } from "@/lib/api";
import { formatUnits } from "@/lib/bets";
import type { BankrollStats, TipRead } from "@/types/api";

/** Recortes de período do painel. `dias: null` = a banca inteira. */
const PERIODOS = [
  { chave: "tudo", rotulo: "Tudo", dias: null },
  { chave: "30d", rotulo: "30 dias", dias: 30 },
  { chave: "7d", rotulo: "7 dias", dias: 7 },
  { chave: "hoje", rotulo: "Hoje", dias: 0 },
] as const;

type Periodo = (typeof PERIODOS)[number]["chave"];

/**
 * O painel de uma banca.
 *
 * Os agregados vêm do `GET /bankrolls/{id}/stats` e a lista do `/tips` da mesma
 * banca — os dois com o mesmo `since`, para os cartões e o extrato falarem do
 * mesmo período.
 *
 * Ambos contam **só tip publicada**: o que está na fila de revisão ainda é
 * rascunho, ninguém do grupo apostou nele, e por isso não há green ou red a
 * confirmar. A aba Tips é onde essas vivem.
 */
export function Dashboard() {
  const { banca } = useBanca();
  const [periodo, setPeriodo] = useState<Periodo>("tudo");
  const [stats, setStats] = useState<BankrollStats | null>(null);
  const [tips, setTips] = useState<TipRead[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const since = desde(periodo);

  const buscar = useCallback(async () => {
    const [novasStats, novasTips] = await Promise.all([
      getStats(banca.id, since ? { since } : {}),
      listTips(banca.id, {
        published: true,
        limit: 200,
        ...(since ? { since } : {}),
      }),
    ]);
    return { stats: novasStats, tips: novasTips };
  }, [banca.id, since]);

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
    void getStats(banca.id, since ? { since } : {})
      .then(setStats)
      .catch(() => {
        /* o número fica um instante velho; o próximo Atualizar corrige */
      });
  }

  const pendentes = tips.filter((t) => t.status === "pending").length;

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1.5">
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
          <span className="ml-1">
            <Ajuda>
              Recorta os números, o gráfico e a lista pela data em que a aposta
              foi publicada no grupo. &quot;Tudo&quot; é a banca desde o começo.
            </Ajuda>
          </span>
        </div>

        <div className="flex items-center gap-3">
          {pendentes > 0 && (
            <span className="flex items-center gap-1.5 text-xs text-muted">
              {formatUnits(emJogo(tips))} em jogo em {pendentes}{" "}
              {pendentes === 1 ? "aposta" : "apostas"}
              <Ajuda lado="esquerda">
                O que já foi para o grupo e ainda não tem resultado. Não entra no
                lucro nem no ROI enquanto não for marcado.
              </Ajuda>
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
          href={`/banca/${banca.slug}/tips`}
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
