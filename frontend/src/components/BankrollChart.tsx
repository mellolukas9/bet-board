"use client";

import { Ajuda } from "@/components/Ajuda";
import { formatUnitsSigned } from "@/lib/bets";
import type { BankrollPoint } from "@/types/api";

/** Sistema de coordenadas interno. A largura real vem do CSS. */
const VB_W = 1000;
const VB_H = 320;
const LINHAS = 5;

/**
 * Evolução da banca, em unidades acumuladas.
 *
 * SVG na mão em vez de uma biblioteca de gráficos: é uma curva só, e trocar
 * ~100 linhas por 40 KB de dependência (mais o wrapper de React) não se paga.
 *
 * O `viewBox` é esticado (`preserveAspectRatio="none"`) para o gráfico ocupar a
 * largura disponível; os traços usam `vector-effect="non-scaling-stroke"` para
 * não engordarem junto, e os rótulos do eixo Y ficam em HTML por fora — texto
 * dentro de um SVG esticado sairia achatado.
 */
export function BankrollChart({
  series,
  carregando = false,
  altura = "h-56",
}: {
  series: BankrollPoint[];
  carregando?: boolean;
  /** Classe de altura do Tailwind. A página pública pede um gráfico maior. */
  altura?: string;
}) {
  // O ponto zero é a banca antes da primeira aposta: sem ele a curva começa já
  // no primeiro resultado e some a origem do ganho.
  const valores = [0, ...series.map((p) => Number(p.cumulative_units))];

  // A escala é arredondada para um passo "redondo" (1, 2, 5, 10, 20, 50…): o
  // eixo precisa dizer "+50u", não "+47,48u". O zero sempre entra, senão a
  // curva perde a referência de lucro contra prejuízo.
  const passo = passoBonito(
    Math.max(...valores, 0) - Math.min(...valores, 0),
    LINHAS,
  );
  const topo = Math.ceil(Math.max(...valores, 0) / passo) * passo;
  const base = Math.floor(Math.min(...valores, 0) / passo) * passo;
  const alcance = topo - base || passo;

  const x = (i: number) =>
    valores.length < 2 ? VB_W : (i / (valores.length - 1)) * VB_W;
  const y = (v: number) => VB_H - ((v - base) / alcance) * VB_H;

  const linha = valores.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const area = `M0,${VB_H} L${valores
    .map((v, i) => `${x(i)},${y(v)}`)
    .join(" L")} L${VB_W},${VB_H} Z`;

  const positivo = valores[valores.length - 1] >= 0;
  const cor = positivo ? "var(--green)" : "var(--red)";

  const rotulos = Array.from(
    { length: Math.round(alcance / passo) + 1 },
    (_, i) => topo - passo * i,
  );

  return (
    <section className="rounded-xl border border-line bg-surface p-4">
      <header className="mb-3 flex items-baseline justify-between">
        <h2 className="flex items-center gap-1.5 text-sm font-medium">
          Evolução da banca
          <Ajuda>
            O lucro somado dia a dia, em unidades. A linha só se mexe quando uma
            aposta é resolvida — e é a data do resultado que conta, não a do
            envio. Acima da linha tracejada a banca está no lucro.
          </Ajuda>
        </h2>
        <span className="text-xs text-muted">
          {series.length === 0
            ? "sem resultados ainda"
            : `${series.length} ${series.length === 1 ? "dia" : "dias"} com resultado`}
        </span>
      </header>

      <div className="flex gap-3">
        <div className="flex w-14 shrink-0 flex-col justify-between py-px text-right text-[10px] tabular-nums text-muted">
          {rotulos.map((valor, i) => (
            <span key={i}>{formatUnitsSigned(round(valor))}</span>
          ))}
        </div>

        <div className={`relative min-w-0 flex-1 ${altura}`}>
          <svg
            viewBox={`0 0 ${VB_W} ${VB_H}`}
            preserveAspectRatio="none"
            className="size-full overflow-visible"
            role="img"
            aria-label={
              series.length === 0
                ? "Banca sem resultados"
                : `Banca em ${formatUnitsSigned(valores[valores.length - 1])} após ${series.length} dias`
            }
          >
            <defs>
              <linearGradient id="preenchimento" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={cor} stopOpacity="0.28" />
                <stop offset="100%" stopColor={cor} stopOpacity="0" />
              </linearGradient>
            </defs>

            {rotulos.map((valor, i) => (
              <line
                key={i}
                x1="0"
                x2={VB_W}
                y1={y(valor)}
                y2={y(valor)}
                stroke="var(--border)"
                strokeWidth="1"
                vectorEffect="non-scaling-stroke"
              />
            ))}

            {/* o zero é a única linha que importa ler de relance */}
            <line
              x1="0"
              x2={VB_W}
              y1={y(0)}
              y2={y(0)}
              stroke="var(--border-strong)"
              strokeWidth="1"
              strokeDasharray="4 4"
              vectorEffect="non-scaling-stroke"
            />

            {!carregando && valores.length > 1 && (
              <>
                <path d={area} fill="url(#preenchimento)" />
                <polyline
                  points={linha}
                  fill="none"
                  stroke={cor}
                  strokeWidth="2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                />
              </>
            )}

            {/* faixas invisíveis só para o tooltip nativo de cada dia */}
            {series.map((ponto, i) => (
              <rect
                key={ponto.date}
                x={x(i + 1) - VB_W / valores.length / 2}
                y="0"
                width={VB_W / valores.length}
                height={VB_H}
                fill="transparent"
              >
                <title>
                  {`${formatarData(ponto.date)} — banca ${formatUnitsSigned(
                    ponto.cumulative_units,
                  )} (dia: ${formatUnitsSigned(ponto.profit_units)}, ${ponto.bets} ${
                    ponto.bets === 1 ? "aposta" : "apostas"
                  })`}
                </title>
              </rect>
            ))}
          </svg>

          {series.length === 0 && !carregando && (
            <p className="absolute inset-0 grid place-items-center text-sm text-muted">
              Marque o resultado das tips para a curva aparecer.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

/**
 * Passo de grade legível para o alcance dado.
 *
 * Sobe o valor bruto (alcance / divisões) para o próximo 1, 2, 5 ou 10 da mesma
 * ordem de grandeza — é o que faz o eixo mostrar 10u, 20u, 50u em vez de 8,33u.
 */
function passoBonito(alcance: number, divisoes: number): number {
  // banca zerada: uma escala de -1u a +1u, para a linha do zero ter onde ficar
  const bruto = Math.max(alcance, 1) / divisoes;
  const magnitude = 10 ** Math.floor(Math.log10(bruto));
  const normalizado = bruto / magnitude;
  const passo = normalizado <= 1 ? 1 : normalizado <= 2 ? 2 : normalizado <= 5 ? 5 : 10;
  return passo * magnitude;
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}

/** A série vem como "2026-08-29"; `new Date` puro leria isso como UTC. */
function formatarData(iso: string): string {
  const [ano, mes, dia] = iso.split("-").map(Number);
  return new Date(ano, mes - 1, dia).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
  });
}
