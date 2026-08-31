/** Cliente HTTP do backend Bet Board. */

import { clearToken, getToken, setToken } from "@/lib/auth";
import type {
  AdminUserCreate,
  AdminUserRead,
  AdminUserUpdate,
  BankrollCreate,
  BankrollRead,
  BankrollStats,
  BankrollUpdate,
  ChatsDetectados,
  MeRead,
  PublicBankroll,
  TelegramDiagnostico,
  HealthResponse,
  TipPublishResponse,
  TipRead,
  TipResultBody,
  TipStatus,
  TipUpdate,
  TokenResponse,
} from "@/types/api";

/** URL usada pelo NAVEGADOR — embutida no bundle em build time. */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * URL usada pelo SERVIDOR Next. No Docker o backend não está em localhost, e sim
 * no host do serviço do Compose — daí a variável separada.
 */
const SERVER_API_BASE_URL =
  process.env.API_BASE_URL_INTERNAL ?? API_BASE_URL;

function baseUrl(): string {
  return typeof window === "undefined" ? SERVER_API_BASE_URL : API_BASE_URL;
}

/**
 * Mensagem para quando o `fetch` estoura antes de haver resposta.
 *
 * As duas causas possíveis são indistinguíveis no navegador, então a mensagem
 * nomeia as duas em vez de afirmar a errada com confiança.
 */
function errorDeRede(): string {
  return (
    `Não foi possível falar com o backend em ${baseUrl()}. ` +
    "Ou ele está fora do ar, ou o endereço deste painel não está liberado no " +
    "CORS_ORIGINS dele."
  );
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Header de autorização, quando há sessão.
 *
 * Toda rota de tips/stats do backend exige o token do login; só `/health` e o
 * próprio `/auth/login` são públicos.
 */
function authHeader(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Sessão vencida: apaga o cookie e recarrega.
 *
 * Quem manda para o `/login` é o `proxy.ts`, ao ver que o cookie sumiu — a
 * regra de "sem sessão, vai para o login" fica num lugar só.
 *
 * Só dispara quando a requisição **levava** um token: um 401 do próprio login é
 * senha errada, e quem mostra isso é o formulário.
 */
function handleExpiredSession(hadToken: boolean): void {
  if (!hadToken || typeof window === "undefined") return;

  clearToken();
  if (window.location.pathname !== "/login") window.location.reload();
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${baseUrl()}${path}`;
  const token = getToken();
  let response: Response;

  try {
    response = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...authHeader(),
        ...init?.headers,
      },
    });
  } catch {
    // O navegador entrega a mesma exceção opaca para rede fora e para resposta
    // bloqueada por CORS — não dá para distinguir daqui. A mensagem cita as
    // duas porque, em produção, CORS mal configurado é de longe a mais comum, e
    // a mensagem antiga mandava procurar o problema no lugar errado.
    throw new ApiError(errorDeRede());
  }

  if (response.status === 401) handleExpiredSession(token !== null);

  if (!response.ok) {
    throw new ApiError(
      (await detailOf(response)) ??
        `${init?.method ?? "GET"} ${path} falhou (${response.status})`,
      response.status,
    );
  }

  // 204 (o DELETE) não tem corpo — tentar parsear estouraria
  if (response.status === 204) return undefined as T;

  return (await response.json()) as T;
}

/**
 * Motivo da recusa, como o FastAPI manda em `detail`.
 *
 * É o que interessa mostrar na tela: no 409 do publish o detail diz exatamente
 * qual campo falta, e no 502 diz o que o provedor de visão respondeu.
 */
async function detailOf(response: Response): Promise<string | null> {
  return response
    .json()
    .then((b) => (typeof b?.detail === "string" ? b.detail : null))
    .catch(() => null);
}

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}

// --- login do admin -----------------------------------------------------------

/** Troca usuário+senha pelo token e já o guarda no cookie. */
export async function login(
  username: string,
  password: string,
): Promise<TokenResponse> {
  const session = await apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

  setToken(session.access_token, session.expires_at);
  return session;
}

/** Quem está logado e quais bancas ele administra. */
export function getMe(): Promise<MeRead> {
  return apiFetch<MeRead>("/auth/me");
}

export function logout(): void {
  clearToken();
}

/**
 * Sobe um print para uma rota que recebe multipart.
 *
 * Não usa `apiFetch` porque multipart não pode ter `Content-Type` fixado à mão —
 * quem monta o boundary é o navegador.
 */
async function postImage<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      body,
      headers: authHeader(),
    });
  } catch {
    throw new ApiError(errorDeRede());
  }

  if (response.status === 401) handleExpiredSession(getToken() !== null);

  if (!response.ok) {
    // o backend manda o motivo em `detail` — é o que interessa ver na tela
    // (chave inválida, quota, formato não suportado…)
    throw new ApiError(
      (await detailOf(response)) ?? `Falha ao ler o print (${response.status})`,
      response.status,
    );
  }

  return (await response.json()) as T;
}

/**
 * Lê o print e **grava** a tip, que nasce em revisão.
 *
 * Print ilegível não vira erro: volta uma tip com `extraction_error` para o
 * admin completar à mão.
 */
export function createTip(bankrollId: number, file: File): Promise<TipRead> {
  return postImage<TipRead>(`/bankrolls/${bankrollId}/tips`, file);
}

/**
 * Lista as tips **de uma banca**.
 *
 * `needsReview` filtra a fila de revisão; `published` é o recorte da banca —
 * só o que foi para o grupo.
 */
export function listTips(
  bankrollId: number,
  options: { needsReview?: boolean; published?: boolean; limit?: number } = {},
): Promise<TipRead[]> {
  const params = new URLSearchParams();
  if (options.needsReview !== undefined) {
    params.set("needs_review", String(options.needsReview));
  }
  if (options.published) params.set("published", "true");
  params.set("limit", String(options.limit ?? 50));

  return apiFetch<TipRead[]>(`/bankrolls/${bankrollId}/tips?${params}`);
}

/** Correção manual — é por aqui que entra o `stake_units`. */
export function patchTip(tipId: number, data: TipUpdate): Promise<TipRead> {
  return apiFetch<TipRead>(`/tips/${tipId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/**
 * Descarta uma tip que não vai ser publicada.
 *
 * Recusa com 409 se ela já foi para o grupo — a mensagem existe fora do banco,
 * e apagar o registro só esconderia o histórico.
 */
export function deleteTip(tipId: number): Promise<void> {
  return apiFetch<void>(`/tips/${tipId}`, { method: "DELETE" });
}

/**
 * Publica a tip nos canais configurados.
 *
 * Recusa com 409 (e o motivo em `detail`) quando falta campo ou a tip já foi
 * publicada. Canal que falha **não** vira erro — vem como `failed` no
 * `channels`.
 *
 * O `force` do backend, que republica, não é usado aqui de propósito: tip
 * enviada é ponto final no painel.
 */
export function publishTip(tipId: number): Promise<TipPublishResponse> {
  return apiFetch<TipPublishResponse>(`/tips/${tipId}/publish`, {
    method: "POST",
    body: JSON.stringify({ force: false }),
  });
}

/**
 * Marca o resultado que o **admin** conferiu.
 *
 * Nesta fase não há API esportiva: green/red/void saem daqui. `pending` desfaz
 * um resultado marcado por engano.
 */
export function setTipResult(
  tipId: number,
  status: TipStatus,
  note?: string,
): Promise<TipRead> {
  const body: TipResultBody = { status, note: note ?? null };
  return apiFetch<TipRead>(`/tips/${tipId}/result`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Consolidação de uma banca: cartões e a série do gráfico. */
export function getStats(
  bankrollId: number,
  options: { since?: string; until?: string } = {},
): Promise<BankrollStats> {
  const params = new URLSearchParams();
  if (options.since) params.set("since", options.since);
  if (options.until) params.set("until", options.until);

  const query = params.toString();
  return apiFetch<BankrollStats>(
    `/bankrolls/${bankrollId}/stats${query ? `?${query}` : ""}`,
  );
}

// --- bancas -------------------------------------------------------------------

export function listBankrolls(): Promise<BankrollRead[]> {
  return apiFetch<BankrollRead[]>("/bankrolls");
}

export function createBankroll(data: BankrollCreate): Promise<BankrollRead> {
  return apiFetch<BankrollRead>("/bankrolls", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Altera a banca. Só o que for enviado muda.
 *
 * Mandar `""` num campo de canal **apaga** o valor — é como o painel
 * desconecta o Telegram.
 */
export function patchBankroll(
  bankrollId: number,
  data: BankrollUpdate,
): Promise<BankrollRead> {
  return apiFetch<BankrollRead>(`/bankrolls/${bankrollId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/** Recusa com 409 enquanto a banca tiver tips. */
export function deleteBankroll(bankrollId: number): Promise<void> {
  return apiFetch<void>(`/bankrolls/${bankrollId}`, { method: "DELETE" });
}

// --- assistente do Telegram ---------------------------------------------------

/**
 * Confere token, canal e permissão de publicar.
 *
 * Sem `credenciais`, testa o que já está salvo — é o "testar de novo" depois de
 * mexer no canal pelo aplicativo.
 */
export function testTelegram(
  bankrollId: number,
  credenciais: { bot_token?: string; chat_id?: string } = {},
): Promise<TelegramDiagnostico> {
  return apiFetch<TelegramDiagnostico>(
    `/bankrolls/${bankrollId}/telegram/test`,
    { method: "POST", body: JSON.stringify(credenciais) },
  );
}

/** Lista os canais que o bot enxerga — é como se descobre o chat_id. */
export function detectTelegramChats(
  bankrollId: number,
  botToken?: string,
): Promise<ChatsDetectados> {
  return apiFetch<ChatsDetectados>(
    `/bankrolls/${bankrollId}/telegram/detect`,
    { method: "POST", body: JSON.stringify({ bot_token: botToken ?? null }) },
  );
}

// --- página pública -----------------------------------------------------------

/** Resultados públicos de uma banca. Não exige login. */
export function getPublicBankroll(slug: string): Promise<PublicBankroll> {
  return apiFetch<PublicBankroll>(`/public/bankrolls/${slug}`);
}

// --- administração do sistema -------------------------------------------------

/**
 * As contas do sistema. Só uma conta administradora enxerga estas rotas — para
 * as demais elas respondem 404, como se não existissem.
 */
export function listAdminUsers(): Promise<AdminUserRead[]> {
  return apiFetch<AdminUserRead[]>("/admin/users");
}

export function createAdminUser(data: AdminUserCreate): Promise<AdminUserRead> {
  return apiFetch<AdminUserRead>("/admin/users", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** Ativa, desativa, promove ou troca a senha de uma conta. */
export function patchAdminUser(
  userId: number,
  data: AdminUserUpdate,
): Promise<AdminUserRead> {
  return apiFetch<AdminUserRead>(`/admin/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/** Recusa com 409 quando a conta ainda tem banca — desativar é o caminho. */
export function deleteAdminUser(userId: number): Promise<void> {
  return apiFetch<void>(`/admin/users/${userId}`, { method: "DELETE" });
}
