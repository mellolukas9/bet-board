"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { esquecerConta, useBanca } from "@/components/AppShell";
import { TelegramWizard } from "@/components/TelegramWizard";
import { ApiError, deleteBankroll, patchBankroll } from "@/lib/api";
import { slugify } from "@/lib/slug";
import type { BankrollRead } from "@/types/api";

/**
 * Configurações da banca: identidade, página pública e canais de envio.
 *
 * Toda alteração sobe para a moldura (`aoMudarBanca`): é ela que mantém a
 * lateral e — quando renomear troca o endereço — a URL desta tela, que sem isso
 * apontaria para uma banca que já não existe naquele slug.
 */
export function ConfigPage() {
  const router = useRouter();
  const { banca, aoMudarBanca } = useBanca();

  return (
    <div className="mx-auto w-full max-w-3xl space-y-4">
      <Identidade bankroll={banca} onChange={aoMudarBanca} />
      <PaginaPublica bankroll={banca} onChange={aoMudarBanca} />
      <TelegramWizard bankroll={banca} onChange={aoMudarBanca} />
      <Perigo bankroll={banca} router={router} />
    </div>
  );
}

function Identidade({
  bankroll,
  onChange,
}: {
  bankroll: BankrollRead;
  onChange: (b: BankrollRead) => void;
}) {
  const [nome, setNome] = useState(bankroll.name);
  const [descricao, setDescricao] = useState(bankroll.description ?? "");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [salvo, setSalvo] = useState(false);

  const mudou = nome !== bankroll.name || descricao !== (bankroll.description ?? "");

  // Prévia do endereço: quem grava é o backend, mas a pessoa precisa ver o link
  // mudando enquanto digita — é o link que ela já mandou para os assinantes.
  const enderecoPrevisto = slugify(nome) || bankroll.slug;
  const vaiTrocarOLink =
    nome.trim() !== bankroll.name && enderecoPrevisto !== bankroll.slug;

  async function salvar() {
    setSalvando(true);
    setErro(null);
    try {
      onChange(
        await patchBankroll(bankroll.id, {
          name: nome.trim(),
          description: descricao.trim() || null,
        }),
      );
      setSalvo(true);
    } catch (e) {
      setErro(mensagem(e, "Falha ao salvar"));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <section className="rounded-xl border border-line bg-surface p-5">
      <h2 className="text-sm font-medium">A banca</h2>

      <label className="mt-4 block text-xs font-medium text-muted" htmlFor="nome">
        Nome
      </label>
      <input
        id="nome"
        value={nome}
        maxLength={120}
        onChange={(e) => {
          setNome(e.target.value);
          setSalvo(false);
        }}
        className="mt-1.5 w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm outline-none transition focus:border-accent/60"
      />
      <p className="mt-1.5 text-xs text-muted">
        O endereço público segue o nome:{" "}
        <span className="font-mono text-foreground/80">/b/{enderecoPrevisto}</span>
        {vaiTrocarOLink && (
          <span className="text-amber">
            {" "}
            — ao salvar, o link atual (/b/{bankroll.slug}) para de funcionar.
          </span>
        )}
      </p>

      <label className="mt-4 block text-xs font-medium text-muted" htmlFor="descricao">
        Descrição <span className="font-normal">(aparece na página pública)</span>
      </label>
      <textarea
        id="descricao"
        value={descricao}
        rows={2}
        onChange={(e) => {
          setDescricao(e.target.value);
          setSalvo(false);
        }}
        placeholder="Tips de futebol, 2 a 4 entradas por dia."
        className="mt-1.5 w-full resize-y rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm outline-none transition focus:border-accent/60"
      />

      {erro && (
        <p
          role="alert"
          className="mt-3 rounded-lg border border-red/30 bg-red/10 px-3 py-2 text-sm text-red"
        >
          {erro}
        </p>
      )}

      <div className="mt-4 flex items-center gap-2">
        <button
          type="button"
          onClick={() => void salvar()}
          disabled={!mudou || salvando}
          className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white disabled:opacity-40"
        >
          {salvando ? "Salvando…" : "Salvar"}
        </button>
        {salvo && !mudou && <span className="text-xs text-green">salvo</span>}
      </div>
    </section>
  );
}

/**
 * Endereço público e a chave que liga a página.
 *
 * O endereço **não** é editável: ele é derivado do nome da banca, no backend.
 * Ter os dois editáveis deixaria `/b/vip-pecanha` numa banca chamada "Free" —
 * e esse link é o que a pessoa manda para os assinantes. Para trocar o
 * endereço, troca-se o nome.
 */
function PaginaPublica({
  bankroll,
  onChange,
}: {
  bankroll: BankrollRead;
  onChange: (b: BankrollRead) => void;
}) {
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [copiado, setCopiado] = useState(false);
  // `window` não existe no servidor, daí o inicializador preguiçoso. Não há
  // risco de divergência na hidratação: esta tela só é montada depois que o
  // AppShell carregou a conta, então o servidor nunca chega a renderizá-la.
  const [origem] = useState(() =>
    typeof window === "undefined" ? "" : window.location.origin,
  );

  const url = `${origem}/b/${bankroll.slug}`;

  async function alternarPublica() {
    setSalvando(true);
    setErro(null);
    try {
      onChange(await patchBankroll(bankroll.id, { is_public: !bankroll.is_public }));
    } catch (e) {
      setErro(mensagem(e, "Falha ao mudar a visibilidade"));
    } finally {
      setSalvando(false);
    }
  }

  async function copiar() {
    try {
      await navigator.clipboard.writeText(url);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      // navegador sem permissão de área de transferência: o link está na tela
    }
  }

  return (
    <section className="rounded-xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-medium">Página pública</h2>
          <p className="mt-0.5 text-xs text-muted">
            O link que você manda para os assinantes verem os resultados.
          </p>
        </div>

        <Interruptor
          ligado={bankroll.is_public}
          ocupado={salvando}
          rotulo={bankroll.is_public ? "Despublicar a banca" : "Publicar a banca"}
          onClick={() => void alternarPublica()}
        />
      </div>

      <p className="mt-3 text-xs text-muted">
        {bankroll.is_public
          ? "Ligada: qualquer pessoa com o link vê os resultados, em unidades. Valores em reais nunca aparecem."
          : "Desligada: o link responde 404 para todo mundo."}
      </p>

      <label className="mt-4 block text-xs font-medium text-muted" htmlFor="slug">
        Endereço
      </label>
      <div className="mt-1.5 flex items-center gap-2">
        <input
          id="slug"
          value={`/b/${bankroll.slug}`}
          readOnly
          disabled
          aria-describedby="slug-ajuda"
          className="min-w-0 flex-1 cursor-not-allowed rounded-lg border border-line bg-surface-2/50 px-3 py-2 font-mono text-sm text-muted"
        />
        {bankroll.is_public && (
          <button
            type="button"
            onClick={() => void copiar()}
            className="shrink-0 rounded-lg border border-line px-3 py-2 text-xs text-muted transition hover:bg-white/5 hover:text-white"
          >
            {copiado ? "copiado" : "copiar link"}
          </button>
        )}
      </div>
      <p id="slug-ajuda" className="mt-1.5 text-xs text-muted">
        Vem do nome da banca. Para mudar o endereço, mude o nome ali em cima.
      </p>

      {bankroll.is_public && origem && (
        <a
          href={`/b/${bankroll.slug}`}
          target="_blank"
          rel="noreferrer"
          className="mt-3 block truncate rounded-lg border border-line bg-surface-2 px-3 py-2 font-mono text-sm text-accent underline underline-offset-2"
        >
          {url}
        </a>
      )}

      {erro && (
        <p
          role="alert"
          className="mt-3 rounded-lg border border-red/30 bg-red/10 px-3 py-2 text-sm text-red"
        >
          {erro}
        </p>
      )}
    </section>
  );
}

/**
 * Interruptor de ligar/desligar.
 *
 * A pista tem largura fixa e é o `relative` de referência; a bolinha é
 * `absolute` dentro dela. A versão anterior empurrava a bolinha com
 * `translate-x` dentro de um flex sem largura definida, e o botão crescia
 * junto — o que aparecia como duas bolas lado a lado quando ligado.
 */
function Interruptor({
  ligado,
  ocupado,
  rotulo,
  onClick,
}: {
  ligado: boolean;
  ocupado: boolean;
  rotulo: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={ligado}
      aria-label={rotulo}
      title={rotulo}
      onClick={onClick}
      disabled={ocupado}
      className={`relative h-6 w-11 shrink-0 rounded-full transition disabled:opacity-40 ${
        ligado ? "bg-green/70" : "bg-surface-3"
      }`}
    >
      <span
        aria-hidden
        className={`absolute top-0.5 size-5 rounded-full bg-white shadow transition-all ${
          ligado ? "left-[1.375rem]" : "left-0.5"
        }`}
      />
    </button>
  );
}

function Perigo({
  bankroll,
  router,
}: {
  bankroll: BankrollRead;
  router: ReturnType<typeof useRouter>;
}) {
  const [confirmando, setConfirmando] = useState(false);
  const [apagando, setApagando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function apagar() {
    setApagando(true);
    setErro(null);
    try {
      await deleteBankroll(bankroll.id);
      // a lateral lembrada ainda tem esta banca; sem isto ela reaparece por um
      // instante na próxima tela
      esquecerConta();
      router.replace("/bancas");
      router.refresh();
    } catch (e) {
      setErro(mensagem(e, "Falha ao apagar"));
      setApagando(false);
      setConfirmando(false);
    }
  }

  return (
    <section className="rounded-xl border border-line bg-surface p-5">
      <h2 className="text-sm font-medium">Apagar a banca</h2>
      <p className="mt-0.5 text-xs text-muted">
        Só funciona enquanto ela não tiver nenhuma tip — histórico não some num
        clique.
      </p>

      {erro && (
        <p
          role="alert"
          className="mt-3 rounded-lg border border-red/30 bg-red/10 px-3 py-2 text-sm text-red"
        >
          {erro}
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {confirmando ? (
          <>
            <span className="text-sm text-red">Apagar {bankroll.name}?</span>
            <button
              type="button"
              onClick={() => setConfirmando(false)}
              disabled={apagando}
              className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white disabled:opacity-40"
            >
              Manter
            </button>
            <button
              type="button"
              onClick={() => void apagar()}
              disabled={apagando}
              className="rounded-lg bg-red px-3 py-1.5 text-sm font-semibold text-[#2a0612] transition hover:brightness-110 disabled:opacity-40"
            >
              {apagando ? "Apagando…" : "Apagar"}
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setConfirmando(true)}
            className="rounded-lg border border-red/30 px-3 py-1.5 text-sm text-red transition hover:bg-red/10"
          >
            Apagar banca
          </button>
        )}
      </div>
    </section>
  );
}

function mensagem(e: unknown, padrao: string): string {
  return e instanceof ApiError || e instanceof Error ? e.message : padrao;
}
