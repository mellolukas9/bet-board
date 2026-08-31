"""Diagnóstico da configuração do Telegram.

Existe para o cliente conseguir se virar sozinho. Configurar um bot de canal tem
três armadilhas conhecidas, e cada uma dá um erro diferente e nada óbvio:

1. token errado → ``401 Unauthorized``
2. bot fora do canal, ou chat_id errado → ``400 chat not found``
3. bot dentro do canal mas sem ser admin → ``400 need administrator rights``

Em vez de deixar o cliente descobrir isso no primeiro envio (quando a tip já
devia ter saído), o painel pergunta ao Telegram **antes** e diz em português o
que falta fazer.

O ``detect_chats`` resolve a pior parte: achar o ``chat_id`` de um canal
privado, que não tem @nome e não aparece em lugar nenhum da interface.
"""

from dataclasses import dataclass, field

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

API_BASE = "https://api.telegram.org"
TIMEOUT_SECONDS = 15.0

#: Status de membro que permitem publicar num canal.
_STATUS_QUE_PUBLICA = ("creator", "administrator")


class TelegramSetupError(RuntimeError):
    """Não deu para falar com o Telegram (rede, timeout)."""


@dataclass
class ChatEncontrado:
    """Um canal/grupo que o bot enxerga."""

    chat_id: str
    title: str
    type: str


@dataclass
class Diagnostico:
    """O que o painel mostra depois de "Testar conexão"."""

    #: tudo certo: dá para publicar agora
    ok: bool = False

    token_valido: bool = False
    bot_username: str | None = None
    bot_name: str | None = None

    canal_encontrado: bool = False
    canal_titulo: str | None = None
    canal_tipo: str | None = None

    bot_e_admin: bool = False
    pode_publicar: bool = False

    #: o que falta fazer, em português, na ordem de resolver
    problemas: list[str] = field(default_factory=list)


def check_token(token: str, *, client: httpx.Client | None = None) -> Diagnostico:
    """Confere só o token (``getMe``). É o passo 1 do assistente."""
    diagnostico = Diagnostico()

    resposta = _call(token, "getMe", client=client)
    if not resposta.ok:
        diagnostico.problemas.append(
            "O token não foi aceito pelo Telegram. Confira se você copiou a linha "
            "inteira que o @BotFather mandou, sem espaços."
        )
        return diagnostico

    bot = resposta.result
    diagnostico.token_valido = True
    diagnostico.bot_username = bot.get("username")
    diagnostico.bot_name = bot.get("first_name")
    return diagnostico


def diagnose(
    token: str | None,
    chat_id: str | None,
    *,
    client: httpx.Client | None = None,
) -> Diagnostico:
    """Confere token, canal e permissão de publicar, nessa ordem.

    Para de descer assim que um passo falha: sem token válido não dá para
    perguntar nada sobre o canal, e a mensagem do passo seguinte só confundiria.
    """
    if not token:
        return Diagnostico(problemas=["Falta o token do bot."])

    diagnostico = check_token(token, client=client)
    if not diagnostico.token_valido:
        return diagnostico

    if not chat_id:
        diagnostico.problemas.append(
            "Falta o canal. Adicione o bot ao canal como administrador, mande "
            "qualquer mensagem lá e clique em Detectar canais."
        )
        return diagnostico

    chat = _call(token, "getChat", params={"chat_id": chat_id}, client=client)
    if not chat.ok:
        diagnostico.problemas.append(
            f"O Telegram não achou esse canal ({chat.description}). Confira se o "
            f"@{diagnostico.bot_username} já foi adicionado ao canal — enquanto "
            "ele estiver de fora, o canal não existe para ele."
        )
        return diagnostico

    diagnostico.canal_encontrado = True
    diagnostico.canal_titulo = chat.result.get("title") or chat.result.get("username")
    diagnostico.canal_tipo = chat.result.get("type")

    membro = _call(
        token,
        "getChatMember",
        params={"chat_id": chat_id, "user_id": _bot_id(token)},
        client=client,
    )
    if not membro.ok:
        diagnostico.problemas.append(
            f"Não consegui conferir a permissão do bot no canal ({membro.description})."
        )
        return diagnostico

    status = membro.result.get("status")
    diagnostico.bot_e_admin = status in _STATUS_QUE_PUBLICA
    # can_post_messages só aparece em canal; em grupo, ser admin já basta
    diagnostico.pode_publicar = diagnostico.bot_e_admin and (
        membro.result.get("can_post_messages", True) is not False
    )

    if not diagnostico.bot_e_admin:
        diagnostico.problemas.append(
            f"O bot está no canal, mas como membro comum — e em canal só "
            f"administrador publica. Abra o canal → Administradores → Adicionar "
            f"administrador → @{diagnostico.bot_username}."
        )
    elif not diagnostico.pode_publicar:
        diagnostico.problemas.append(
            "O bot é administrador, mas está sem a permissão "
            '"Publicar mensagens". Ligue essa opção nas permissões dele.'
        )

    diagnostico.ok = not diagnostico.problemas
    return diagnostico


def detect_chats(token: str, *, client: httpx.Client | None = None) -> list[ChatEncontrado]:
    """Lista os canais/grupos que o bot enxergou nas últimas mensagens.

    É o jeito de descobrir o ``chat_id`` de um **canal privado**, que não tem
    @nome e não mostra o id em lugar nenhum do aplicativo. O Telegram só conta o
    que passou pelo ``getUpdates``, então a instrução para o cliente é: adicione
    o bot, mande uma mensagem qualquer no canal, e só então clique em detectar.

    Raises:
        TelegramSetupError: o token não foi aceito.
    """
    resposta = _call(token, "getUpdates", params={"limit": 100}, client=client)
    if not resposta.ok:
        raise TelegramSetupError(
            f"O Telegram recusou o token ao listar as conversas: {resposta.description}"
        )

    encontrados: dict[str, ChatEncontrado] = {}

    for update in resposta.results:
        for chave in ("channel_post", "message", "edited_channel_post", "my_chat_member"):
            chat = (update.get(chave) or {}).get("chat")
            if not chat:
                continue

            chat_id = str(chat.get("id"))
            # conversa direta com uma pessoa não é destino de tip
            if chat.get("type") == "private":
                continue

            encontrados.setdefault(
                chat_id,
                ChatEncontrado(
                    chat_id=chat_id,
                    title=chat.get("title") or chat.get("username") or chat_id,
                    type=chat.get("type", "desconhecido"),
                ),
            )

    return list(encontrados.values())


# --- chamada crua -------------------------------------------------------------


@dataclass
class _Resposta:
    ok: bool
    result: dict
    results: list[dict]
    description: str


def _call(
    token: str,
    method: str,
    *,
    params: dict | None = None,
    client: httpx.Client | None = None,
) -> _Resposta:
    """Chama a Bot API. Recusa do Telegram **não** é exceção — é resposta.

    Um token errado ou um canal inexistente são justamente o que estamos
    diagnosticando; virar exceção obrigaria o chamador a tratar como erro o
    caminho normal desta função.

    Raises:
        TelegramSetupError: falha de rede ou timeout.
    """
    url = f"{API_BASE}/bot{token}/{method}"

    try:
        if client is not None:
            response = client.get(url, params=params)
        else:
            with httpx.Client(timeout=TIMEOUT_SECONDS) as http:
                response = http.get(url, params=params)
    except httpx.HTTPError as exc:
        raise TelegramSetupError(f"Falha de rede ao falar com o Telegram: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        return _Resposta(False, {}, [], f"resposta inesperada do Telegram ({response.status_code})")

    resultado = body.get("result")
    return _Resposta(
        ok=bool(body.get("ok")),
        result=resultado if isinstance(resultado, dict) else {},
        results=resultado if isinstance(resultado, list) else [],
        description=str(body.get("description", "sem detalhe")),
    )


def _bot_id(token: str) -> str:
    """O id do bot é o pedaço antes dos dois-pontos do token — sem ida à rede."""
    return token.split(":", 1)[0]
