from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from nexora.composition import compose_private_application


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nexora local single-owner identity operator")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser(
        "create-bootstrap-token",
        help="print one 256-bit token that expires in ten minutes and can be used once",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    container = compose_private_application(environ=os.environ)
    try:
        service = container.owner_identity_service
        if service is None:
            raise RuntimeError("private identity runtime was not composed")
        if arguments.command == "create-bootstrap-token":
            print(service.create_local_bootstrap_token())
            return 0
        raise RuntimeError("unknown identity operator command")
    finally:
        if container.database_engine is not None:
            container.database_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
