from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence

from nexora import __version__
from nexora.composition import compose_application
from nexora.config import load_settings

# Frozen P1-01 evidence marker: "worker execution is unavailable until NEX-P1-05".
# P1-05 replaces that temporary boundary with the injected DurableWorker engine;
# this composition root still refuses to claim work without an explicit handler registry.


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nexora durable worker composition root")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate that the worker package can start without claiming jobs",
    )
    return parser


def main(argv: Sequence[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.check:
        container = compose_application(load_settings(environ))
        print(
            f"nexora-worker {__version__}: configuration "
            f"{container.identity.configuration_checksum}; durable-job engine ready"
        )
        return 0
    raise SystemExit("no durable job handlers are registered; refusing to claim work")


if __name__ == "__main__":
    raise SystemExit(main())
