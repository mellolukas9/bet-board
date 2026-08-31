/**
 * Sessão do admin no navegador.
 *
 * O token vai num cookie (não em `localStorage`) por um motivo só: o
 * `middleware.ts` roda no servidor e precisa enxergá-lo para mandar quem não
 * está logado para `/login` antes de a página renderizar. Não é `httpOnly`
 * porque o próprio cliente monta o header `Authorization` — quem valida o token
 * é o backend, o cookie aqui é só onde ele fica guardado.
 */

export const TOKEN_COOKIE = "bb_token";

/** Lê o token do cookie. `null` no servidor ou quando não há sessão. */
export function getToken(): string | null {
  if (typeof document === "undefined") return null;

  const match = document.cookie.match(
    new RegExp(`(?:^|; )${TOKEN_COOKIE}=([^;]*)`),
  );
  return match ? decodeURIComponent(match[1]) : null;
}

/** Guarda o token até a data em que o backend disse que ele expira. */
export function setToken(token: string, expiresAt: string): void {
  const expires = new Date(expiresAt);
  // data inválida (backend antigo, relógio torto): cai em cookie de sessão
  const attrs = Number.isNaN(expires.getTime())
    ? ""
    : `; expires=${expires.toUTCString()}`;

  document.cookie = `${TOKEN_COOKIE}=${encodeURIComponent(token)}; path=/${attrs}; SameSite=Lax`;
}

export function clearToken(): void {
  document.cookie = `${TOKEN_COOKIE}=; path=/; max-age=0; SameSite=Lax`;
}
