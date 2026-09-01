/**
 * Números derivados de uma tip e formatação em pt-BR.
 *
 * A mesma fórmula do backend (`app/services/stats.py`), repetida aqui para a
 * linha da lista: pedir o cálculo de cada linha ao servidor seria uma ida à
 * rede por aposta. Os agregados (cartões e gráfico) **continuam vindo do
 * backend** — é ele quem enxerga tudo, não só a página carregada.
 */

import type { TipRead, TipStatus } from "@/types/api";

/** Valor apostado em unidades; 0 quando o admin ainda não informou. */
export function stakeUnits(tip: TipRead): number {
  return Number(tip.stake_units ?? 0);
}

export function odd(tip: TipRead): number {
  return Number(tip.odd ?? 0);
}

/** O que voltou do encerramento antecipado, em unidades. */
export function cashoutUnits(tip: TipRead): number {
  return Number(tip.cashout_units ?? 0);
}

/**
 * "Ganho": o retorno bruto. stake x odd no green, nada no red.
 *
 * No encerramento quem diz é a casa: voltou o valor do cash out.
 */
export function retorno(tip: TipRead): number {
  if (tip.status === "green") return stakeUnits(tip) * odd(tip);
  if (tip.status === "void") return stakeUnits(tip);
  if (tip.status === "cashout") return cashoutUnits(tip);
  return 0;
}

/**
 * "Lucro": o que sobra. `stake x (odd - 1)` no green, `-stake` no red.
 *
 * O encerramento é a diferença entre o que voltou e o que foi apostado — por
 * isso ele pode dar lucro **ou** prejuízo, sem ser green nem red.
 */
export function lucro(tip: TipRead): number {
  if (tip.status === "green") return stakeUnits(tip) * (odd(tip) - 1);
  if (tip.status === "red") return -stakeUnits(tip);
  if (tip.status === "cashout") return cashoutUnits(tip) - stakeUnits(tip);
  return 0;
}

export const ROTULO_STATUS: Record<TipStatus, string> = {
  pending: "Pendente",
  green: "Ganha",
  red: "Perdida",
  void: "Anulada",
  cashout: "Encerrada",
};

// --- formatação ---------------------------------------------------------------

const numero = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Unidades sem casa decimal à toa: "2u", "2,5u". */
export function formatUnits(value: number | string | null): string {
  const n = Number(value ?? 0);
  const texto = Number.isInteger(n)
    ? String(n)
    : n.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  return `${texto}u`;
}

/** Unidades com sinal explícito — o lucro precisa mostrar o "+". */
export function formatUnitsSigned(value: number | string | null): string {
  const n = Number(value ?? 0);
  return `${n > 0 ? "+" : ""}${formatUnits(n)}`;
}

export function formatMoney(value: number | string | null): string {
  return `R$ ${numero.format(Number(value ?? 0))}`;
}

/** Odd no padrão da casa: 3 casas, vírgula decimal ("1,850"). */
export function formatOdd(value: string | null): string {
  if (value === null) return "—";
  return Number(value).toLocaleString("pt-BR", {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  });
}

export function formatPercent(value: number | string | null): string {
  return `${numero.format(Number(value ?? 0))}%`;
}

export function formatHora(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** "Sábado 29" — o cabeçalho de cada dia da lista. */
export function formatDiaLongo(iso: string): string {
  const data = new Date(iso);
  const dia = data.toLocaleDateString("pt-BR", { weekday: "long" });
  return `${dia.charAt(0).toUpperCase()}${dia.slice(1)} ${data.getDate()}`;
}

/** "Agosto de 2026" — o cabeçalho de cada mês. */
export function formatMesLongo(iso: string): string {
  const texto = new Date(iso).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  });
  return `${texto.charAt(0).toUpperCase()}${texto.slice(1)}`;
}

/** Chave de agrupamento estável, no fuso local (não em UTC). */
export function chaveDoDia(iso: string): string {
  const d = new Date(iso);
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  return `${d.getFullYear()}-${mes}-${String(d.getDate()).padStart(2, "0")}`;
}

export function chaveDoMes(iso: string): string {
  return chaveDoDia(iso).slice(0, 7);
}
