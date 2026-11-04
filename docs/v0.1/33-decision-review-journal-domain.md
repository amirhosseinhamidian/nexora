# NEX-P3-01 — Decision, Review and Journal Domain Freeze

Status: **Frozen — `NEX-P3-02` is the only opened stage**

P3-01 freezes the domain language and invariants for explainable decision
evidence, explicit owner review and an append-oriented outcome journal. It adds
no database table, API, Web screen, provider registration or runtime behavior.

## Prerequisite and boundary

`NEX-P3-00` is frozen at commit
`adfe6291490a03f7be2f3f9e9261b5d2454dd8b3`. Local development may continue,
but `NEX-V0.1-SERVER-DEPLOYMENT-ACCEPTANCE` remains deferred and blocks v0.1
production deployment and release.

TRD Bot owns market, Strategy, Signal, Candidate and Risk evidence. Nexora owns
the owner's review, local alert state, watchlist and outcome journal. Neither
system reads the other's database. Nexora stores versioned references and
checksums and never edits the provider's evidence.

## Freeze evidence

Candidate `ffa4acd39806e72f7e53d16af7e9937c12e669c5` with tree
`b21956943411f7b7a4d6d333a4953c093be562ed` passed the dedicated Decision,
Review and Journal workflow plus all 29 regression workflows on the same SHA.
The primary push run is
`https://github.com/amirhosseinhamidian/nexora/actions/runs/41859051343`.

The checksummed evidence is recorded in
`artifacts/p3-01/decision-review-journal-domain-freeze.json`. The Freeze adds no
database table, API, UI or runtime behavior and does not pass the deferred
server gate.

## Source evidence

Every projected decision record retains:

- provider identity and release;
- payload schema version and stable source record ID;
- source event ID, event time and Nexora observation time;
- payload checksum;
- policy/model identity, version and checksum when supplied;
- explicit stale, missing, degraded or unknown-schema state.

Unknown schemas and checksum mismatches are quarantined. UTC remains canonical.
Provider sync cannot rewrite an owner note or a previously recorded review.

## Decision record

`decision_record` is an owner-scoped projection of immutable source evidence.
It may represent a Candidate, Risk assessment, Portfolio assessment or
monitoring alert. Its local state is derived from append-only reviews and can be
`review_pending`, `accepted`, `rejected`, `deferred`, `expired` or
`superseded`.

Duplicate source delivery is idempotent. Projection state uses optimistic
versions. An expired cursor requires full resync rather than an inferred gap
fill.

## Human review

The owner can record exactly one of:

- `accept`;
- `reject`;
- `defer`.

A review requires the Decision reference, source-evidence checksum, namespaced
reason code, owner actor, review time, recording time, idempotency key and
expected version. Recorded reviews are immutable. Correction uses a superseding
review, preserving both records.

Provider reason codes and owner reason codes remain separate namespaces. An
`other_with_note` reason requires a note. A deferred review may include a
`revisit_at` time.

Accepting a Candidate does not create an OrderIntent, submit an order, approve
real-money execution or post a Portfolio transaction. It is durable human
decision evidence only.

## Portfolio impact

The initial `portfolio_candidate_impact` is advisory and may report:

- exposure delta;
- concentration delta;
- risk-budget delta;
- simulated allocation delta.

It requires Candidate and Portfolio snapshot references, calculation version,
input checksums and explicit uncertainty. What-if analysis cannot persist an
accounting transaction or submit an order.

## Alerts and watchlists

Source alerts remain immutable. Nexora records append-only owner state changes
for `open`, `acknowledged`, `snoozed`, `resolved` and `expired`. Snoozed state
requires a resume time. Notification delivery is deferred.

Watchlists are owner-scoped and can contain assets, markets, Strategies or
Candidate sources. They use optimistic concurrency and idempotent item
registration. A watchlist never becomes a trade instruction or exchange
subscription manager.

## Outcome journal

`outcome_journal_entry` links a Decision to owner notes, review rationale,
observed outcomes, expectation comparisons, lessons or corrections. Entries
retain event and recording times. Observed outcomes require source lineage and
show uncertainty.

Entries are append-only. Correction uses a superseding entry. Provider sync
cannot rewrite human notes, and P3-01 introduces no AI-generated journal entry.

## Export boundary

Both `private_complete` and `ai_safe` profiles cover Decision records, source
references, reviews, Portfolio impacts, Alert history, watchlists, Journal,
lineage and uncertainty. Exports remain schema-versioned, owner-scoped,
timestamped and checksummed.

Credentials, tokens, sessions, recovery material, private keys and raw security
context remain excluded. No export receives a public download URL.

## Deferred implementation

- P3-02 freezes the TRD Bot v0.3.1 integration contract;
- P3-03 owns persistence, migrations and durable projection;
- P3-04 through P3-10 own the API and product experiences;
- P3-11 owns complete Phase 3 export implementation;
- P3-12 owns integrated accessibility and E2E;
- P3-13 owns Phase 3 acceptance.

TRD Bot `0.3.0` remains incompatible. Fixtures may be defined before `0.3.1`,
but a compatible provider is required before durable projection can freeze.

## Explicitly forbidden

- direct TRD Bot database access or source-evidence mutation;
- treating owner review as execution authorization;
- creating an order or accounting transaction from Accept or What-if;
- exchange credentials, private keys, signing or fund transfer;
- public deployment, SaaS or multi-user identity;
- live orders or autonomous AI execution;
- ML training/inference, financial advice or tax advice;
- production-readiness claims before the private-VPS gate passes.

## Verification and transition

Run:

```bash
uv run python scripts/verify_decision_review_journal_domain.py
uv run python -m unittest tests/test_decision_review_journal_domain.py -v
```

The accepted candidate passed its dedicated workflow and every repository
regression on one SHA. P3-01 is frozen; the only opened stage is `NEX-P3-02`.
