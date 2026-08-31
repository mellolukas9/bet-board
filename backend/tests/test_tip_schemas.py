from app.schemas.tip import TipExtracted


def make_extracted(**overrides) -> TipExtracted:
    """Constrói um TipExtracted completo; os campos são obrigatórios no schema."""
    base = {
        "source": "Bet365",
        "matches": ["Flamengo x Palmeiras"],
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
        "matches",
        "market",
        "odd",
        "stake",
        "currency",
        "unreadable_reason",
    }


# --- nome do evento, derivado da quantidade de partidas ----------------------


def test_um_jogo_vira_o_nome_do_jogo() -> None:
    assert make_extracted(matches=["Aston Villa x Arsenal"]).event == "Aston Villa x Arsenal"


def test_selecoes_da_mesma_partida_contam_uma_vez() -> None:
    """Múltipla de 3 seleções no mesmo jogo continua sendo aquele jogo."""
    extracted = make_extracted(matches=["Aston Villa x Arsenal"] * 3)

    assert extracted.event == "Aston Villa x Arsenal"


def test_dois_jogos_viram_dupla() -> None:
    assert make_extracted(matches=["A x B", "C x D"]).event == "Dupla"


def test_tres_jogos_viram_tripla() -> None:
    assert make_extracted(matches=["A x B", "C x D", "E x F"]).event == "Tripla"


def test_mais_de_tres_viram_multipla() -> None:
    partidas = ["A x B", "C x D", "E x F", "G x H"]

    assert make_extracted(matches=partidas).event == "Múltipla"


def test_sem_partidas_o_evento_e_nulo() -> None:
    assert make_extracted(matches=None).event is None
    assert make_extracted(matches=[]).event is None
    assert make_extracted(matches=["  "]).event is None


def test_o_evento_sai_na_resposta_da_api() -> None:
    """É `computed_field`: o /tips/preview precisa devolvê-lo."""
    corpo = make_extracted(matches=["A x B", "C x D"]).model_dump()

    assert corpo["event"] == "Dupla"


def test_o_evento_nao_vai_no_schema_mandado_para_a_ia() -> None:
    """Contar partidas é trabalho de código; a IA só lista o que leu."""
    schema = TipExtracted.model_json_schema()

    assert "event" not in schema["properties"]


def test_prefixo_de_bilhete_sai_do_mercado() -> None:
    """O tipo da aposta já é o evento; repetir no mercado duplica na mensagem."""
    for bruto in ("Dupla: X + Y", "Múltipla - X + Y", "TRIPLA — X + Y"):
        assert make_extracted(market=bruto).market == "X + Y"


def test_mercado_sem_prefixo_fica_intacto() -> None:
    assert make_extracted(market="Over 2.5 gols").market == "Over 2.5 gols"
