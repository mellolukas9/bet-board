import Link from "next/link";

import { diaAtras } from "@/lib/bets";
import type { TipStatus } from "@/types/api";

/** Recortes de período da página pública. `dias: null` = a banca inteira. */
export const PERIODOS = [
  { chave: "tudo", rotulo: "Tudo", dias: null },
  { chave: "90d", rotulo: "90 dias", dias: 90 },
  { chave: "30d", rotulo: "30 dias", dias: 30 },
  { chave: "7d", rotulo: "7 dias", dias: 7 },
] as const;

export type PeriodoPublico = (typeof PERIODOS)[number]["chave"];

/** Recortes de resultado. Valem só para a lista — ver `FiltrosPublicos`. */
export const RESULTADOS = [
  { chave: "todas", rotulo: "Todas", status: undefined },
  { chave: "green", rotulo: "Ganhas", status: "green" },
  { chave: "red", rotulo: "Perdidas", status: "red" },
  { chave: "cashout", rotulo: "Encerradas", status: "cashout" },
  { chave: "pending", rotulo: "Em aberto", status: "pending" },
] as const;

export type ResultadoPublico = (typeof RESULTADOS)[number]["chave"];

/** O período pedido na URL, ou "tudo" quando ela não pede nada válido. */
export function periodoDe(valor: string | undefined): PeriodoPublico {
  return PERIODOS.find((p) => p.chave === valor)?.chave ?? "tudo";
}

export function resultadoDe(valor: string | undefined): ResultadoPublico {
  return RESULTADOS.find((r) => r.chave === valor)?.chave ?? "todas";
}

/**
 * Data inicial do período, no formato que a API espera (AAAA-MM-DD).
 *
 * O "hoje" é o de São Paulo, não o do servidor: esta página é renderizada em
 * UTC, onde o dia vira três horas antes.
 */
export function desde(periodo: PeriodoPublico): string | undefined {
  const dias = PERIODOS.find((p) => p.chave === periodo)?.dias;
  if (dias === null || dias === undefined) return undefined;
  return diaAtras(dias);
}

export function statusDe(resultado: ResultadoPublico): TipStatus | undefined {
  return RESULTADOS.find((r) => r.chave === resultado)?.status;
}

/**
 * Os filtros da página pública.
 *
 * São **links**, não botões: a página é renderizada no servidor (é um link
 * compartilhado em grupo, precisa abrir inteira sem esperar JavaScript), e o
 * filtro escolhido fica na URL — o assinante consegue mandar "olha os últimos
 * 30 dias" para alguém.
 *
 * O período recorta os números e a lista; o resultado recorta **só a lista**,
 * porque cartões de um resultado escolhido a dedo sempre diriam 100% de acerto.
 */
export function FiltrosPublicos({
  slug,
  periodo,
  resultado,
}: {
  slug: string;
  periodo: PeriodoPublico;
  resultado: ResultadoPublico;
}) {
  function href(novo: { periodo?: PeriodoPublico; resultado?: ResultadoPublico }) {
    const params = new URLSearchParams();
    const p = novo.periodo ?? periodo;
    const r = novo.resultado ?? resultado;
    if (p !== "tudo") params.set("periodo", p);
    if (r !== "todas") params.set("resultado", r);

    const query = params.toString();
    return `/b/${slug}${query ? `?${query}` : ""}`;
  }

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <Grupo rotulo="Período">
        {PERIODOS.map((p) => (
          <Opcao
            key={p.chave}
            href={href({ periodo: p.chave })}
            ativa={p.chave === periodo}
          >
            {p.rotulo}
          </Opcao>
        ))}
      </Grupo>

      <Grupo rotulo="Mostrar">
        {RESULTADOS.map((r) => (
          <Opcao
            key={r.chave}
            href={href({ resultado: r.chave })}
            ativa={r.chave === resultado}
          >
            {r.rotulo}
          </Opcao>
        ))}
      </Grupo>
    </div>
  );
}

function Grupo({
  rotulo,
  children,
}: {
  rotulo: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-[10px] font-semibold tracking-widest text-muted">
        {rotulo.toUpperCase()}
      </span>
      {children}
    </div>
  );
}

function Opcao({
  href,
  ativa,
  children,
}: {
  href: string;
  ativa: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      scroll={false}
      aria-current={ativa ? "true" : undefined}
      className={`rounded-lg px-3 py-1.5 text-sm transition ${
        ativa
          ? "bg-accent/20 font-medium text-white ring-1 ring-inset ring-accent/40"
          : "border border-line text-muted hover:bg-white/5 hover:text-white"
      }`}
    >
      {children}
    </Link>
  );
}
