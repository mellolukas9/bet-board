"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ApiError,
  createAdminUser,
  deleteAdminUser,
  getMe,
  listAdminUsers,
  logout,
  patchAdminUser,
} from "@/lib/api";
import type { AdminUserRead, UserRead } from "@/types/api";

/**
 * Painel de administração do sistema — separado do painel do tipster.
 *
 * Aqui você cria e desativa as contas dos clientes. A moldura é outra
 * (`AppShell` é a do cliente, com as bancas dele na lateral) porque o assunto é
 * outro: quem administra o sistema não tem banca para operar nesta tela.
 *
 * Para quem não é administrador, a API responde 404 — e a tela diz isso em vez
 * de ficar carregando.
 */
export function AdminPage() {
  const router = useRouter();
  const [eu, setEu] = useState<UserRead | null>(null);
  const [contas, setContas] = useState<AdminUserRead[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [semAcesso, setSemAcesso] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let atual = true;

    void (async () => {
      try {
        const [me, lista] = await Promise.all([getMe(), listAdminUsers()]);
        if (!atual) return;
        setEu(me.user);
        setContas(lista);
        setErro(null);
      } catch (e) {
        if (!atual) return;
        if (e instanceof ApiError && e.status === 404) setSemAcesso(true);
        else if (!(e instanceof ApiError && e.status === 401)) {
          setErro(e instanceof Error ? e.message : "Falha ao carregar as contas");
        }
      } finally {
        if (atual) setCarregando(false);
      }
    })();

    return () => {
      atual = false;
    };
  }, []);

  async function recarregar() {
    try {
      setContas(await listAdminUsers());
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao recarregar");
    }
  }

  if (semAcesso) return <SemAcesso />;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-4xl items-center gap-3 px-5">
          <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-amber to-red text-sm font-bold text-[#1a0d02]">
            A
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-semibold tracking-tight">
              Administração
            </h1>
            <p className="truncate text-xs text-muted">
              Contas do sistema{eu && ` · ${eu.username}`}
            </p>
          </div>

          <Link
            href="/"
            className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white"
          >
            Meu painel
          </Link>
          <button
            type="button"
            onClick={() => {
              logout();
              router.replace("/login");
              router.refresh();
            }}
            className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white"
          >
            Sair
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-4xl space-y-4 p-5">
        {erro && (
          <p
            role="alert"
            className="rounded-xl border border-red/30 bg-red/10 p-4 text-sm text-red"
          >
            {erro}
          </p>
        )}

        <NovaConta onCriada={() => void recarregar()} />

        {carregando && (
          <div className="h-32 animate-pulse rounded-xl border border-line bg-surface" />
        )}

        {!carregando && (
          <section className="overflow-hidden rounded-xl border border-line bg-surface">
            <header className="flex items-center justify-between border-b border-line bg-surface-2 px-5 py-3">
              <h2 className="text-sm font-medium">
                {contas.length} {contas.length === 1 ? "conta" : "contas"}
              </h2>
              <button
                type="button"
                onClick={() => void recarregar()}
                className="rounded-lg border border-line px-2.5 py-1 text-xs text-muted transition hover:bg-white/5 hover:text-white"
              >
                Atualizar
              </button>
            </header>

            <div className="divide-y divide-line/70">
              {contas.map((conta) => (
                <Conta
                  key={conta.id}
                  conta={conta}
                  souEu={conta.id === eu?.id}
                  onMudou={(nova) =>
                    setContas((atuais) =>
                      atuais.map((c) => (c.id === nova.id ? nova : c)),
                    )
                  }
                  onApagada={(id) =>
                    setContas((atuais) => atuais.filter((c) => c.id !== id))
                  }
                />
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

function Conta({
  conta,
  souEu,
  onMudou,
  onApagada,
}: {
  conta: AdminUserRead;
  souEu: boolean;
  onMudou: (c: AdminUserRead) => void;
  onApagada: (id: number) => void;
}) {
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [novaSenha, setNovaSenha] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState(false);

  async function acao(fn: () => Promise<void>) {
    setOcupado(true);
    setErro(null);
    try {
      await fn();
    } catch (e) {
      setErro(mensagem(e, "Falha na operação"));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <article className={conta.is_active ? "" : "opacity-60"}>
      <div className="flex flex-wrap items-center gap-3 px-5 py-4">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 font-medium">
            {conta.username}
            {conta.is_superuser && (
              <span className="rounded-full bg-amber/15 px-2 py-0.5 text-[11px] text-amber">
                administrador
              </span>
            )}
            {!conta.is_active && (
              <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-muted">
                desativada
              </span>
            )}
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {conta.name && `${conta.name} · `}
            {conta.bankrolls} {conta.bankrolls === 1 ? "banca" : "bancas"} ·{" "}
            {conta.tips} {conta.tips === 1 ? "tip" : "tips"} ·{" "}
            {conta.last_login_at
              ? `último acesso ${new Date(conta.last_login_at).toLocaleDateString("pt-BR")}`
              : "nunca entrou"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={ocupado}
            onClick={() =>
              void acao(async () => {
                const senha = gerarSenha();
                onMudou(await patchAdminUser(conta.id, { password: senha }));
                setNovaSenha(senha);
              })
            }
            className="rounded-lg border border-line px-2.5 py-1 text-xs text-muted transition hover:bg-white/5 hover:text-white disabled:opacity-40"
          >
            Nova senha
          </button>

          {/* desativar a si mesmo tranca você para fora; o backend recusa, e a
              tela nem oferece */}
          {!souEu && (
            <button
              type="button"
              disabled={ocupado}
              onClick={() =>
                void acao(async () =>
                  onMudou(
                    await patchAdminUser(conta.id, { is_active: !conta.is_active }),
                  ),
                )
              }
              className="rounded-lg border border-line px-2.5 py-1 text-xs text-muted transition hover:bg-white/5 hover:text-white disabled:opacity-40"
            >
              {conta.is_active ? "Desativar" : "Reativar"}
            </button>
          )}

          {!souEu && !confirmando && (
            <button
              type="button"
              disabled={ocupado}
              onClick={() => setConfirmando(true)}
              title="Apagar (só funciona sem bancas)"
              className="rounded-lg px-2 py-1 text-xs text-muted transition hover:bg-red/10 hover:text-red disabled:opacity-40"
            >
              ✕
            </button>
          )}

          {confirmando && (
            <>
              <button
                type="button"
                onClick={() => setConfirmando(false)}
                className="rounded-lg border border-line px-2.5 py-1 text-xs text-muted transition hover:bg-white/5"
              >
                Manter
              </button>
              <button
                type="button"
                disabled={ocupado}
                onClick={() =>
                  void acao(async () => {
                    await deleteAdminUser(conta.id);
                    onApagada(conta.id);
                  })
                }
                className="rounded-lg bg-red px-2.5 py-1 text-xs font-semibold text-[#2a0612] transition hover:brightness-110 disabled:opacity-40"
              >
                Apagar
              </button>
            </>
          )}
        </div>
      </div>

      {novaSenha && (
        <p className="border-t border-green/20 bg-green/10 px-5 py-2.5 text-sm">
          Senha nova de <strong>{conta.username}</strong>:{" "}
          <code className="rounded bg-black/30 px-1.5 py-0.5 font-mono">{novaSenha}</code>{" "}
          <span className="text-xs text-muted">
            — copie agora, ela não aparece de novo.
          </span>
        </p>
      )}

      {erro && (
        <p
          role="alert"
          className="border-t border-red/20 bg-red/10 px-5 py-2.5 text-xs text-red"
        >
          {erro}
        </p>
      )}
    </article>
  );
}

function NovaConta({ onCriada }: { onCriada: () => void }) {
  const [usuario, setUsuario] = useState("");
  const [nome, setNome] = useState("");
  const [banca, setBanca] = useState("");
  const [senha, setSenha] = useState(gerarSenha);
  const [criando, setCriando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [criada, setCriada] = useState<{ usuario: string; senha: string } | null>(null);

  async function criar(e: React.FormEvent) {
    e.preventDefault();
    setCriando(true);
    setErro(null);
    try {
      await createAdminUser({
        username: usuario.trim(),
        password: senha,
        name: nome.trim() || null,
        bankroll_name: banca.trim() || null,
      });
      setCriada({ usuario: usuario.trim(), senha });
      setUsuario("");
      setNome("");
      setBanca("");
      setSenha(gerarSenha());
      onCriada();
    } catch (e) {
      setErro(mensagem(e, "Falha ao criar a conta"));
    } finally {
      setCriando(false);
    }
  }

  return (
    <form
      onSubmit={(e) => void criar(e)}
      className="rounded-xl border border-line bg-surface p-5"
    >
      <h2 className="text-sm font-medium">Nova conta</h2>
      <p className="mt-0.5 text-xs text-muted">
        Você define a senha e entrega ao cliente — não há e-mail nem
        confirmação.
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Campo
          id="usuario"
          rotulo="Usuário"
          valor={usuario}
          onChange={setUsuario}
          placeholder="pecanha"
          required
          minLength={3}
          pattern="[A-Za-z0-9._\\-]+"
          dica="Letras, números, ponto, hífen ou sublinhado."
        />
        <Campo
          id="nome"
          rotulo="Nome (opcional)"
          valor={nome}
          onChange={setNome}
          placeholder="Peçanha"
        />
        <Campo
          id="banca"
          rotulo="Primeira banca (opcional)"
          valor={banca}
          onChange={setBanca}
          placeholder="Vip Peçanha"
          dica="O endereço público sai deste nome."
        />
        <div>
          <label className="block text-xs font-medium text-muted" htmlFor="senha">
            Senha
          </label>
          <div className="mt-1.5 flex gap-2">
            <input
              id="senha"
              value={senha}
              minLength={8}
              required
              onChange={(e) => setSenha(e.target.value)}
              className="min-w-0 flex-1 rounded-lg border border-line bg-surface-2 px-3 py-2 font-mono text-sm outline-none transition focus:border-accent/60"
            />
            <button
              type="button"
              onClick={() => setSenha(gerarSenha())}
              title="Gerar outra"
              className="shrink-0 rounded-lg border border-line px-2.5 text-xs text-muted transition hover:bg-white/5 hover:text-white"
            >
              ↻
            </button>
          </div>
          <p className="mt-1 text-[11px] text-muted">Mínimo de 8 caracteres.</p>
        </div>
      </div>

      {erro && (
        <p role="alert" className="mt-3 text-sm text-red">
          {erro}
        </p>
      )}

      {criada && (
        <p className="mt-3 rounded-lg border border-green/30 bg-green/10 px-3 py-2 text-sm">
          Conta <strong>{criada.usuario}</strong> criada. Senha:{" "}
          <code className="rounded bg-black/30 px-1.5 py-0.5 font-mono">
            {criada.senha}
          </code>{" "}
          <span className="text-xs text-muted">— copie agora.</span>
        </p>
      )}

      <button
        type="submit"
        disabled={criando || !usuario.trim() || senha.length < 8}
        className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent/85 disabled:opacity-40"
      >
        {criando ? "Criando…" : "Criar conta"}
      </button>
    </form>
  );
}

function Campo({
  id,
  rotulo,
  valor,
  onChange,
  placeholder,
  dica,
  ...resto
}: {
  id: string;
  rotulo: string;
  valor: string;
  onChange: (v: string) => void;
  placeholder?: string;
  dica?: string;
  // o resto vai direto para o <input> (required, minLength, pattern…); os
  // atributos que este componente já controla ficam de fora para não colidirem
} & Omit<
  React.InputHTMLAttributes<HTMLInputElement>,
  "id" | "value" | "onChange" | "placeholder"
>) {
  return (
    <div>
      <label className="block text-xs font-medium text-muted" htmlFor={id}>
        {rotulo}
      </label>
      <input
        id={id}
        value={valor}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="off"
        className="mt-1.5 w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm outline-none transition focus:border-accent/60"
        {...resto}
      />
      {dica && <p className="mt-1 text-[11px] text-muted">{dica}</p>}
    </div>
  );
}

function SemAcesso() {
  return (
    <main className="grid min-h-screen place-items-center p-6">
      <div className="max-w-sm rounded-xl border border-line bg-surface p-8 text-center">
        <h1 className="text-lg font-semibold">Página não encontrada</h1>
        <p className="mt-2 text-sm text-muted">
          Esta conta não administra o sistema.
        </p>
        <Link
          href="/"
          className="mt-5 inline-block rounded-lg border border-line px-3 py-1.5 text-sm text-muted transition hover:bg-white/5 hover:text-white"
        >
          Ir para o meu painel
        </Link>
      </div>
    </main>
  );
}

/**
 * Senha inicial legível, gerada no navegador.
 *
 * Sem `i`, `l`, `1`, `O` e `0`: a senha vai ser lida em voz alta ou copiada de
 * um print, e esses cinco são os que geram o suporte de volta.
 */
function gerarSenha(): string {
  const alfabeto = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789";
  const bytes = new Uint32Array(14);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => alfabeto[b % alfabeto.length]).join("");
}

function mensagem(e: unknown, padrao: string): string {
  return e instanceof ApiError || e instanceof Error ? e.message : padrao;
}
