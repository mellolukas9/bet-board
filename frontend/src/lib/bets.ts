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

/**
 * O fuso do board.
 *
 * A hora e o dia **nunca** saem do relógio de quem abre a página: a página
 * pública é renderizada no servidor (`force-dynamic`), e o servidor roda em
 * UTC — sem fixar o fuso, uma tip das 19h aparece como 22h para o assinante.
 */
export const FUSO = "America/Sao_Paulo";

export function formatHora(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: FUSO,
  });
}

/** "Sábado 29" — o cabeçalho de cada dia da lista. */
export function formatDiaLongo(iso: string): string {
  const data = new Date(iso);
  const dia = data.toLocaleDateString("pt-BR", { weekday: "long", timeZone: FUSO });
  const numero = data.toLocaleDateString("pt-BR", { day: "numeric", timeZone: FUSO });
  return `${dia.charAt(0).toUpperCase()}${dia.slice(1)} ${numero}`;
}

/** "Agosto de 2026" — o cabeçalho de cada mês. */
export function formatMesLongo(iso: string): string {
  const texto = new Date(iso).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
    timeZone: FUSO,
  });
  return `${texto.charAt(0).toUpperCase()}${texto.slice(1)}`;
}

/** Chave de agrupamento estável ("2026-08-29"), no fuso de São Paulo. */
export function chaveDoDia(iso: string): string {
  // "en-CA" já formata como AAAA-MM-DD — é a saída que o agrupamento espera.
  return new Date(iso).toLocaleDateString("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: FUSO,
  });
}

export function chaveDoMes(iso: string): string {
  return chaveDoDia(iso).slice(0, 7);
}

/** Hoje em São Paulo, como "AAAA-MM-DD" — a base dos filtros por período. */
function hojeEmSaoPaulo(): string {
  return chaveDoDia(new Date().toISOString());
}

/** "AAAA-MM-DD" de `dias` atrás em São Paulo, no formato que a API espera. */
export function diaAtras(dias: number): string {
  const [ano, mes, dia] = hojeEmSaoPaulo().split("-").map(Number);
  // Meio-dia UTC: longe das bordas, o -dias nunca escorrega de dia.
  const data = new Date(Date.UTC(ano, mes - 1, dia, 12));
  data.setUTCDate(data.getUTCDate() - dias);
  return data.toISOString().slice(0, 10);
}
