"""Testes do template da mensagem — formatação pura, sem IA nem rede."""

from decimal import Decimal

import pytest

from app.schemas.tip import TipExtracted
from app.services.messaging.formatter import (
    format_money,
    format_odd,
    format_tip_message,
    format_units,
)

COMPLETE = TipExtracted(
    source="bet365",
    matches=["Flamengo x Palmeiras"],
    market="Mais de 2.5 gols",
    odd=1.85,
    stake=150.0,
    currency="BRL",
    unreadable_reason=None,
)


def test_money_uses_brazilian_format() -> None:
    assert format_money(150.0, "BRL") == "R$ 150,00"
    assert format_money(1234.5, "BRL") == "R$ 1.234,50"
    assert format_money(1234567.89, "BRL") == "R$ 1.234.567,89"


def test_money_without_known_currency_omits_the_symbol() -> None:
    assert format_money(50.0, None) == "50,00"
    assert format_money(50.0, "XYZ") == "50,00"


def test_odd_always_has_two_decimals_with_comma() -> None:
    assert format_odd(1.85) == "1,85"
    assert format_odd(2.0) == "2,00"
    assert format_odd(1.5) == "1,50"


def test_complete_tip_renders_every_line() -> None:
    message = format_tip_message(COMPLETE)

    assert "Flamengo x Palmeiras" in message
    assert "Mais de 2.5 gols" in message
    assert "1,85" in message
    assert "R$ 150,00" in message
    assert "bet365" in message


def test_missing_fields_are_omitted_not_printed_as_none() -> None:
    partial = COMPLETE.model_copy(update={"stake": None, "source": None})

    message = format_tip_message(partial)

    assert "None" not in message
    assert "Stake" not in message
    assert "bet365" not in message
    # o que sobrou continua lá
    assert "Flamengo x Palmeiras" in message
    assert "1,85" in message


def test_message_is_deterministic() -> None:
    assert format_tip_message(COMPLETE) == format_tip_message(COMPLETE)


# --- stake em unidades (decisao de 27/08) ------------------------------------


@pytest.mark.parametrize(
    ("units", "esperado"),
    [
        ("2", "2u"),
        ("2.00", "2u"),
        ("1.5", "1,5u"),
        ("0.5", "0,5u"),
        ("0.25", "0,25u"),
        ("10", "10u"),
    ],
)
def test_units_drop_the_decimal_when_it_is_zero(units: str, esperado: str) -> None:
    assert format_units(Decimal(units)) == esperado


def test_units_replace_the_amount_in_reais() -> None:
    """O grupo aposta em unidades; o valor do print nao vai para a mensagem."""
    message = format_tip_message(COMPLETE, stake_units=Decimal("2"))

    assert "Stake: 2u" in message
    assert "R$" not in message


def test_without_units_the_message_falls_back_to_the_amount_read() -> None:
    message = format_tip_message(COMPLETE, stake_units=None)

    assert "R$ 150,00" in message
    linha_do_stake = message.split("Stake: ")[1].splitlines()[0]
    assert "u" not in linha_do_stake
