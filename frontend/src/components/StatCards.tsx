"use client";

import {
  formatMoney,
  formatPercent,
  formatUnits,
  formatUnitsSigned,
} from "@/lib/bets";
import type { BankrollStats } from "@/types/api";

/**
 * Os quatro números do topo do painel.
 *
 * Vêm do `GET /stats`, não da lista carregada na tela: a lista é paginada e os
 * cartões precisam enxergar a banca inteira.
 */
export function StatCards({ stats }: { stats: BankrollStats | null }) {
  const lucro = Number(stats?.profit_units ?? 0);
  const roi = Number(stats?.roi ?? 0);

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Card
        rotulo="APOSTAS"
        valor={String(stats?.bets ?? 0)}
        ajuda="Total de tips no board, incluindo as que ainda aguardam resultado."
        rodape={
          stats
            ? `${stats.settled} resolvidas · ${stats.pending} pendentes`
            : undefined
        }
      />
      <Card
        rotulo="LUCRO"
        valor={formatUnitsSigned(lucro)}
        tom={lucro > 0 ? "green" : lucro < 0 ? "red" : "neutro"}
        ajuda="Soma do lucro das tips resolvidas, em unidades. Anuladas devolvem o stake e valem 0."
        rodape={stats ? formatMoney(stats.profit_brl) : undefined}
      />
      <Card
        rotulo="ROI"
        valor={formatPercent(roi)}
        tom={roi > 0 ? "green" : roi < 0 ? "red" : "neutro"}
        ajuda="Lucro dividido pelo total apostado, em unidades."
        rodape={stats ? `${formatUnits(stats.staked_units)} apostadas` : undefined}
      />
      <Card
        rotulo="ACERTO"
        valor={formatPercent(stats?.hit_rate ?? 0)}
        ajuda="Greens sobre o total de tips resolvidas. Anuladas ficam de fora."
        rodape={stats ? `${stats.green} green · ${stats.red} red` : undefined}
      />
    </div>
  );
}

function Card({
  rotulo,
  valor,
  ajuda,
  rodape,
  tom = "neutro",
}: {
  rotulo: string;
  valor: string;
  ajuda: string;
  rodape?: string;
  tom?: "green" | "red" | "neutro";
}) {
  const cor =
    tom === "green" ? "text-green" : tom === "red" ? "text-red" : "text-white";

  return (
    <article className="relative rounded-xl border border-line bg-surface px-4 py-4 text-center">
      <span
        title={ajuda}
        aria-label={ajuda}
        className="absolute right-3 top-3 grid size-4 cursor-help place-items-center rounded-full border border-line text-[9px] text-muted"
      >
        ?
      </span>
      <p className="text-[10px] font-semibold tracking-widest text-muted">
        {rotulo}
      </p>
      <p className={`mt-1.5 text-2xl font-bold tabular-nums ${cor}`}>{valor}</p>
      {rodape && <p className="mt-1 text-[11px] text-muted">{rodape}</p>}
    </article>
  );
}
