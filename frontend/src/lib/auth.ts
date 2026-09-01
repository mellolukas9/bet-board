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

/** Os dois prazos de uma sessão, em milissegundos desde a época. */
export type PrazoDaSessao = {
  /** quando o token deixa de valer, se ninguém renovar */
  expiraEm: number;
  /** de quanto é a janela inteira — é o backend que decide, não o painel */
  janelaMs: number;
};

/**
 * Lê os prazos do próprio token.
 *
 * O corpo de um JWT é base64, não é segredo: quem tem o token já sabe tudo o
 * que está escrito nele. Ler daqui evita guardar a validade num segundo lugar,
 * que sairia de sincronia com o token na primeira renovação.
 *
 * `null` quando o token não é um JWT legível — aí quem manda é o servidor, que
 * vai recusá-lo no próximo pedido.
 */
export function prazoDaSessao(token: string): PrazoDaSessao | null {
  try {
    const corpo = token.split(".")[1];
    if (!corpo) return null;

    const json = atob(corpo.replace(/-/g, "+").replace(/_/g, "/"));
    const { exp, iat } = JSON.parse(json) as { exp?: number; iat?: number };
    if (typeof exp !== "number") return null;

    return {
      expiraEm: exp * 1000,
      // sem `iat` (token antigo), assume a janela cheia a partir de agora
      janelaMs: typeof iat === "number" ? (exp - iat) * 1000 : exp * 1000 - Date.now(),
    };
  } catch {
    return null;
  }
}
