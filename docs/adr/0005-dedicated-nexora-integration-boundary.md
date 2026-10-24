# ADR 0005: Dedicated Nexora integration boundary

Status: **Accepted and frozen by NEX-P0-03**

## Context

TRD Bot `0.3.0` exposes useful research, alert, decision, risk and Paper/Shadow
portfolio reads. Those endpoints were designed for its own UI, however, and do
not provide one capability handshake, one versioned envelope, a cursor event
feed, a general export bundle, or an idempotent Nexora command boundary.

Direct access to the TRD Bot database would couple Nexora to private tables,
bypass API security, and make independent upgrades unsafe.

## Decision

TRD Bot `0.3.1+` will expose an additive boundary under
`/api/v1/integration/nexora`. Nexora must negotiate
`nexora-trd-integration-v1` before synchronizing. TRD Bot `0.3.0` is recorded as
`legacy_read_only_blocked`, not silently adapted. Direct database access and
shared tables are forbidden.

The boundary contains read snapshots, an immutable event feed, deterministic
exports and only idempotent Paper/Shadow decision-review commands. It contains
no live-order, wallet, transfer or exchange-credential capability.

## Consequences

- TRD Bot needs a small `0.3.1+` compatibility release before Nexora runtime
  integration can start.
- Both products may evolve independently behind a negotiated contract version.
- Unknown versions and missing capabilities fail closed.
- Authentication and transport are deliberately selected in `NEX-P0-04`.
