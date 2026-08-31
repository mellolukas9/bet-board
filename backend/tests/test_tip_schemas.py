from app.schemas.tip import TipExtracted


def make_extracted(**overrides) -> TipExtracted:
    """Constrói um TipExtracted completo; os campos são obrigatórios no schema."""
    base = {
        "source": "Bet365",
        "event": "Flamengo x Palmeiras",
        "market": "Over 2.5 gols",
        "odd": 1.85,
        "stake": 50.0,
        "currency": "BRL",
        "unreadable_reason": None,
    }
    return TipExtracted(**{**base, **overrides})


def test_complete_extraction_has_no_missing_fields() -> None:
    extracted = make_extracted()

    assert extracted.is_complete
    assert extracted.missing_fields == []


def test_missing_fields_are_listed() -> None:
    extracted = make_extracted(odd=None, stake=None)

    assert not extracted.is_complete
    assert extracted.missing_fields == ["odd", "stake"]


def test_unreadable_print_is_never_complete() -> None:
    # currency não entra em REQUIRED_FIELDS, então sem unreadable_reason este
    # caso seria considerado completo — é a razão de o campo existir.
    extracted = make_extracted(unreadable_reason="Print borrado")

    assert not extracted.is_complete
    assert extracted.missing_fields == []


def test_schema_marks_every_field_required() -> None:
    # Structured outputs pedem que a IA se pronuncie sobre cada campo (com null
    # quando não achou) em vez de omiti-lo.
    schema = TipExtracted.model_json_schema()

    assert set(schema["required"]) == {
        "source",
        "event",
        "market",
        "odd",
        "stake",
        "currency",
        "unreadable_reason",
    }
