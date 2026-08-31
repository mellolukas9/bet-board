"""CLI de apoio ao desenvolvimento.

Uso:
    python -m app.cli extract print1.png print2.jpg
    python -m app.cli extract tests/fixtures/prints/*.png --json
    python -m app.cli create-user --username pecanha --bankroll "Vip Peçanha"
    python -m app.cli create-user --username lucas --superuser
    python -m app.cli list-users
    python -m app.cli promote --username lucas
    python -m app.cli set-password --username pecanha
    python -m app.cli hash-password
"""

import argparse
import getpass
import json
import sys
from pathlib import Path

from app.services.vision import (
    UnsupportedImageError,
    VisionError,
    detect_media_type,
    get_vision_extractor,
)


def _extract_one(extractor, path: Path) -> dict:
    data = path.read_bytes()
    media_type = detect_media_type(data, path.name)
    extracted = extractor.extract(data, media_type)
    return extracted.model_dump()


def cmd_extract(args: argparse.Namespace) -> int:
    try:
        extractor = get_vision_extractor()
    except (VisionError, ValueError) as exc:
        # chave ausente ou VISION_PROVIDER inválido — erro de configuração,
        # não vale despejar traceback em cima do usuário
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2

    results: list[dict] = []
    failures = 0

    for raw_path in args.paths:
        path = Path(raw_path)
        entry: dict = {"file": str(path)}

        if not path.is_file():
            entry["error"] = "arquivo não encontrado"
            failures += 1
        else:
            try:
                entry["tip"] = _extract_one(extractor, path)
            except (VisionError, UnsupportedImageError) as exc:
                entry["error"] = str(exc)
                failures += 1

        results.append(entry)

        if not args.json:
            _print_human(entry)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))

    return 1 if failures else 0


def _print_human(entry: dict) -> None:
    print(f"\n=== {entry['file']} ===")

    if "error" in entry:
        print(f"  ERRO: {entry['error']}")
        return

    tip = entry["tip"]
    if tip.get("unreadable_reason"):
        print(f"  ILEGÍVEL: {tip['unreadable_reason']}")

    for field in ("source", "event", "market", "odd", "stake", "currency"):
        value = tip.get(field)
        marker = " " if value is not None else "!"
        print(f"  {marker} {field:<9} {value if value is not None else '—'}")


def cmd_hash_password(args: argparse.Namespace) -> int:
    """Imprime o hash de uma senha, sem tocar no banco.

    Serve para conferência e para script; quem cria conta é o ``create-user``.
    A senha é pedida pelo ``getpass`` (não aparece na tela nem no histórico do
    shell) a menos que venha em ``--password``.
    """
    # import tardio: a CLI de extração não deve carregar config de auth à toa
    from app.core.security import hash_password

    senha = _pedir_senha(args)
    if senha is None:
        return 2

    print(hash_password(senha))
    return 0


def _pedir_senha(args: argparse.Namespace) -> str | None:
    """Senha por ``getpass``, com confirmação. ``None`` quando desiste."""
    if args.password:
        return args.password

    senha = getpass.getpass("Senha: ")
    if not senha:
        print("ERRO: senha vazia.", file=sys.stderr)
        return None
    if senha != getpass.getpass("Confirme: "):
        print("ERRO: as senhas não conferem.", file=sys.stderr)
        return None
    return senha


def cmd_create_user(args: argparse.Namespace) -> int:
    """Cria a conta de um cliente e, se pedido, a primeira banca dele.

    Não há cadastro aberto: contas nascem aqui e você entrega usuário e senha.
    """
    from app.db.session import SessionLocal
    from app.services import bankrolls as bankrolls_service
    from app.services import users as users_service

    senha = _pedir_senha(args)
    if senha is None:
        return 2

    with SessionLocal() as session:
        try:
            user = users_service.create_user(
                session, username=args.username, password=senha, name=args.name
            )
        except users_service.UsernameTaken as exc:
            print(f"ERRO: {exc}", file=sys.stderr)
            return 2

        user.is_superuser = bool(args.superuser)

        banca = None
        if args.bankroll:
            banca = bankrolls_service.create_bankroll(session, user, name=args.bankroll)

        session.commit()

        papel = " (administrador do sistema)" if user.is_superuser else ""
        print(f"Conta criada: {user.username}{papel} (id {user.id})")
        if banca is not None:
            print(f"Banca criada: {banca.name} — endereço público /b/{banca.slug}")
        else:
            print("Sem banca ainda: a pessoa cria a primeira pelo painel.")

    return 0


def cmd_list_users(args: argparse.Namespace) -> int:
    """Lista as contas e as bancas de cada uma."""
    from app.db.session import SessionLocal
    from app.services import users as users_service

    with SessionLocal() as session:
        contas = users_service.list_users(session)

        if not contas:
            print("Nenhuma conta ainda. Crie uma com: python -m app.cli create-user")
            return 0

        for user in contas:
            marcas = []
            if user.is_superuser:
                marcas.append("admin do sistema")
            if not user.is_active:
                marcas.append("desativada")
            sufixo = f"  ({', '.join(marcas)})" if marcas else ""
            print(f"#{user.id} {user.username}{sufixo}")
            for banca in user.bankrolls:
                canal = "telegram ok" if banca.telegram_configured else "sem canal"
                visivel = "pública" if banca.is_public else "privada"
                print(f"    /b/{banca.slug}  {banca.name}  [{visivel}, {canal}]")

    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    """Promove uma conta existente a administradora do sistema."""
    from app.db.session import SessionLocal
    from app.services import users as users_service

    with SessionLocal() as session:
        user = users_service.get_by_username(session, args.username)
        if user is None:
            print(f"ERRO: conta {args.username!r} não existe.", file=sys.stderr)
            return 2

        if user.is_superuser:
            print(f"{user.username} já é administrador do sistema.")
            return 0

        user.is_superuser = True
        session.commit()
        print(f"{user.username} agora administra o sistema.")

    return 0


def cmd_set_password(args: argparse.Namespace) -> int:
    """Troca a senha de uma conta — o caminho de "esqueci a senha"."""
    from app.db.session import SessionLocal
    from app.services import users as users_service

    senha = _pedir_senha(args)
    if senha is None:
        return 2

    with SessionLocal() as session:
        user = users_service.get_by_username(session, args.username)
        if user is None:
            print(f"ERRO: conta {args.username!r} não existe.", file=sys.stderr)
            return 2

        users_service.set_password(session, user, senha)
        session.commit()
        print(f"Senha trocada para {user.username}.")

    return 0


SENHA_INLINE_HELP = (
    "Senha em texto puro (evite: fica no histórico do shell). Sem isto, pergunta."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli", description="Ferramentas do Bet Board")
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract", help="Lê prints de tips e mostra o resultado")
    extract.add_argument("paths", nargs="+", help="Caminhos dos prints")
    extract.add_argument("--json", action="store_true", help="Saída em JSON")
    extract.set_defaults(func=cmd_extract)

    criar = sub.add_parser("create-user", help="Cria a conta de um cliente")
    criar.add_argument("--username", required=True, help="Usuário do login")
    criar.add_argument("--name", help="Nome da pessoa, só para exibição")
    criar.add_argument("--bankroll", help="Cria também a primeira banca com este nome")
    criar.add_argument(
        "--superuser",
        action="store_true",
        help="Conta de administrador do sistema (cria e desativa outras contas)",
    )
    criar.add_argument("--password", help=SENHA_INLINE_HELP)
    criar.set_defaults(func=cmd_create_user)

    listar = sub.add_parser("list-users", help="Lista as contas e as bancas de cada uma")
    listar.set_defaults(func=cmd_list_users)

    promover = sub.add_parser(
        "promote", help="Torna uma conta administradora do sistema"
    )
    promover.add_argument("--username", required=True)
    promover.set_defaults(func=cmd_promote)

    trocar = sub.add_parser("set-password", help="Troca a senha de uma conta")
    trocar.add_argument("--username", required=True)
    trocar.add_argument("--password", help=SENHA_INLINE_HELP)
    trocar.set_defaults(func=cmd_set_password)

    hash_cmd = sub.add_parser("hash-password", help="Só imprime o hash de uma senha")
    hash_cmd.add_argument("--password", help=SENHA_INLINE_HELP)
    hash_cmd.set_defaults(func=cmd_hash_password)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
