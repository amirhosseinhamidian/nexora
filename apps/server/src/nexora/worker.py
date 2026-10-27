from __future__ import annotations

import argparse
import os
import signal
from collections.abc import Mapping, Sequence
from threading import Event
from uuid import UUID

from nexora import __version__
from nexora.composition import compose_application, compose_private_application
from nexora.config import load_settings
from nexora.durable_worker import DurableWorker
from nexora.observability import LOG_FILE_ENV, load_observability_settings
from nexora.trd_bot_sync import EVENT_SYNC_JOB_TYPE, TrdBotSyncHandlers, initial_event_sync_payload

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
    parser.add_argument("--once", action="store_true", help="run one bounded registered synchronization cycle")
    parser.add_argument("--run", action="store_true", help="run bounded cycles until SIGTERM or SIGINT")
    parser.add_argument("--worker-id", help="stable private worker identity used for leases")
    parser.add_argument("--poll-seconds", type=float, default=2.0, help="idle polling interval")
    parser.add_argument("--enqueue-initial-sync", metavar="OWNER_UUID", help="enqueue the initial TRD Bot event sync")
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
    if arguments.once or arguments.run or arguments.enqueue_initial_sync:
        source = os.environ if environ is None else environ
        container = compose_private_application(environ=source)
        try:
            if container.durable_work_repository is None or container.trd_bot_client is None:
                raise SystemExit("private synchronization dependencies are unavailable")
            if arguments.enqueue_initial_sync:
                owner_id = UUID(arguments.enqueue_initial_sync)
                job_id = container.durable_work_repository.enqueue_job(
                    owner_id=owner_id,
                    job_type=EVENT_SYNC_JOB_TYPE,
                    idempotency_key="trd-event-initial-sync-v1",
                    payload=initial_event_sync_payload(),
                )
                print(f"enqueued {job_id}")
                return 0
            if not arguments.worker_id:
                raise SystemExit("--worker-id is required with --once or --run")
            handlers = TrdBotSyncHandlers(container.trd_bot_client)
            worker = DurableWorker(
                container.durable_work_repository,
                handlers.registry(),
                worker_id=arguments.worker_id,
                observer=container.observability,
            )
            if arguments.run:
                stop = Event()

                def request_stop(_: int, __: object) -> None:
                    stop.set()

                signal.signal(signal.SIGTERM, request_stop)
                signal.signal(signal.SIGINT, request_stop)
                summary = worker.run_until_stopped(stop, poll_seconds=arguments.poll_seconds)
                print(
                    f"cycles={summary.cycles} claimed={summary.claimed} "
                    f"succeeded={summary.succeeded} failed={summary.failed}"
                )
                return 1 if summary.failed else 0
            result = worker.run_once()
            print(f"claimed={result.claimed} succeeded={result.succeeded} failed={result.failed}")
            return 1 if result.failed else 0
        finally:
            if container.trd_bot_client is not None:
                container.trd_bot_client.close()
            if container.database_engine is not None:
                container.database_engine.dispose()
    raise SystemExit("no durable job handlers are registered; refusing to claim work")


if __name__ == "__main__":
    raise SystemExit(main())
