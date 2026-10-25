# ADR 0014: Deterministic polyglot runtime bootstrap

- Status: Accepted by NEX-P1-01 candidate
- Date: 2026-10-24

## Context

Phase 0 selected a lightweight polyglot monorepo but intentionally deferred exact
runtime versions, dependency resolution, executable entry points, and containers.
The first implementation stage must close that debt without claiming database,
authentication, integration, worker, or production readiness.

## Decision

Nexora uses one repository with a Next.js web application and one Python package
containing separate FastAPI API and worker composition roots. Node.js 24.22.1,
pnpm 10.34.8, Python 3.13.16, uv 0.13.4, direct dependencies, lockfiles, and base
container images are exact. CI installs from `pnpm-lock.yaml` and `uv.lock` in
frozen mode.

The API exposes only a minimal liveness endpoint. Interactive documentation is
disabled at bootstrap. The worker supports a side-effect-free `--check` command
and refuses execution until the durable job contract is delivered in NEX-P1-05.

## Consequences

- Local development and CI resolve the same dependency graph.
- Web and server can be validated independently without adding an orchestration framework.
- P0 debt `NEX-DEBT-P0-02-001` is closed.
- A successful scaffold build is not a production-readiness claim.
- PostgreSQL, authentication, TRD Bot integration, and durable jobs remain deferred.
