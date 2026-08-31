"use client";

import { useState } from "react";

import { ApiError, setTipResult } from "@/lib/api";
import {
  ROTULO_STATUS,
  chaveDoDia,
  chaveDoMes,
  formatDiaLongo,
  formatHora,
  formatMesLongo,
  formatMoney,
  formatOdd,
  formatUnits,
  formatUnitsSigned,
  lucro,
  retorno,
  stakeUnits,
} from "@/lib/bets";
import type { TipRead, TipStatus } from "@/types/api";

/**
 * A lista de apostas do painel, agrupada por mês e por dia — cada grupo com o
 * seu saldo à direita, como num extrato.
 *
 * É aqui que o admin **diz se a tip deu green ou red**: não há API esportiva
 * nesta fase, o resultado é conferido a olho e marcado no botão.
 */
export function BetList({
  tips,
  onChange,
  carregando,
}: {
  tips: TipRead[];
  onChange: (tip: TipRead) => void;
  carregando: boolean;
}) {
  if (carregando && tips.length === 0) {
    return <Esqueleto />;
  }

  if (tips.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-line p-10 text-center text-sm text-muted">
        Nenhuma aposta ainda. Suba um print na aba <strong>Tips</strong> para
        começar.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      {agrupar(tips).map((mes) => (
        <section key={mes.chave}>
          <CabecalhoDeGrupo
            titulo={formatMesLongo(mes.tips[0].created_at)}
            saldo={mes.saldo}
            destaque
          />

          <div className="mt-2 space-y-3">
            {mes.dias.map((dia) => (
              <div
                key={dia.chave}
                className="overflow-hidden rounded-xl border border-line bg-surface"
              >
                <CabecalhoDeGrupo
                  titulo={formatDiaLongo(dia.tips[0].created_at)}
                  saldo={dia.saldo}
                />
                <div className="divide-y divide-line/70">
                  {dia.tips.map((tip) => (
                    <BetRow key={tip.id} tip={tip} onChange={onChange} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function CabecalhoDeGrupo({
  titulo,
  saldo,
  destaque = false,
}: {
  titulo: string;
  saldo: number;
  destaque?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-between gap-3 px-4 py-2.5 ${
        destaque
          ? "rounded-xl border border-accent/30 bg-accent/10"
          : "border-b border-line bg-surface-2"
      }`}
    >
      <span
        className={`truncate text-sm ${destaque ? "font-semibold text-white" : "font-medium text-foreground/90"}`}
      >
        {titulo}
      </span>
      <SaldoDoGrupo valor={saldo} />
    </div>
  );
}

function SaldoDoGrupo({ valor }: { valor: number }) {
  const cor =
    valor > 0
      ? "bg-green/15 text-green"
      : valor < 0
        ? "bg-red/15 text-red"
        : "bg-white/5 text-muted";

  return (
    <span
      className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold tabular-nums ${cor}`}
    >
      {formatUnitsSigned(valor)}
    </span>
  );
}

/** Uma aposta na lista, com a marcação de resultado à direita. */
function BetRow({
  tip,
  onChange,
}: {
  tip: TipRead;
  onChange: (tip: TipRead) => void;
}) {
  const [salvando, setSalvando] = useState<TipStatus | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [desfazendo, setDesfazendo] = useState(false);

  const resultado = lucro(tip);
  const semUnidades = tip.stake_units === null;

  async function marcar(status: TipStatus) {
    setSalvando(status);
    setErro(null);
    try {
      onChange(await setTipResult(tip.id, status));
      setDesfazendo(false);
    } catch (e) {
      setErro(
        e instanceof ApiError || e instanceof Error
          ? e.message
          : "Falha ao marcar o resultado",
      );
    } finally {
      setSalvando(null);
    }
  }

  return (
    <div>
      <article className="flex items-stretch gap-3 bg-surface transition hover:bg-surface-2/60">
      <div className="min-w-0 flex-1 py-3 pl-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[11px] text-foreground/80">
            {formatHora(tip.created_at)}
          </span>
          {/* mercado de aposta múltipla vem com a descrição inteira; sem o
              truncate ele quebra em duas linhas e desalinha a lista */}
          <span
            title={tip.market ?? undefined}
            className="max-w-[24rem] truncate rounded bg-accent/15 px-1.5 py-0.5 text-[11px] text-accent"
          >
            {tip.market ?? "Sem mercado"}
          </span>
          {tip.needs_review && (
            <span className="rounded bg-amber/15 px-1.5 py-0.5 text-[11px] text-amber">
              Em revisão
            </span>
          )}
        </div>

        <p className="mt-1.5 truncate text-sm font-medium">
          {tip.event ?? "Evento não lido"}
          {tip.source && (
            <span className="ml-2 text-xs font-normal text-muted">
              {tip.source}
            </span>
          )}
        </p>
      </div>

      <div className="hidden items-center gap-5 py-3 pr-1 text-right sm:flex">
        <Coluna rotulo="Cotação" valor={formatOdd(tip.odd)} />
        <Coluna
          rotulo="Valor"
          valor={semUnidades ? "—" : formatUnits(tip.stake_units)}
          titulo={tip.stake ? formatMoney(tip.stake) : undefined}
        />
        <Coluna
          rotulo="Ganho"
          valor={formatUnits(retorno(tip))}
          tom={tip.status === "green" ? "green" : tip.status === "red" ? "red" : "neutro"}
        />
        <Coluna
          rotulo="Lucro"
          valor={formatUnitsSigned(resultado)}
          tom={resultado > 0 ? "green" : resultado < 0 ? "red" : "neutro"}
        />
      </div>

      <FaixaDeResultado
        tip={tip}
        salvando={salvando}
        desfazendo={desfazendo}
        onDesfazer={() => setDesfazendo((v) => !v)}
        onMarcar={(status) => void marcar(status)}
      />
      </article>

      {erro && (
        <p role="alert" className="border-t border-red/20 bg-red/10 px-4 py-2 text-xs text-red">
          {erro}
        </p>
      )}
    </div>
  );
}

function Coluna({
  rotulo,
  valor,
  tom = "neutro",
  titulo,
}: {
  rotulo: string;
  valor: string;
  tom?: "green" | "red" | "neutro";
  titulo?: string;
}) {
  const cor =
    tom === "green" ? "text-green" : tom === "red" ? "text-red" : "text-white";

  return (
    <div className="w-20" title={titulo}>
      <p className={`text-sm font-semibold tabular-nums ${cor}`}>{valor}</p>
      <p className="text-[10px] text-muted">{rotulo}</p>
    </div>
  );
}

/**
 * A faixa da direita: mostra o resultado quando já há um, e vira os botões de
 * marcar quando a tip está pendente.
 *
 * Marcar é um clique; **desmarcar** pede dois (clicar na faixa e confirmar) —
 * desfazer um resultado mexe no lucro consolidado, não é para escapar do dedo.
 */
function FaixaDeResultado({
  tip,
  salvando,
  desfazendo,
  onDesfazer,
  onMarcar,
}: {
  tip: TipRead;
  salvando: TipStatus | null;
  desfazendo: boolean;
  onDesfazer: () => void;
  onMarcar: (status: TipStatus) => void;
}) {
  if (tip.status === "pending") {
    return (
      <div className="flex w-14 shrink-0 flex-col border-l border-line">
        <BotaoDeResultado
          rotulo="Green"
          simbolo="✓"
          classe="text-green hover:bg-green/20"
          ocupado={salvando === "green"}
          onClick={() => onMarcar("green")}
        />
        <BotaoDeResultado
          rotulo="Red"
          simbolo="✕"
          classe="text-red hover:bg-red/20"
          ocupado={salvando === "red"}
          onClick={() => onMarcar("red")}
        />
        <BotaoDeResultado
          rotulo="Anulada (stake devolvido)"
          simbolo="∅"
          classe="text-muted hover:bg-white/10"
          ocupado={salvando === "void"}
          onClick={() => onMarcar("void")}
        />
      </div>
    );
  }

  const cor =
    tip.status === "green"
      ? "bg-green/15 text-green"
      : tip.status === "red"
        ? "bg-red/15 text-red"
        : "bg-white/5 text-muted";

  if (desfazendo) {
    return (
      <div className="flex w-14 shrink-0 flex-col border-l border-line">
        <BotaoDeResultado
          rotulo="Desfazer: volta para pendente"
          simbolo="↺"
          classe="text-amber hover:bg-amber/20"
          ocupado={salvando === "pending"}
          onClick={() => onMarcar("pending")}
        />
        <BotaoDeResultado
          rotulo="Cancelar"
          simbolo="✕"
          classe="text-muted hover:bg-white/10"
          ocupado={false}
          onClick={onDesfazer}
        />
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onDesfazer}
      title={`${ROTULO_STATUS[tip.status]} — clique para desfazer`}
      className={`w-14 shrink-0 border-l border-line text-[11px] font-medium transition hover:brightness-125 ${cor}`}
    >
      <span
        className="inline-block py-2"
        style={{ writingMode: "vertical-rl", rotate: "180deg" }}
      >
        {ROTULO_STATUS[tip.status]}
      </span>
    </button>
  );
}

function BotaoDeResultado({
  rotulo,
  simbolo,
  classe,
  ocupado,
  onClick,
}: {
  rotulo: string;
  simbolo: string;
  classe: string;
  ocupado: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={ocupado}
      title={rotulo}
      aria-label={rotulo}
      className={`flex-1 text-sm transition disabled:opacity-40 ${classe}`}
    >
      {ocupado ? "…" : simbolo}
    </button>
  );
}

function Esqueleto() {
  return (
    <div className="space-y-2">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="h-16 animate-pulse rounded-xl border border-line bg-surface"
        />
      ))}
    </div>
  );
}

// --- agrupamento --------------------------------------------------------------

type Grupo = { chave: string; tips: TipRead[]; saldo: number };
type Mes = Grupo & { dias: Grupo[] };

/**
 * Mês → dia, na ordem em que a lista chega (mais recentes primeiro), com o
 * saldo de cada grupo em unidades.
 */
function agrupar(tips: TipRead[]): Mes[] {
  const meses = new Map<string, Mes>();

  for (const tip of tips) {
    const chaveMes = chaveDoMes(tip.created_at);
    let mes = meses.get(chaveMes);
    if (!mes) {
      mes = { chave: chaveMes, tips: [], saldo: 0, dias: [] };
      meses.set(chaveMes, mes);
    }

    const chaveDia = chaveDoDia(tip.created_at);
    let dia = mes.dias.find((d) => d.chave === chaveDia);
    if (!dia) {
      dia = { chave: chaveDia, tips: [], saldo: 0 };
      mes.dias.push(dia);
    }

    const resultado = lucro(tip);
    mes.tips.push(tip);
    mes.saldo += resultado;
    dia.tips.push(tip);
    dia.saldo += resultado;
  }

  return [...meses.values()];
}

/** Soma de unidades das tips (usado pelo painel no resumo do período). */
export function saldoDe(tips: TipRead[]): number {
  return tips.reduce((total, tip) => total + lucro(tip), 0);
}

/** Unidades ainda em jogo — o que está apostado e sem resultado. */
export function emJogo(tips: TipRead[]): number {
  return tips
    .filter((tip) => tip.status === "pending")
    .reduce((total, tip) => total + stakeUnits(tip), 0);
}
