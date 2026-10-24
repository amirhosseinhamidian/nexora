# ADR 0013: Evidence-gated Phase 0 transition

Status: Accepted and frozen by NEX-P0-05

## Context

Phase 0 has frozen product scope, the technical baseline, the TRD Bot integration
surface, and the private security and operational boundary. Starting runtime work
from documentation alone would still allow a candidate and its reviewed CI evidence
to diverge.

## Decision

The transition from Phase 0 to `NEX-P1-01` is fail-closed and requires all of the
following:

1. every P0-01 through P0-04 freeze record validates against its current contract;
2. every Phase 0 requirement has a named owner, durable evidence, and an automated
   verifier in the machine-readable traceability matrix;
3. every declared debt is closed or transferred to an explicit owner and due stage;
4. the P0-05 candidate SHA is bound to one successful GitHub Actions run containing
   every required contract job;
5. that evidence is committed separately as an immutable P0-05 freeze record.

The acceptance candidate itself does not authorize runtime bootstrap. Only the final
freeze record may set the next allowed stage to `NEX-P1-01`. Later implementation
must not rewrite the historical candidate or freeze evidence.

The final freeze binds candidate SHA
`20cf4eacc095d19711b3b80f518c56019445e87e` to successful GitHub Actions run
`40080625175`. The immutable record is stored at
`artifacts/p0-05/phase-zero-freeze.json`; it is the authority that opens
`NEX-P1-01`.

## Consequences

- An uncommitted local run, a green run for another SHA, or a partially successful
  workflow cannot open Phase 1.
- Phase 0 evidence remains reproducible after runtime code is introduced.
- The exact dependency-pin debt stays visible and becomes a mandatory P1-01 output.
- Any change to a frozen boundary requires a new explicit decision and evidence;
  silent contract drift fails verification.
- The process adds one small freeze commit after candidate CI, but it makes the
  transition independently auditable.
