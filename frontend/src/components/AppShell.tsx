"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  use,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { AvisoDeSessao, useSessao } from "@/components/Sessao";
import { ApiError, getMe, logout } from "@/lib/api";
import type { BankrollRead, MeRead, UserRead } from "@/types/api";

/** As três telas de dentro de uma banca. */
const SECOES = [
  { chave: "banca", rotulo: "Banca", caminho: "", icone: IconeBanca },
  { chave: "tips", rotulo: "Tips", caminho: "/tips", icone: IconeTips },
  { chave: "config", rotulo: "Configurações", caminho: "/config", icone: IconeConfig },
] as const;

/**
 * A última conta carregada, guardada fora do React.
 *
 * A moldura da banca sobrevive à troca de seção (ela é o `layout` do
 * `/banca/[slug]`), mas as telas de conta — `/bancas`, `/admin` — montam uma
 * moldura nova cada uma. Sem esta memória, cada ida a elas apagava a lateral
 * inteira e a redesenhava idêntica meio segundo depois. O `GET /auth/me`
 * continua acontecendo: ele só deixou de ser o que decide se há algo na tela.
 */
let contaEmMemoria: MeRead | null = null;

/**
 * Descarta a conta lembrada.
 *
 * Quem cria ou apaga uma banca precisa chamar isto: a lista lembrada ficaria
 * uma banca atrás, e a próxima moldura a montar desenharia a lateral errada
 * antes de o `GET /auth/me` corrigi-la.
 */
export function esquecerConta(): void {
  contaEmMemoria = null;
}

/** A banca aberta, para as telas de dentro dela. */
export type BancaAberta = {
  banca: BankrollRead;
  /** Avisa a moldura de que a banca mudou (renomear troca o nome na lateral). */
  aoMudarBanca: (banca: BankrollRead) => void;
};

const BancaContext = createContext<BancaAberta | null>(null);

/**
 * A banca da URL, já resolvida pela moldura.
 *
 * Só existe dentro de `/banca/[slug]`; fora dali é erro de programação, e o
 * throw diz isso na hora, em vez de deixar um `null` chegar à tela.
 */
export function useBanca(): BancaAberta {
  const contexto = use(BancaContext);
  if (contexto === null) {
    throw new Error("useBanca() só funciona dentro do layout de /banca/[slug].");
  }
  return contexto;
}

/** O caminho depois do `/banca/{slug}` — "", "/tips" ou "/config". */
function caminhoDaSecao(pathname: string, slug: string): string {
  return pathname.startsWith(`/banca/${slug}`)
    ? pathname.slice(`/banca/${slug}`.length)
    : "";
}

/**
 * Moldura do painel: barra lateral com as bancas da conta + topo.
 *
 * É ela que carrega o `GET /auth/me` e resolve o `slug` da URL para a banca
 * correspondente, entregue às telas de dentro pelo `useBanca()` — em vez de
 * cada uma ir buscar a sua.
 *
 * Dentro de uma banca ela é o `layout` do `/banca/[slug]`: montada uma vez, ela
 * **fica** quando se troca de seção. Antes cada tela montava a sua, e ir da
 * Banca para Tips apagava a lateral e o topo para redesenhá-los iguais.
 *
 * Fica de fora do `/login` e da página pública, que não têm conta nenhuma.
 */
export function AppShell({
  slug,
  titulo,
  acoes,
  children,
}: {
  /** Banca da URL. Sem ela, a moldura serve uma tela de conta (ex: /bancas). */
  slug?: string;
  titulo?: string;
  acoes?: ReactNode;
  children: ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<UserRead | null>(contaEmMemoria?.user ?? null);
  const [bankrolls, setBankrolls] = useState<BankrollRead[]>(
    contaEmMemoria?.bankrolls ?? [],
  );
  const [carregando, setCarregando] = useState(contaEmMemoria === null);
  const [erro, setErro] = useState<string | null>(null);
  //: "confirmando" enquanto a pergunta está na tela, "saindo" enquanto a volta
  //: para o login acontece
  const [saida, setSaida] = useState<"nao" | "confirmando" | "saindo">("nao");
  // a sessão cai sozinha depois de um tempo sem uso; o relógio mora aqui porque
  // esta moldura é o que toda tela de dentro da conta tem em comum
  const { avisoEmSegundos, continuar } = useSessao();

  const secao = slug
    ? SECOES.find((s) => s.caminho === caminhoDaSecao(pathname, slug))?.chave
    : undefined;

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
        contaEmMemoria = me;
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

  /**
   * Sair de verdade, depois de a pessoa confirmar.
   *
   * O estado vira "saindo" **antes** do `replace` porque a volta ao login passa
   * pelo servidor (é o `proxy` que decide a rota): sem a tela de saída, o
   * painel ficaria parado, com os dados de quem já saiu, até a troca acontecer.
   */
  function sair() {
    setSaida("saindo");
    // a memória da conta não pode sobreviver ao logout: quem entrasse depois
    // nesta aba veria a lateral da pessoa anterior por um instante
    contaEmMemoria = null;
    logout();
    router.replace("/login");
    // o proxy lê o cookie no servidor; sem o refresh a rota anterior fica em cache
    router.refresh();
  }

  const atual = slug ? bankrolls.find((b) => b.slug === slug) : undefined;

  /**
   * A tela de dentro mexeu na banca (renomear, publicar): a lateral precisa
   * acompanhar, porque a moldura não remonta mais a cada navegação.
   *
   * Renomear também troca o endereço, e o endereço está na URL — daí o
   * `replace`, que faz a moldura reencontrar a banca pelo slug novo sem
   * recarregar a página.
   */
  const aoMudarBanca = useCallback(
    (banca: BankrollRead) => {
      contaEmMemoria = null;
      setBankrolls((atuais) => atuais.map((b) => (b.id === banca.id ? banca : b)));
      if (slug && banca.slug !== slug) {
        router.replace(`/banca/${banca.slug}${caminhoDaSecao(pathname, slug)}`);
      }
    },
    [pathname, router, slug],
  );

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
            onClick={() => setSaida("confirmando")}
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
            onClick={() => setSaida("confirmando")}
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

          {!carregando && !erro && !slug && children}

          {!carregando &&
            !erro &&
            slug &&
            (atual ? (
              <BancaContext value={{ banca: atual, aoMudarBanca }}>
                {children}
              </BancaContext>
            ) : (
              <BancaNaoEncontrada slug={slug} />
            ))}
        </main>
      </div>

      {saida === "confirmando" && (
        <ConfirmarSaida
          nome={user?.name || user?.username}
          onCancelar={() => setSaida("nao")}
          onSair={sair}
        />
      )}

      {saida === "saindo" && <Saindo />}

      {/* enquanto a pessoa está confirmando a saída, avisar que a sessão vai
          cair só atrapalharia a leitura de uma pergunta que já é sobre sair */}
      {avisoEmSegundos !== null && saida === "nao" && (
        <AvisoDeSessao segundos={avisoEmSegundos} onContinuar={continuar} />
      )}
    </div>
  );
}

/**
 * "Sair mesmo?", antes de derrubar a sessão.
 *
 * Não é um `confirm()` do navegador: ele trava a página inteira enquanto está
 * aberto, e é o mesmo motivo pelo qual as outras confirmações do painel (a de
 * descartar tip, a de apagar banca) também são de mentira.
 *
 * O botão que fica em foco é o de **ficar**: quem chegou aqui sem querer sai da
 * pergunta com um Enter, e quem quer mesmo sair dá um Tab a mais.
 */
function ConfirmarSaida({
  nome,
  onCancelar,
  onSair,
}: {
  nome?: string | null;
  onCancelar: () => void;
  onSair: () => void;
}) {
  // Esc fecha: é o que se espera de qualquer caixa dessas, e aqui ela cobre a
  // tela inteira — sem isso o teclado ficaria preso nos dois botões
  useEffect(() => {
    function aoTeclar(e: KeyboardEvent) {
      if (e.key === "Escape") onCancelar();
    }
    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, [onCancelar]);

  return (
    <div
      // clicar fora é o mesmo que cancelar; o `stopPropagation` da caixa evita
      // que um clique dentro dela conte como "fora"
      onClick={onCancelar}
      className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-5 backdrop-blur-sm"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-da-saida"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-xl border border-line bg-surface p-6 shadow-2xl"
      >
        <h2 id="titulo-da-saida" className="text-base font-medium">
          Sair da conta?
        </h2>
        <p className="mt-1.5 text-sm text-muted">
          {nome ? `Você vai desconectar ${nome} deste navegador e ` : "Você vai "}
          voltar para a tela de login.
        </p>

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            autoFocus
            onClick={onCancelar}
            className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white"
          >
            Ficar
          </button>
          <button
            type="button"
            onClick={onSair}
            className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white transition hover:bg-accent/85"
          >
            Sair
          </button>
        </div>
      </div>
    </div>
  );
}

/** A tela enquanto o painel dá lugar ao login. */
function Saindo() {
  return (
    <div
      role="status"
      className="fixed inset-0 z-50 grid place-items-center bg-background/95 backdrop-blur-sm"
    >
      <div className="flex items-center gap-3 text-sm text-muted">
        <span
          aria-hidden
          className="size-4 shrink-0 animate-spin rounded-full border-2 border-line border-t-accent"
        />
        Saindo…
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
