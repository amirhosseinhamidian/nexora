from __future__ import annotations

import argparse
from collections.abc import Sequence

from nexora import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nexora durable worker composition root")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate that the worker package can start without claiming jobs",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.check:
        print(f"nexora-worker {__version__}: ready for P1-05 durable-job implementation")
        return 0
    raise SystemExit("worker execution is unavailable until NEX-P1-05")


if __name__ == "__main__":
    raise SystemExit(main())
