import { Ajuda } from "@/components/Ajuda";
import { BankrollChart } from "@/components/BankrollChart";
import {
  FiltrosPublicos,
  type PeriodoPublico,
  type ResultadoPublico,
} from "@/components/FiltrosPublicos";
import {
  ROTULO_STATUS,
  chaveDoDia,
  formatDiaLongo,
  formatHora,
  formatOdd,
  formatPercent,
  formatUnits,
  formatUnitsSigned,
} from "@/lib/bets";
import type { BankrollPoint, PublicBankroll, PublicTip } from "@/types/api";

/**
 * A página que o tipster manda para os assinantes.
 *
 * Renderizada no servidor: é um link compartilhado, e precisa abrir inteira
 * para quem clica — sem esperar JavaScript, e com o texto disponível para
 * pré-visualização de link. Os filtros seguem essa regra: são links que trocam
 * a URL, não estado de cliente.
 *
 * Tudo em **unidades**. O backend nem envia os valores em reais nesta rota
 * (ver `app/schemas/public.py`), então não há como vazar daqui.
 */
export function PublicBankrollPage({
  banca,
  periodo,
  resultado,
}: {
  banca: PublicBankroll;
  periodo: PeriodoPublico;
  resultado: ResultadoPublico;
}) {
  const lucro = Number(banca.stats.profit_units);

  return (
    <main className="mx-auto w-full max-w-6xl px-5 py-8">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-green to-accent text-base font-bold text-[#07101f]">
              B
            </span>
            <h1 className="truncate text-2xl font-semibold tracking-tight">
              {banca.name}
            </h1>
          </div>
          {banca.description && (
            <p className="mt-2 max-w-prose text-sm text-muted">
              {banca.description}
            </p>
          )}
        </div>

        {banca.since && (
          <p className="text-xs text-muted">
            resultados desde{" "}
            {new Date(banca.since).toLocaleDateString("pt-BR", {
              month: "long",
              year: "numeric",
            })}
          </p>
        )}
      </header>

      <div className="space-y-4">
        <FiltrosPublicos
          slug={banca.slug}
          periodo={periodo}
          resultado={resultado}
        />

        <BankrollChart series={comoSerie(banca.stats.series)} altura="h-80 sm:h-96" />

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Cartao
            rotulo="APOSTAS"
            valor={String(banca.stats.bets)}
            ajuda="Quantas apostas foram enviadas ao grupo no período, contando as que ainda esperam resultado."
          />
          <Cartao
            rotulo="LUCRO"
            valor={formatUnitsSigned(lucro)}
            tom={lucro > 0 ? "green" : lucro < 0 ? "red" : "neutro"}
            ajuda="O resultado somado do período, em unidades. Uma aposta de 2u na cotação 1,85 devolve +1,7u se ganhar e -2u se perder."
          />
          <Cartao
            rotulo="ROI"
            valor={formatPercent(banca.stats.roi)}
            tom={Number(banca.stats.roi) > 0 ? "green" : "neutro"}
            ajuda="Retorno sobre o investimento: o lucro dividido por tudo o que foi apostado. 10% quer dizer que cada 1u apostada devolveu 0,1u de lucro."
          />
          <Cartao
            rotulo="ACERTO"
            valor={formatPercent(banca.stats.hit_rate)}
            ajuda="Quantas apostas resolvidas terminaram no positivo. Anuladas ficam de fora. Acerto alto com cotação baixa pode render menos que o contrário — por isso ele anda junto do ROI."
          />
        </div>

        <Lista tips={banca.tips} resultado={resultado} />
      </div>

      <footer className="mt-10 border-t border-line pt-5 text-center text-xs text-muted">
        <p>
          Valores em unidades (u) — 1u é a aposta padrão da banca.
          &quot;Encerrada&quot; é a aposta que saiu antes do fim do jogo, pelo
          valor que a casa ofereceu na hora. Resultados conferidos e publicados
          pelo administrador do grupo.
        </p>
        <p className="mt-2">Bet Board</p>
      </footer>
    </main>
  );
}

/** Adapta a série pública (sem reais) à do gráfico, que espera os dois. */
function comoSerie(series: PublicBankroll["stats"]["series"]): BankrollPoint[] {
  return series.map((p) => ({
    date: p.date,
    bets: p.bets,
    profit_units: p.profit_units,
    cumulative_units: p.cumulative_units,
    profit_brl: "0",
    cumulative_brl: "0",
  }));
}

function Cartao({
  rotulo,
  valor,
  ajuda,
  tom = "neutro",
}: {
  rotulo: string;
  valor: string;
  ajuda: string;
  tom?: "green" | "red" | "neutro";
}) {
  const cor =
    tom === "green" ? "text-green" : tom === "red" ? "text-red" : "text-white";

  return (
    <article className="relative rounded-xl border border-line bg-surface px-4 py-5 text-center">
      {/* o assinante do grupo é quem menos conhece o jargão: aqui o "?" vale
          ainda mais do que no painel de quem administra */}
      <span className="absolute right-3 top-3">
        <Ajuda lado="esquerda">{ajuda}</Ajuda>
      </span>
      <p className="text-[11px] font-semibold tracking-widest text-muted">
        {rotulo}
      </p>
      <p className={`mt-1.5 text-2xl font-bold tabular-nums ${cor}`}>{valor}</p>
    </article>
  );
}

function Lista({
  tips,
  resultado,
}: {
  tips: PublicTip[];
  resultado: ResultadoPublico;
}) {
  if (tips.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-line p-10 text-center text-sm text-muted">
        {resultado === "todas"
          ? "Nenhuma aposta publicada neste período."
          : "Nenhuma aposta com este resultado neste período."}
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {agruparPorDia(tips).map((dia) => (
        <section
          key={dia.chave}
          className="overflow-hidden rounded-xl border border-line bg-surface"
        >
          <div className="flex items-center justify-between gap-3 border-b border-line bg-surface-2 px-5 py-3">
            <span className="text-[15px] font-medium">
              {formatDiaLongo(dia.tips[0].created_at)}
            </span>
            <Saldo valor={dia.saldo} />
          </div>

          <div className="divide-y divide-line/70">
            {dia.tips.map((tip) => (
              <Linha key={tip.id} tip={tip} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function Linha({ tip }: { tip: PublicTip }) {
  const resultado = lucroDe(tip);
  // encerrada não tem cor própria: quem diz se ela foi boa ou ruim é o saldo
  const cor =
    tip.status === "green" || (tip.status === "cashout" && resultado > 0)
      ? "bg-green/15 text-green"
      : tip.status === "red" || (tip.status === "cashout" && resultado < 0)
        ? "bg-red/15 text-red"
        : "bg-white/5 text-muted";

  return (
    <article className="flex items-stretch gap-3">
      <div className="min-w-0 flex-1 px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded bg-surface-3 px-2 py-0.5 font-mono text-xs text-foreground/80">
            {formatHora(tip.created_at)}
          </span>
          <span
            title={tip.market ?? undefined}
            className="max-w-[28rem] truncate rounded bg-accent/15 px-2 py-0.5 text-xs text-accent"
          >
            {tip.market ?? "—"}
          </span>
        </div>
        <p className="mt-2 truncate text-base font-medium">
          {tip.event ?? "—"}
          {tip.source && (
            <span className="ml-2 text-sm font-normal text-muted">
              {tip.source}
            </span>
          )}
        </p>
      </div>

      <div className="hidden items-center gap-7 py-4 pr-2 text-right sm:flex">
        <Coluna rotulo="Cotação" valor={formatOdd(tip.odd)} />
        <Coluna
          rotulo="Valor"
          valor={tip.stake_units ? formatUnits(tip.stake_units) : "—"}
        />
        <Coluna
          rotulo="Lucro"
          valor={
            tip.status === "pending" ? "—" : formatUnitsSigned(resultado)
          }
          tom={resultado > 0 ? "green" : resultado < 0 ? "red" : "neutro"}
        />
      </div>

      <span
        className={`grid w-16 shrink-0 place-items-center border-l border-line text-xs font-medium ${cor}`}
      >
        <span style={{ writingMode: "vertical-rl", rotate: "180deg" }}>
          {ROTULO_STATUS[tip.status]}
        </span>
      </span>
    </article>
  );
}

function Coluna({
  rotulo,
  valor,
  tom = "neutro",
}: {
  rotulo: string;
  valor: string;
  tom?: "green" | "red" | "neutro";
}) {
  const cor =
    tom === "green" ? "text-green" : tom === "red" ? "text-red" : "text-white";

  return (
    <div className="w-24">
      <p className={`text-base font-semibold tabular-nums ${cor}`}>{valor}</p>
      <p className="text-[11px] text-muted">{rotulo}</p>
    </div>
  );
}

function Saldo({ valor }: { valor: number }) {
  const cor =
    valor > 0
      ? "bg-green/15 text-green"
      : valor < 0
        ? "bg-red/15 text-red"
        : "bg-white/5 text-muted";

  return (
    <span
      className={`shrink-0 rounded-md px-2.5 py-1 text-sm font-semibold tabular-nums ${cor}`}
    >
      {formatUnitsSigned(valor)}
    </span>
  );
}

/**
 * Lucro em unidades.
 *
 * A mesma fórmula do backend, repetida aqui pelo mesmo motivo do painel: é uma
 * conta por linha, e os agregados (que é o que precisa bater) já vêm prontos.
 *
 * No encerramento antecipado o backend já manda o que voltou em unidades — o
 * valor em reais, de onde sai essa proporção, não passa por esta rota.
 */
function lucroDe(tip: PublicTip): number {
  const stake = Number(tip.stake_units ?? 0);
  if (tip.status === "green") return stake * (Number(tip.odd ?? 0) - 1);
  if (tip.status === "red") return -stake;
  if (tip.status === "cashout") return Number(tip.cashout_units ?? 0) - stake;
  return 0;
}

function agruparPorDia(tips: PublicTip[]) {
  const dias = new Map<string, { chave: string; tips: PublicTip[]; saldo: number }>();

  for (const tip of tips) {
    const chave = chaveDoDia(tip.created_at);
    let dia = dias.get(chave);
    if (!dia) {
      dia = { chave, tips: [], saldo: 0 };
      dias.set(chave, dia);
    }
    dia.tips.push(tip);
    dia.saldo += lucroDe(tip);
  }

  return [...dias.values()];
}
