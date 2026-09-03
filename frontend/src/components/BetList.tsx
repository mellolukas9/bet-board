"use client";

import { useState } from "react";

import { Ajuda } from "@/components/Ajuda";
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
 * É aqui que o admin **diz como a tip terminou**: não há API esportiva nesta
 * fase, o resultado é conferido a olho e marcado no botão. São quatro saídas —
 * ganha, perdida, anulada e encerrada antes do fim (o cash out da casa).
 *
 * A lista recebe só tip **publicada**. Aposta que não chegou ao grupo não tem
 * resultado a confirmar, e o backend recusa marcá-la (409).
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
        Nenhuma aposta publicada ainda. A banca mostra o que foi para o grupo —
        suba o print e publique na aba <strong>Tips</strong>.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-end gap-1.5 text-xs text-muted">
        Como marcar o resultado
        <Ajuda lado="esquerda">
          Na faixa à direita de cada aposta: ✓ ganha, ✕ perdida, ∅ anulada (a
          casa devolveu o valor) e ⇄ encerrada antes do fim, quando você tirou o
          dinheiro no meio do jogo. Já marcada, clique na faixa para desfazer.
        </Ajuda>
      </div>

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
  const [encerrando, setEncerrando] = useState(false);

  const resultado = lucro(tip);
  const semUnidades = tip.stake_units === null;

  async function marcar(status: TipStatus, cashoutAmount?: string) {
    setSalvando(status);
    setErro(null);
    try {
      onChange(await setTipResult(tip.id, status, { cashoutAmount }));
      setDesfazendo(false);
      setEncerrando(false);
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
            className="max-w-full truncate rounded bg-accent/15 px-1.5 py-0.5 text-[11px] text-accent sm:max-w-[24rem]"
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

        {/* No celular as colunas da direita não cabem, e sem elas a lista virava
            só evento e mercado — a aposta sem número nenhum. Aqui eles voltam
            em uma linha, rotulados para não virar adivinhação. O ganho fica de
            fora: em quatro dedos de tela, cotação, valor e lucro são o que se
            confere de relance. */}
        <p className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted tabular-nums sm:hidden">
          <span>
            cotação <b className="font-semibold text-white">{formatOdd(tip.odd)}</b>
          </span>
          <span>
            valor{" "}
            <b className="font-semibold text-white">
              {semUnidades ? "—" : formatUnits(tip.stake_units)}
            </b>
          </span>
          {tip.status !== "pending" && (
            <span>
              lucro{" "}
              <b
                className={`font-semibold ${
                  resultado > 0
                    ? "text-green"
                    : resultado < 0
                      ? "text-red"
                      : "text-white"
                }`}
              >
                {formatUnitsSigned(resultado)}
              </b>
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
        onMarcar={(status) => {
          if (status === "cashout") {
            setEncerrando(true);
            return;
          }
          void marcar(status);
        }}
      />
      </article>

      {encerrando && (
        <FormularioDeEncerramento
          tip={tip}
          salvando={salvando === "cashout"}
          onCancelar={() => setEncerrando(false)}
          onConfirmar={(valor) => void marcar("cashout", valor)}
        />
      )}

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
      <div className="grid w-20 shrink-0 grid-cols-2 grid-rows-2 border-l border-line sm:w-16">
        <BotaoDeResultado
          rotulo="Ganha"
          simbolo="✓"
          classe="text-green hover:bg-green/20"
          ocupado={salvando === "green"}
          onClick={() => onMarcar("green")}
        />
        <BotaoDeResultado
          rotulo="Perdida"
          simbolo="✕"
          classe="text-red hover:bg-red/20"
          ocupado={salvando === "red"}
          onClick={() => onMarcar("red")}
        />
        <BotaoDeResultado
          rotulo="Anulada (a casa devolveu o valor apostado)"
          simbolo="∅"
          classe="text-muted hover:bg-white/10"
          ocupado={salvando === "void"}
          onClick={() => onMarcar("void")}
        />
        <BotaoDeResultado
          rotulo="Encerrada antes do fim (cash out)"
          simbolo="⇄"
          classe="text-accent hover:bg-accent/20"
          ocupado={salvando === "cashout"}
          onClick={() => onMarcar("cashout")}
        />
      </div>
    );
  }

  // no encerramento não há cor de resultado a herdar: quem diz se ele foi bom
  // ou ruim é o saldo, e ele pode ser qualquer um dos dois
  const saldo = lucro(tip);
  const cor =
    tip.status === "green" || (tip.status === "cashout" && saldo > 0)
      ? "bg-green/15 text-green"
      : tip.status === "red" || (tip.status === "cashout" && saldo < 0)
        ? "bg-red/15 text-red"
        : "bg-white/5 text-muted";

  if (desfazendo) {
    return (
      <div className="flex w-20 shrink-0 flex-col border-l border-line sm:w-16">
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
      className={`w-20 shrink-0 border-l border-line text-[11px] font-medium transition hover:brightness-125 sm:w-16 ${cor}`}
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

/**
 * Por quanto a aposta foi encerrada.
 *
 * O valor é pedido em **reais** porque é assim que a casa oferece o cash out,
 * na tela em que a pessoa acabou de clicar. As unidades saem da proporção com o
 * valor apostado, e a prévia mostra o resultado dessa conta antes de gravar —
 * encerrar por menos do que apostou é um prejuízo legítimo, mas não pode ser
 * uma surpresa.
 */
function FormularioDeEncerramento({
  tip,
  salvando,
  onCancelar,
  onConfirmar,
}: {
  tip: TipRead;
  salvando: boolean;
  onCancelar: () => void;
  onConfirmar: (valor: string) => void;
}) {
  const [texto, setTexto] = useState("");

  const apostado = Number(tip.stake ?? 0);
  const devolvido = paraNumero(texto);
  const valido = devolvido !== null && devolvido >= 0 && apostado > 0;
  const saldo = valido ? (devolvido / apostado - 1) * stakeUnits(tip) : 0;

  // Tip publicada antes de o valor em reais virar obrigatório: sem ele não há
  // proporção, e um campo com o botão desligado não diria por quê.
  if (apostado <= 0) {
    return (
      <div className="flex flex-wrap items-center gap-3 border-t border-amber/20 bg-amber/10 px-4 py-3 text-xs text-amber">
        <p>
          Esta aposta não tem o valor em reais, e é dele que sai a proporção do
          encerramento. Marque ganha, perdida ou anulada.
        </p>
        <button
          type="button"
          onClick={onCancelar}
          className="ml-auto rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white"
        >
          Fechar
        </button>
      </div>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (valido) onConfirmar(String(devolvido));
      }}
      className="flex flex-wrap items-center gap-2 border-t border-accent/20 bg-accent/5 px-4 py-3 text-sm"
    >
      <label className="flex items-center gap-2">
        <span className="text-muted">Encerrada por R$</span>
        <input
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          inputMode="decimal"
          autoFocus
          placeholder={apostado ? apostado.toFixed(2).replace(".", ",") : "0,00"}
          className="w-28 rounded-lg border border-line bg-surface-2 px-2.5 py-1.5 text-sm tabular-nums outline-none transition focus:border-accent/60"
        />
      </label>

      <span className="text-xs text-muted">
        apostado {formatMoney(tip.stake)} ({formatUnits(tip.stake_units)})
      </span>

      {valido && (
        <span
          className={`text-xs font-semibold tabular-nums ${
            saldo > 0 ? "text-green" : saldo < 0 ? "text-red" : "text-muted"
          }`}
        >
          → {formatUnitsSigned(saldo)} na banca
        </span>
      )}

      <div className="ml-auto flex gap-2">
        <button
          type="button"
          onClick={onCancelar}
          disabled={salvando}
          className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white disabled:opacity-40"
        >
          Cancelar
        </button>
        <button
          type="submit"
          disabled={!valido || salvando}
          className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white transition hover:bg-accent/85 disabled:opacity-40"
        >
          {salvando ? "Encerrando…" : "Encerrar"}
        </button>
      </div>
    </form>
  );
}

/** Aceita "180,50" e "180.50" — o teclado brasileiro dá a vírgula. */
function paraNumero(texto: string): number | null {
  const limpo = texto.trim().replace(",", ".");
  if (limpo === "") return null;
  const n = Number(limpo);
  return Number.isFinite(n) ? n : null;
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
