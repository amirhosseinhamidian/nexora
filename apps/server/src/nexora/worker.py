from __future__ import annotations

import argparse
import os
from collections.abc import Mapping, Sequence

from nexora import __version__
from nexora.composition import compose_application
from nexora.config import load_settings
from nexora.observability import LOG_FILE_ENV, load_observability_settings

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
        source = os.environ if environ is None else environ
        settings = load_settings(source, permitted_external_variables=frozenset({LOG_FILE_ENV}))
        observability_settings = load_observability_settings(
            source,
            production=settings.environment.value == "production",
        )
        if observability_settings.log_file is None:
            container = compose_application(load_settings(environ))
        else:
            container = compose_application(settings, observability_settings=observability_settings)
        print(
            f"nexora-worker {__version__}: configuration "
            f"{container.identity.configuration_checksum}; durable-job engine ready"
        )
        return 0
    raise SystemExit("no durable job handlers are registered; refusing to claim work")


if __name__ == "__main__":
    raise SystemExit(main())
