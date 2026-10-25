# ADR 0016: Fail-closed runtime configuration and explicit composition

- Status: Frozen by NEX-P1-02
- Date: 2026-10-25

## Context

The frozen runtime foundation created API and worker entry points but left their
settings implicit and hard-coded. The next stage needs one typed configuration
boundary and one explicit composition model before database, authentication,
TRD Bot integration, or durable job adapters can be introduced.

## Decision

Nexora loads only an allowlisted set of non-secret `NEXORA_*` process environment
variables into an immutable Pydantic model. Unknown prefixed variables, blank
values, invalid enum values, unsafe deployment-profile combinations, privileged
ports, and public-internet profiles fail closed. Configuration is not loaded
automatically from dotenv files. Development operators may source an untracked
file explicitly; production secret-file injection remains deferred to NEX-P1-06.

The API and worker use the same loader and `compose_application` factory. The
factory returns a small immutable container containing only validated settings
and non-secret runtime identity. It does not register database, identity,
integration, or job adapters. A deterministic SHA-256 fingerprint is calculated
from the configuration schema and canonical non-secret settings.

## Consequences

- API and worker configuration cannot drift silently.
- Process startup fails before side effects when configuration is invalid.
- The local profile remains loopback-only and production permits only the frozen
  `private_single_host` topology.
- The container is explicit and testable without a global service locator.
- Secrets, database URLs, service tokens, and credentials are not accepted by
  this stage.
- Operational or production readiness is not claimed.
