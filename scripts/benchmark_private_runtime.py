#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import ssl
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit


def private_origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise argparse.ArgumentTypeError("base URL must be a credential-free HTTPS origin")
    if not parsed.hostname or parsed.path not in {"", "/"}:
        raise argparse.ArgumentTypeError("base URL must not include a path")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError as error:
        raise argparse.ArgumentTypeError("base URL host must be a literal private-overlay address") from error
    carrier_grade_nat = address in ipaddress.ip_network("100.64.0.0/10")
    if address.is_unspecified or address.is_multicast or address.is_reserved:
        raise argparse.ArgumentTypeError("base URL cannot target an unspecified or reserved address")
    if not (address.is_private or address.is_loopback or carrier_grade_nat):
        raise argparse.ArgumentTypeError("base URL cannot target a public address")
    return value.rstrip("/")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Nexora private overload smoke benchmark")
    value.add_argument("--base-url", required=True, type=private_origin)
    value.add_argument("--ca-file", required=True, type=Path)
    value.add_argument("--requests", type=int, default=100)
    value.add_argument("--concurrency", type=int, default=25)
    value.add_argument("--environment-label", required=True)
    value.add_argument("--output", required=True, type=Path)
    return value


def main() -> int:
    arguments = parser().parse_args()
    if arguments.requests < 26 or arguments.requests > 10_000:
        raise SystemExit("--requests must be between 26 and 10000")
    if arguments.concurrency < 2 or arguments.concurrency > 100:
        raise SystemExit("--concurrency must be between 2 and 100")
    if not arguments.environment_label.strip() or len(arguments.environment_label) > 80:
        raise SystemExit("--environment-label must contain 1 to 80 characters")
    if not arguments.ca_file.is_absolute() or arguments.ca_file.is_symlink() or not arguments.ca_file.is_file():
        raise SystemExit("--ca-file must be an absolute regular non-symbolic file")
    commit_sha = os.environ.get("SOURCE_COMMIT_SHA", "")
    if len(commit_sha) != 40 or any(character not in "0123456789abcdef" for character in commit_sha):
        raise SystemExit("SOURCE_COMMIT_SHA must identify the deployed candidate")
    context = ssl.create_default_context(cafile=str(arguments.ca_file))
    target = f"{arguments.base_url}/v1/session"

    def request_once(_: int) -> tuple[int, float, bool]:
        started = time.perf_counter()
        status = 0
        retry_after = False
        try:
            with urllib.request.urlopen(target, timeout=10, context=context) as response:
                status = response.status
                retry_after = response.headers.get("Retry-After") is not None
        except urllib.error.HTTPError as error:
            status = error.code
            retry_after = error.headers.get("Retry-After") is not None
        except (OSError, TimeoutError, urllib.error.URLError):
            status = 0
        return status, (time.perf_counter() - started) * 1000, retry_after

    samples: list[tuple[int, float, bool]] = []
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=arguments.concurrency) as executor:
        futures = [executor.submit(request_once, index) for index in range(arguments.requests)]
        for future in as_completed(futures):
            samples.append(future.result())
    duration = time.perf_counter() - started
    statuses: dict[str, int] = {}
    for status, _, _ in samples:
        statuses[str(status)] = statuses.get(str(status), 0) + 1
    latencies = sorted(sample[1] for sample in samples)
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)]
    throughput = len(samples) / duration
    rate_limited = [sample for sample in samples if sample[0] == 429]
    failures: list[str] = []
    if not rate_limited:
        failures.append("overload_did_not_produce_429")
    if any(not sample[2] for sample in rate_limited):
        failures.append("retry_after_missing")
    if any(sample[0] >= 500 or sample[0] == 0 for sample in samples):
        failures.append("server_or_transport_failure")
    if p95 > 300:
        failures.append("non_export_api_p95_budget_exceeded")
    if throughput < 10:
        failures.append("sustained_throughput_budget_missed")
    report: dict[str, object] = {
        "schema_version": "nexora-private-runtime-benchmark-v1",
        "candidate_commit_sha": commit_sha,
        "environment_label": arguments.environment_label,
        "generated_at": datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "target_origin": arguments.base_url,
        "requested_samples": arguments.requests,
        "completed_samples": len(samples),
        "concurrency": arguments.concurrency,
        "status_counts": statuses,
        "retry_after_present_on_all_429": bool(rate_limited) and all(sample[2] for sample in rate_limited),
        "duration_seconds": round(duration, 6),
        "throughput_per_second": round(throughput, 6),
        "minimum_throughput_per_second": 10,
        "latency_p50_ms": round(statistics.median(latencies), 6),
        "latency_p95_ms": round(p95, 6),
        "latency_p95_budget_ms": 300,
        "immutable_evidence_dropped": False,
        "failure_reasons": failures,
        "passed": not failures,
    }
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["report_checksum"] = hashlib.sha256(encoded).hexdigest()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
