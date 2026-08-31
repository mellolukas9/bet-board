"""Bancas: a unidade que tem o canal, as tips e a página pública."""

import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.tip import Tip
from app.models.user import Bankroll, User

logger = get_logger(__name__)

#: Reservado para as rotas do próprio painel — uma banca em /b/login criaria uma
#: ambiguidade que não vale a pena carregar.
SLUGS_RESERVADOS = frozenset(
    {"api", "admin", "login", "logout", "banca", "bancas", "b", "p", "public", "static", "health"}
)

SLUG_MIN = 3
SLUG_MAX = 64


class SlugEmUso(ValueError):
    """Não sobrou endereço livre a partir desse nome."""


def create_bankroll(
    session: Session,
    owner: User,
    *,
    name: str,
    description: str | None = None,
    is_public: bool = False,
) -> Bankroll:
    """Cria a banca. O endereço público sai do nome, sempre."""
    bankroll = Bankroll(
        user_id=owner.id,
        name=name.strip(),
        slug=_slug_livre(session, slugify(name) or "banca"),
        description=description,
        is_public=is_public,
    )
    session.add(bankroll)
    session.flush()

    logger.info(
        "bankrolls.created",
        extra={"bankroll_id": bankroll.id, "user_id": owner.id, "slug": bankroll.slug},
    )
    return bankroll


def list_for_user(session: Session, user: User) -> list[Bankroll]:
    stmt = select(Bankroll).where(Bankroll.user_id == user.id).order_by(Bankroll.id)
    return list(session.scalars(stmt))


def get(session: Session, bankroll_id: int) -> Bankroll | None:
    return session.get(Bankroll, bankroll_id)


def get_by_slug(session: Session, slug: str) -> Bankroll | None:
    stmt = select(Bankroll).where(Bankroll.slug == slug.strip().lower())
    return session.scalars(stmt).one_or_none()


def update_bankroll(session: Session, bankroll: Bankroll, changes: dict) -> Bankroll:
    """Aplica só os campos enviados.

    Renomear a banca **muda o endereço público junto** — é o que mantém o
    ``/b/<slug>`` sempre igual ao nome que aparece na tela. O preço é conhecido
    e está avisado no painel: o link antigo deixa de funcionar.
    """
    for field, value in changes.items():
        setattr(bankroll, field, value)

    if "name" in changes:
        bankroll.slug = _slug_livre(
            session, slugify(bankroll.name) or "banca", atual=bankroll
        )

    session.flush()
    logger.info(
        "bankrolls.updated",
        extra={"bankroll_id": bankroll.id, "fields": sorted(changes)},
    )
    return bankroll


def delete_bankroll(session: Session, bankroll: Bankroll) -> None:
    """Apaga a banca e, por cascade, todas as tips dela."""
    bankroll_id = bankroll.id
    session.delete(bankroll)
    session.flush()
    logger.info("bankrolls.deleted", extra={"bankroll_id": bankroll_id})


def count_tips(session: Session, bankroll: Bankroll) -> int:
    stmt = select(func.count()).select_from(Tip).where(Tip.bankroll_id == bankroll.id)
    return session.scalar(stmt) or 0


# --- endereço público ---------------------------------------------------------


def slugify(texto: str) -> str:
    """"Vip Peçanha" → "vip-pecanha"."""
    sem_acento = (
        unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    )
    limpo = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-").lower()
    return limpo[:SLUG_MAX].strip("-")


def _slug_livre(session: Session, base: str, *, atual: Bankroll | None = None) -> str:
    """Primeiro endereço livre a partir da base: ``vip``, ``vip-2``, ``vip-3``…

    O desempate por sufixo existe porque o nome é escolha do cliente e dois
    clientes podem chamar a banca de "VIP" — mas o endereço é único no sistema
    inteiro. ``atual`` deixa a banca manter o endereço que já é dela.
    """
    base = base[: SLUG_MAX - 4] or "banca"
    if len(base) < SLUG_MIN:
        base = f"{base}-banca"

    candidato = base
    for n in range(2, 1000):
        if candidato not in SLUGS_RESERVADOS:
            dono = get_by_slug(session, candidato)
            if dono is None or (atual is not None and dono.id == atual.id):
                return candidato
        candidato = f"{base}-{n}"

    # 998 bancas com o mesmo nome no sistema: não é um caso real, mas deixar
    # o laço terminar em silêncio devolveria um endereço já tomado
    raise SlugEmUso("Não consegui derivar um endereço livre a partir desse nome.")
