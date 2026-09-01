"use client";

import { Ajuda } from "@/components/Ajuda";
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
 *
 * Cada um traz o seu "?": ROI, unidade e taxa de acerto são jargão de quem já
 * opera banca, e o painel é usado por quem está começando.
 */
export function StatCards({ stats }: { stats: BankrollStats | null }) {
  const lucro = Number(stats?.profit_units ?? 0);
  const roi = Number(stats?.roi ?? 0);

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Card
        rotulo="APOSTAS"
        valor={String(stats?.bets ?? 0)}
        ajuda="Quantas tips foram publicadas no grupo no período — incluindo as que ainda esperam resultado. O que está na fila de revisão não entra: ninguém apostou nele."
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
        ajuda="Quanto a banca ganhou (ou perdeu) no período, em unidades. Uma tip de 2u na odd 1,85 devolve +1,7u se ganhar e -2u se perder. Anulada devolve o stake e vale 0."
        rodape={stats ? formatMoney(stats.profit_brl) : undefined}
      />
      <Card
        rotulo="ROI"
        valor={formatPercent(roi)}
        tom={roi > 0 ? "green" : roi < 0 ? "red" : "neutro"}
        ajuda="Retorno sobre o investimento: o lucro dividido por tudo o que foi apostado. 10% quer dizer que cada 1u apostada devolveu 0,1u de lucro. É o número que compara duas bancas de tamanhos diferentes."
        rodape={stats ? `${formatUnits(stats.staked_units)} apostadas` : undefined}
      />
      <Card
        rotulo="ACERTO"
        valor={formatPercent(stats?.hit_rate ?? 0)}
        ajuda="Quantas apostas resolvidas terminaram no positivo. Encerrada com lucro conta como acerto; anulada fica de fora. Acerto alto com odd baixa pode dar menos lucro que o contrário — por isso ele anda junto do ROI."
        rodape={
          stats
            ? `${stats.green} green · ${stats.red} red${
                stats.cashout > 0 ? ` · ${stats.cashout} encerrada${stats.cashout > 1 ? "s" : ""}` : ""
              }`
            : undefined
        }
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
      <span className="absolute right-3 top-3">
        <Ajuda lado="esquerda">{ajuda}</Ajuda>
      </span>
      <p className="text-[10px] font-semibold tracking-widest text-muted">
        {rotulo}
      </p>
      <p className={`mt-1.5 text-2xl font-bold tabular-nums ${cor}`}>{valor}</p>
      {rodape && <p className="mt-1 text-[11px] text-muted">{rodape}</p>}
    </article>
  );
}
