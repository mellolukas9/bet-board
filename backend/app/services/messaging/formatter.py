"""Template único da mensagem da tip (Fase 1.3).

Formatação pura: recebe a tip lida do print e devolve o texto que vai para o
Telegram/WhatsApp. Sem IA, sem I/O — o mesmo dado gera sempre a mesma mensagem.
"""

from decimal import Decimal

from app.schemas.tip import TipExtracted

_CURRENCY_SYMBOLS = {
    "BRL": "R$",
    "USD": "US$",
    "EUR": "€",
}


def format_money(value: float | Decimal, currency: str | None) -> str:
    """Formata no padrão brasileiro: 1234.5 + BRL -> 'R$ 1.234,50'."""
    inteiro, _, decimal = f"{Decimal(str(value)):,.2f}".partition(".")
    # ',' vira separador de milhar e '.' vira decimal — troca em duas etapas
    inteiro = inteiro.replace(",", ".")
    valor = f"{inteiro},{decimal}"

    symbol = _CURRENCY_SYMBOLS.get((currency or "").upper())
    return f"{symbol} {valor}" if symbol else valor


def format_odd(odd: float | Decimal) -> str:
    """Odd sempre com duas casas, vírgula decimal: 1.85 -> '1,85'."""
    return f"{Decimal(str(odd)):.2f}".replace(".", ",")


def format_units(units: float | Decimal) -> str:
    """Unidades sem casa decimal à toa: 2 -> '2u', 1.5 -> '1,5u', 0.5 -> '0,5u'."""
    valor = Decimal(str(units)).normalize()
    # normalize() vira notação científica em inteiros grandes (2E+1); quantize desfaz
    if valor == valor.to_integral_value():
        valor = valor.quantize(Decimal("1"))
    return f"{valor}u".replace(".", ",")


def format_tip_message(
    tip: TipExtracted,
    *,
    stake_units: float | Decimal | None = None,
    link: str | None = None,
) -> str:
    """Monta a mensagem padrão da tip.

    Campos que a IA não achou são simplesmente omitidos — a mensagem sai com o
    que existe, em vez de estampar "None" no grupo.

    O grupo trabalha em unidades, então ``stake_units`` (informado pelo admin na
    revisão) manda no stake. Sem ele a mensagem cai no valor em reais lido do
    print — é o que o ``/tips/preview`` mostra, antes de existir a revisão.

    ``link`` é o bilhete na casa de apostas, quando o admin informou: com ele o
    assinante abre a mesma aposta em vez de remontá-la campo a campo.
    """
    linhas = ["🎯 *NOVA TIP*", ""]

    if tip.event:
        linhas.append(f"⚽ {tip.event}")
    if tip.market:
        linhas.append(f"📊 {tip.market}")
    if tip.odd is not None:
        linhas.append(f"📈 Odd: *{format_odd(tip.odd)}*")
    if stake_units is not None:
        linhas.append(f"💰 Stake: {format_units(stake_units)}")
    elif tip.stake is not None:
        linhas.append(f"💰 Stake: {format_money(tip.stake, tip.currency)}")
    if tip.source:
        linhas.append(f"🏠 {tip.source}")
    if link:
        linhas.extend(["", f"🔗 Entrar na aposta: {link}"])

    linhas.extend(["", "🍀 Boa sorte!"])
    return "\n".join(linhas)
