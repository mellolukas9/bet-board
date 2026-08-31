"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { ApiError, login } from "@/lib/api";

/**
 * Login do admin.
 *
 * Um usuário só — o dono do grupo —, com as credenciais no `.env` do backend.
 * O token volta do `POST /auth/login` e fica num cookie, que o `proxy.ts` lê
 * para barrar quem não entrou.
 */
export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [usuario, setUsuario] = useState("");
  const [senha, setSenha] = useState("");
  const [entrando, setEntrando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function entrar(e: React.FormEvent) {
    e.preventDefault();
    setEntrando(true);
    setErro(null);

    try {
      await login(usuario.trim(), senha);
      // `next` vem do proxy: volta para a página que a pessoa tentou abrir
      const destino = params.get("next");
      router.replace(destino?.startsWith("/") ? destino : "/");
      // o cookie acabou de nascer; sem isto o proxy ainda enxerga o estado antigo
      router.refresh();
    } catch (e) {
      setErro(
        e instanceof ApiError || e instanceof Error
          ? e.message
          : "Não foi possível entrar",
      );
      setEntrando(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-green to-accent text-base font-bold text-[#07101f]">
            B
          </span>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Bet Board</h1>
            <p className="text-xs text-muted">Painel do administrador</p>
          </div>
        </div>

        <form
          onSubmit={(e) => void entrar(e)}
          className="rounded-2xl border border-line bg-surface p-6"
        >
          <label className="block text-xs font-medium text-muted" htmlFor="usuario">
            Usuário
          </label>
          <input
            id="usuario"
            name="username"
            autoComplete="username"
            autoFocus
            required
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm outline-none transition focus:border-accent/60"
          />

          <label
            className="mt-4 block text-xs font-medium text-muted"
            htmlFor="senha"
          >
            Senha
          </label>
          <input
            id="senha"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm outline-none transition focus:border-accent/60"
          />

          {erro && (
            <p
              role="alert"
              className="mt-4 rounded-lg border border-red/30 bg-red/10 px-3 py-2 text-sm text-red"
            >
              {erro}
            </p>
          )}

          <button
            type="submit"
            disabled={entrando}
            className="mt-6 w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition hover:bg-accent/85 disabled:opacity-50"
          >
            {entrando ? "Entrando…" : "Entrar"}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-muted">
          Não há cadastro aberto: a conta é criada pelo administrador do
          sistema. Perdeu a senha? Fale com quem lhe entregou o acesso.
        </p>
      </div>
    </main>
  );
}
