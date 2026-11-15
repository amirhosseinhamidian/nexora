# NEX-P3-05 — Risk Gate Explanation and Reason Codes

This stage exposes compatible TRD Bot Risk Gate evidence as an owner-scoped,
read-only explanation. TRD Bot remains the sole owner of risk policy evaluation;
Nexora validates and displays the supplied result without recreating the Risk
Engine, changing a decision or inferring missing evidence.

## API and lineage

`GET /v1/risk-gates/{evaluation_id}` reads only the active projection generation
for the authenticated owner. The client cannot select an owner or staging
generation. A missing active projection returns an explicit degraded envelope;
a valid projection without the requested Risk Gate returns 404. Structurally
inconsistent risk evidence fails closed with 422.

The response preserves provider release, source schema, observation time,
source checksum, event/aggregate lineage and Nexora's evidence checksum. Policy
version and policy checksum must agree across the provider resource, immutable
Risk Gate record and assessment before anything is exposed.

## Explanation semantics

Provider `outcome.reason_codes` are returned in their original order and value
under the explicit `trd_bot` namespace. Future owner-review reasons remain a
separate namespace owned by P3-07. The complete provider check set is validated
in its canonical order (`candidate_fresh`, `ranking_score`, `reward_risk`,
`risk_budget`, `notional_cap`) and returned with pass/fail state, actual value,
limit value and provider explanation.

TRD Bot 0.3.1 does not supply a dedicated uncertainty value in
`trd-bot-risk-gate-v1`. Nexora therefore shows `not_supplied` with the stable
reason `TRD_BOT_RISK_UNCERTAINTY_NOT_SUPPLIED`. It does not translate ranking
score, failed checks or market confidence into fabricated uncertainty.

Approved Risk Gates have no rejection reason code; their supplied checks remain
the complete explanation. Rejected Risk Gates preserve both the provider reason
code and failed checks. Candidate deferral prevents a Risk Gate from existing,
so it remains explicit as unavailable evidence rather than a synthesized Risk
Gate decision.

## Product and security boundary

The bilingual Candidate workspace fetches the matching Risk Gate by immutable
`evaluation_id`, rejects a projection-generation mismatch and shows policy
lineage, reasons, checks and uncertainty state. Provider position-sizing data is
validated for lineage but deliberately not returned by the API or shown in the
Web experience; Portfolio impact belongs to P3-06.

This stage adds no live trading, order submission, exchange credential, wallet,
fund transfer, direct TRD Bot database access, shared database, policy editor or
human review. The response states `offline_only=true`,
`external_order_submission_allowed=false` and `position_sizing_exposed=false`.

## Recovery and transition

Failed, cancelled or incomplete CI cannot accept P3-05 or open P3-06. Correct
the candidate and rerun contract, backend, Web, runtime-contract and PostgreSQL
gates on the same candidate SHA. Provider compatibility must remain valid.
