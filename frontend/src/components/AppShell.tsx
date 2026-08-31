"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { ApiError, getMe, logout } from "@/lib/api";
import type { BankrollRead, UserRead } from "@/types/api";

/** As três telas de dentro de uma banca. */
const SECOES = [
  { chave: "banca", rotulo: "Banca", caminho: "", icone: IconeBanca },
  { chave: "tips", rotulo: "Tips", caminho: "/tips", icone: IconeTips },
  { chave: "config", rotulo: "Configurações", caminho: "/config", icone: IconeConfig },
] as const;

export type Secao = (typeof SECOES)[number]["chave"];

/**
 * Moldura do painel: barra lateral com as bancas da conta + topo.
 *
 * É ela que carrega o `GET /auth/me` — uma vez por tela — e resolve o `slug` da
 * URL para a banca correspondente. As páginas de dentro recebem a banca já
 * resolvida, em vez de cada uma ir buscar a sua.
 *
 * Fica de fora do `/login` e da página pública, que não têm conta nenhuma.
 */
export function AppShell({
  slug,
  secao,
  titulo,
  acoes,
  children,
}: {
  /** Banca da URL. Sem ela, a moldura serve uma tela de conta (ex: /bancas). */
  slug?: string;
  secao?: Secao;
  titulo?: string;
  acoes?: ReactNode;
  children: ReactNode | ((bankroll: BankrollRead) => ReactNode);
}) {
  const router = useRouter();
  const [user, setUser] = useState<UserRead | null>(null);
  const [bankrolls, setBankrolls] = useState<BankrollRead[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  /**
   * Carga da conta.
   *
   * O `await` vem antes de qualquer `setState`: no corpo síncrono do efeito o
   * React 19 reprova (`react-hooks/set-state-in-effect`).
   */
  useEffect(() => {
    let atual = true;

    void (async () => {
      try {
        const me = await getMe();
        if (!atual) return;
        setUser(me.user);
        setBankrolls(me.bankrolls);
        setErro(null);
      } catch (e) {
        // 401 já é tratado no cliente HTTP: ele limpa o cookie e recarrega
        if (atual && !(e instanceof ApiError && e.status === 401)) {
          setErro(e instanceof Error ? e.message : "Falha ao carregar a conta");
        }
      } finally {
        if (atual) setCarregando(false);
      }
    })();

    return () => {
      atual = false;
    };
  }, []);

  function sair() {
    logout();
    router.replace("/login");
    // o proxy lê o cookie no servidor; sem o refresh a rota anterior fica em cache
    router.refresh();
  }

  const atual = slug ? bankrolls.find((b) => b.slug === slug) : undefined;

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-surface md:flex">
        <Link
          href="/"
          className="flex h-16 items-center gap-2.5 border-b border-line px-5"
        >
          <span className="grid size-8 place-items-center rounded-lg bg-gradient-to-br from-green to-accent text-sm font-bold text-[#07101f]">
            B
          </span>
          <span className="text-[15px] font-semibold tracking-tight">
            Bet Board
          </span>
        </Link>

        <nav className="flex-1 overflow-y-auto p-3">
          <p className="px-2 pb-2 pt-1 text-[10px] font-semibold tracking-widest text-muted">
            BANCAS
          </p>

          {bankrolls.map((b) => (
            <div key={b.id} className="mb-1">
              <Link
                href={`/banca/${b.slug}`}
                aria-current={b.slug === slug ? "page" : undefined}
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition ${
                  b.slug === slug
                    ? "bg-accent/15 font-medium text-white ring-1 ring-inset ring-accent/30"
                    : "text-muted hover:bg-white/5 hover:text-white"
                }`}
              >
                <span className="truncate">{b.name}</span>
                {b.is_public && (
                  <span
                    title="Página pública ligada"
                    className="ml-auto shrink-0 text-[10px] text-green"
                  >
                    ●
                  </span>
                )}
              </Link>

              {/* as seções só aparecem sob a banca aberta: um menu por banca
                  deixaria a lateral ilegível para quem tem várias */}
              {b.slug === slug && (
                <div className="ml-3 mt-1 border-l border-line pl-2">
                  {SECOES.map(({ chave, rotulo, caminho, icone: Icone }) => (
                    <Link
                      key={chave}
                      href={`/banca/${b.slug}${caminho}`}
                      aria-current={chave === secao ? "page" : undefined}
                      className={`flex items-center gap-2 rounded-md px-2.5 py-1.5 text-[13px] transition ${
                        chave === secao
                          ? "text-white"
                          : "text-muted hover:text-white"
                      }`}
                    >
                      <Icone />
                      {rotulo}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          ))}

          {!carregando && bankrolls.length === 0 && (
            <p className="px-3 py-2 text-xs text-muted">
              Nenhuma banca ainda.
            </p>
          )}

          <Link
            href="/bancas"
            className="mt-2 flex items-center gap-2 rounded-lg border border-dashed border-line px-3 py-2 text-sm text-muted transition hover:border-accent/50 hover:text-white"
          >
            + Nova banca
          </Link>
        </nav>

        <div className="border-t border-line p-3">
          {/* o atalho só existe para quem administra o sistema; para os demais a
              rota /admin responde "não encontrada" */}
          {user?.is_superuser && (
            <Link
              href="/admin"
              className="mb-1 flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-amber transition hover:bg-amber/10"
            >
              <IconeAdmin />
              Administração
            </Link>
          )}

          {user && (
            <p className="truncate px-3 pb-1 text-xs text-muted">
              {user.name || user.username}
            </p>
          )}
          <button
            type="button"
            onClick={sair}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-muted transition hover:bg-white/5 hover:text-white"
          >
            <IconeSair />
            Sair
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-16 items-center gap-4 border-b border-line bg-surface/95 px-5 backdrop-blur">
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-semibold tracking-tight">
              {titulo ?? atual?.name ?? "Bet Board"}
            </h1>
            {atual && (
              <p className="truncate text-xs text-muted">
                {SECOES.find((s) => s.chave === secao)?.rotulo}
                {atual.is_public && ` · pública em /b/${atual.slug}`}
              </p>
            )}
          </div>
          {acoes}
          <button
            type="button"
            onClick={sair}
            className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white md:hidden"
          >
            Sair
          </button>
        </header>

        <main className="flex-1 p-5">
          {erro && (
            <p
              role="alert"
              className="mx-auto max-w-5xl rounded-xl border border-red/30 bg-red/10 p-4 text-sm text-red"
            >
              {erro}
            </p>
          )}

          {carregando && <Carregando />}

          {!carregando && !erro && typeof children !== "function" && children}

          {!carregando && !erro && typeof children === "function" && (
            atual ? children(atual) : <BancaNaoEncontrada slug={slug} />
          )}
        </main>
      </div>
    </div>
  );
}

function Carregando() {
  return (
    <div className="mx-auto max-w-5xl space-y-3">
      <div className="h-56 animate-pulse rounded-xl border border-line bg-surface" />
      <div className="h-24 animate-pulse rounded-xl border border-line bg-surface" />
    </div>
  );
}

function BancaNaoEncontrada({ slug }: { slug?: string }) {
  return (
    <div className="mx-auto max-w-md rounded-xl border border-line bg-surface p-8 text-center">
      <p className="text-sm">
        Não achei a banca <span className="font-mono">{slug}</span> nesta conta.
      </p>
      <Link
        href="/bancas"
        className="mt-4 inline-block rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white"
      >
        Ver minhas bancas
      </Link>
    </div>
  );
}

function IconeBanca() {
  return (
    <svg viewBox="0 0 20 20" className="size-3.5" fill="none" aria-hidden>
      <path
        d="M4 13.5 8 9l3 3 5-5.5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconeTips() {
  return (
    <svg viewBox="0 0 20 20" className="size-3.5" fill="none" aria-hidden>
      <rect
        x="3.5"
        y="3.5"
        width="13"
        height="13"
        rx="2.5"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <path d="M7 8h6M7 11.5h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function IconeConfig() {
  return (
    <svg viewBox="0 0 20 20" className="size-3.5" fill="none" aria-hidden>
      <circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M10 3v2m0 10v2M3 10h2m10 0h2M5.2 5.2l1.4 1.4m6.8 6.8 1.4 1.4m0-9.6-1.4 1.4m-6.8 6.8-1.4 1.4"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconeAdmin() {
  return (
    <svg viewBox="0 0 20 20" className="size-4" fill="none" aria-hidden>
      <path
        d="M10 3.5 4.5 6v3.8c0 3 2.3 5.4 5.5 6.7 3.2-1.3 5.5-3.7 5.5-6.7V6L10 3.5Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconeSair() {
  return (
    <svg viewBox="0 0 20 20" className="size-4" fill="none" aria-hidden>
      <path
        d="M8 4.5H5.5A1.5 1.5 0 0 0 4 6v8a1.5 1.5 0 0 0 1.5 1.5H8"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path
        d="M11.5 7 14.5 10l-3 3M14 10H7.5"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
