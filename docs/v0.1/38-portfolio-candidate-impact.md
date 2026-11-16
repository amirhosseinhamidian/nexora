# NEX-P3-06 — Portfolio Candidate Impact and Bounded What-if

This stage displays immutable, provider-owned Paper/Shadow portfolio analysis
for a Candidate. TRD Bot remains the only owner of Portfolio Intelligence;
Nexora validates and presents the supplied recommendation, exposure,
concentration, correlation, deterministic scenarios and checks without
recomputing or overriding them.

## API and cross-resource lineage

`GET /v1/portfolio-impacts/{evaluation_id}` reads only the active projection
generation of the authenticated owner. A missing active projection returns a
degraded envelope, a missing matching resource returns 404, and malformed or
inconsistent provider evidence fails closed with 422.

The `portfolio_intelligence.risk_gate_checksum` must equal the immutable record
checksum of an approved Risk Gate for the same `evaluation_id` in the same
active projection. A missing, rejected, malformed or checksum-mismatched Risk
Gate invalidates Portfolio Impact. This prevents a structurally valid analysis
from being detached from the approved risk evidence that authorized the
provider to calculate it.

## Bounded analysis

Nexora preserves the exact ordered scenario shocks `-0.10`, `-0.05`, `0.05`
and `0.10`, plus their projected equity and loss fraction. It requires the
complete provider check sequence: portfolio active, portfolio capacity,
projected exposure, projected concentration, candidate correlation, scenario
loss and regime alignment. Recommendation and stage disposition must agree
with those checks.

The view exposes snapshot mode/source, projected exposure and concentration,
correlation evidence, provider reasons and policy lineage. An explicit
`unavailable` response remains unavailable; Nexora never fabricates a baseline
or analysis. TRD Bot 0.3.1 supplies no dedicated uncertainty value, so the API
returns `not_supplied` with
`TRD_BOT_PORTFOLIO_UNCERTAINTY_NOT_SUPPLIED`.

## Portfolio and execution boundary

Provider 0.3.1 Portfolio Intelligence concerns its own deterministic Paper or
Shadow simulated portfolio. It does not carry a versioned mapping from provider
symbols to Nexora personal asset UUIDs. P3-06 therefore does not guess that
mapping or bind the analysis to a personal portfolio. Such binding remains
blocked until a separately versioned asset-map contract exists.

This endpoint and UI are advisory and read-only. They create no Nexora
Transaction, OrderIntent, order, allocation, wallet action or fund transfer.
There is no direct/shared TRD Bot database access, service-token disclosure,
exchange credential, live-trading capability or production-readiness claim.

## Acceptance and recovery

P3-07 opens only after the exact P3-06 candidate SHA passes contract, backend,
Web, runtime-contract and PostgreSQL 17 CI gates. Failed, cancelled, skipped or
incomplete CI does not accept this stage. Correct the candidate, rerun all gates
on one SHA and retain provider compatibility and security boundaries.
