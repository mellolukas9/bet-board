"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell, esquecerConta } from "@/components/AppShell";
import { ApiError, createBankroll, listBankrolls } from "@/lib/api";
import type { BankrollRead } from "@/types/api";

/**
 * As bancas da conta, e o formulário de criar mais uma.
 *
 * Cada banca é um grupo: canal próprio, tips próprias e página pública própria.
 * É aqui que um tipster separa o VIP do Free.
 */
export function BancasPage() {
  const [bankrolls, setBankrolls] = useState<BankrollRead[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let atual = true;

    void (async () => {
      try {
        const encontradas = await listBankrolls();
        if (atual) setBankrolls(encontradas);
      } catch (e) {
        if (atual) setErro(mensagem(e, "Falha ao carregar as bancas"));
      } finally {
        if (atual) setCarregando(false);
      }
    })();

    return () => {
      atual = false;
    };
  }, []);

  return (
    <AppShell titulo="Minhas bancas">
      <div className="mx-auto w-full max-w-3xl space-y-4">
        {erro && (
          <p
            role="alert"
            className="rounded-xl border border-red/30 bg-red/10 p-4 text-sm text-red"
          >
            {erro}
          </p>
        )}

        {!carregando && bankrolls.length === 0 && (
          <p className="rounded-xl border border-dashed border-line p-10 text-center text-sm text-muted">
            Você ainda não tem nenhuma banca. Crie a primeira abaixo.
          </p>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          {bankrolls.map((b) => (
            <Cartao key={b.id} bankroll={b} />
          ))}
        </div>

        <NovaBanca
          onCriada={(nova) => setBankrolls((atuais) => [...atuais, nova])}
        />
      </div>
    </AppShell>
  );
}

function Cartao({ bankroll }: { bankroll: BankrollRead }) {
  return (
    <Link
      href={`/banca/${bankroll.slug}`}
      className="rounded-xl border border-line bg-surface p-4 transition hover:border-accent/40 hover:bg-surface-2"
    >
      <h2 className="truncate font-medium">{bankroll.name}</h2>
      <p className="mt-0.5 truncate font-mono text-xs text-muted">
        /b/{bankroll.slug}
      </p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Selo ok={bankroll.telegram_configured}>
          {bankroll.telegram_configured ? "Telegram ligado" : "sem canal"}
        </Selo>
        <Selo ok={bankroll.is_public}>
          {bankroll.is_public ? "página pública" : "privada"}
        </Selo>
      </div>
    </Link>
  );
}

function Selo({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[11px] ${
        ok ? "bg-green/15 text-green" : "bg-white/5 text-muted"
      }`}
    >
      {children}
    </span>
  );
}

function NovaBanca({ onCriada }: { onCriada: (b: BankrollRead) => void }) {
  const router = useRouter();
  const [nome, setNome] = useState("");
  const [criando, setCriando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function criar(e: React.FormEvent) {
    e.preventDefault();
    setCriando(true);
    setErro(null);
    try {
      const nova = await createBankroll({ name: nome.trim() });
      // a lateral lembrada ainda não conhece esta banca
      esquecerConta();
      onCriada(nova);
      setNome("");
      // já leva para a configuração: sem canal, a banca não publica nada
      router.push(`/banca/${nova.slug}/config`);
    } catch (e) {
      setErro(mensagem(e, "Falha ao criar a banca"));
      setCriando(false);
    }
  }

  return (
    <form
      onSubmit={(e) => void criar(e)}
      className="rounded-xl border border-line bg-surface p-5"
    >
      <h2 className="text-sm font-medium">Nova banca</h2>
      <p className="mt-0.5 text-xs text-muted">
        O endereço público é derivado do nome, e dá para trocar depois.
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        <input
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          required
          maxLength={120}
          placeholder="Vip Peçanha"
          className="min-w-0 flex-1 rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm outline-none transition focus:border-accent/60"
        />
        <button
          type="submit"
          disabled={criando || !nome.trim()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent/85 disabled:opacity-40"
        >
          {criando ? "Criando…" : "Criar"}
        </button>
      </div>

      {erro && (
        <p role="alert" className="mt-3 text-sm text-red">
          {erro}
        </p>
      )}
    </form>
  );
}

function mensagem(e: unknown, padrao: string): string {
  return e instanceof ApiError || e instanceof Error ? e.message : padrao;
}
