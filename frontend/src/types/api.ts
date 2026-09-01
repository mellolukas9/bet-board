/** Tipos que espelham os schemas Pydantic do backend. */

export type HealthResponse = {
  status: string;
  app: string;
  environment: string;
  /** "up" quando o Postgres respondeu ao SELECT 1 */
  database: "up" | "down";
};

/** `cashout` é o encerramento antecipado: saiu da aposta antes do fim do jogo. */
export type TipStatus = "pending" | "green" | "red" | "void" | "cashout";
export type Channel = "telegram" | "whatsapp";
export type MessageStatus = "sent" | "failed";

/** Uma tentativa de envio em um canal — espelha MessageLogRead. */
export type MessageLogRead = {
  id: number;
  channel: Channel;
  status: MessageStatus;
  sent_at: string | null;
  error: string | null;
};

/**
 * Tip persistida — espelha TipRead.
 *
 * Os numéricos chegam como string: o backend os declara `Decimal`, e o
 * Pydantic serializa Decimal como string para não perder precisão no JSON.
 */
export type TipRead = {
  id: number;
  source: string | null;
  event: string | null;
  market: string | null;
  odd: string | null;
  stake: string | null;
  /** null até o admin informar — a IA nunca preenche */
  stake_units: string | null;
  /** quanto a casa devolveu no encerramento antecipado, em reais */
  cashout_amount: string | null;
  /** o mesmo valor em unidades, na proporção do stake (derivado no backend) */
  cashout_units: string | null;
  currency: string;
  /** link do bilhete na casa; vai na mensagem do grupo */
  link: string | null;
  raw_image_ref: string | null;
  status: TipStatus;
  needs_review: boolean;
  extraction_error: string | null;
  extracted_at: string | null;
  /** null enquanto a tip não foi para o grupo — é o que libera marcar resultado */
  published_at: string | null;
  resolved_at: string | null;
  created_at: string;
  messages: MessageLogRead[];
};

/** Corpo do PATCH /tips/{id} — só o que for enviado é alterado. */
export type TipUpdate = {
  source?: string | null;
  event?: string | null;
  market?: string | null;
  odd?: string | null;
  stake?: string | null;
  stake_units?: string | null;
  currency?: string | null;
  link?: string | null;
  status?: TipStatus;
  needs_review?: boolean;
};

/** Resposta de POST /tips/{id}/publish. */
export type TipPublishResponse = {
  tip: TipRead;
  message: string;
  /** canal -> status; canal que falhou não derruba a requisição */
  channels: Partial<Record<Channel, MessageStatus>>;
};

/** Corpo do POST /tips/{id}/result — o admin diz o resultado. */
export type TipResultBody = {
  status: TipStatus;
  /** obrigatório em `cashout`, recusado nos demais: o valor devolvido, em reais */
  cashout_amount?: string | null;
  note?: string | null;
};

/** Resposta de POST /auth/login. */
export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_at: string;
  username: string;
};

/** A conta logada. */
export type UserRead = {
  id: number;
  username: string;
  name: string | null;
  is_active: boolean;
  /** administra o sistema (cria e desativa contas), não só a banca dele */
  is_superuser: boolean;
  created_at: string;
};

/**
 * Uma banca — a unidade que tem o canal, as tips e a URL pública.
 *
 * O token do bot nunca vem inteiro: só `telegram_bot_token_hint`, com o id do
 * bot e os últimos dígitos, para a pessoa reconhecer qual bot está ali.
 */
export type BankrollRead = {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  is_public: boolean;
  created_at: string;
  telegram_configured: boolean;
  telegram_bot_token_hint: string | null;
  telegram_chat_id: string | null;
  whatsapp_webhook_url: string | null;
};

/** Resposta de GET /auth/me: quem sou eu e quais bancas administro. */
export type MeRead = {
  user: UserRead;
  bankrolls: BankrollRead[];
};

export type BankrollCreate = {
  /** o endereço público sai daqui — não há campo de slug */
  name: string;
  description?: string | null;
  is_public?: boolean;
};

/**
 * Corpo do PATCH /bankrolls/{id}. String vazia num campo de canal apaga o valor.
 *
 * Não há `slug`: o endereço público é derivado do nome, no backend.
 */
export type BankrollUpdate = {
  name?: string;
  description?: string | null;
  is_public?: boolean;
  telegram_bot_token?: string;
  telegram_chat_id?: string;
  whatsapp_webhook_url?: string;
};

/** Resultado do "Testar conexão" do assistente do Telegram. */
export type TelegramDiagnostico = {
  ok: boolean;
  token_valido: boolean;
  bot_username: string | null;
  bot_name: string | null;
  canal_encontrado: boolean;
  canal_titulo: string | null;
  canal_tipo: string | null;
  bot_e_admin: boolean;
  pode_publicar: boolean;
  /** o que falta fazer, em português */
  problemas: string[];
};

export type ChatDetectado = {
  chat_id: string;
  title: string;
  type: string;
};

export type ChatsDetectados = {
  chats: ChatDetectado[];
  /** instrução para quando a lista vem vazia */
  dica: string | null;
};

/** Um dia da curva da banca. */
export type BankrollPoint = {
  date: string;
  bets: number;
  profit_units: string;
  profit_brl: string;
  cumulative_units: string;
  cumulative_brl: string;
};

/**
 * Consolidação da banca (GET /stats).
 *
 * Como em TipRead, os numéricos chegam como string: são Decimal no backend.
 */
export type BankrollStats = {
  bets: number;
  settled: number;
  pending: number;
  green: number;
  red: number;
  void: number;
  /** encerradas antes do fim (cash out) */
  cashout: number;
  needs_review: number;
  staked_units: string;
  staked_brl: string;
  profit_units: string;
  profit_brl: string;
  /** lucro / apostado, em % */
  roi: string;
  /** resolvidas no positivo / resolvidas, em % */
  hit_rate: string;
  series: BankrollPoint[];
};

// --- página pública -----------------------------------------------------------

/** Uma aposta como um assinante do grupo vê: sem valores em reais. */
export type PublicTip = {
  id: number;
  event: string | null;
  market: string | null;
  source: string | null;
  odd: string | null;
  stake_units: string | null;
  /** o que voltou de um encerramento antecipado, em unidades (null nas demais) */
  cashout_units: string | null;
  status: TipStatus;
  created_at: string;
  resolved_at: string | null;
};

export type PublicPoint = {
  date: string;
  bets: number;
  profit_units: string;
  cumulative_units: string;
};

export type PublicStats = {
  bets: number;
  settled: number;
  pending: number;
  green: number;
  red: number;
  void: number;
  cashout: number;
  staked_units: string;
  profit_units: string;
  roi: string;
  hit_rate: string;
  series: PublicPoint[];
};

/** A página pública inteira, numa resposta só. */
export type PublicBankroll = {
  name: string;
  slug: string;
  description: string | null;
  owner_name: string | null;
  since: string | null;
  stats: PublicStats;
  tips: PublicTip[];
};

// --- administração do sistema -------------------------------------------------

/** Uma conta, como o administrador do sistema a vê. */
export type AdminUserRead = UserRead & {
  last_login_at: string | null;
  bankrolls: number;
  tips: number;
};

export type AdminUserCreate = {
  username: string;
  password: string;
  name?: string | null;
  /** cria junto a primeira banca do cliente */
  bankroll_name?: string | null;
  is_superuser?: boolean;
};

export type AdminUserUpdate = {
  name?: string | null;
  is_active?: boolean;
  is_superuser?: boolean;
  password?: string;
};
