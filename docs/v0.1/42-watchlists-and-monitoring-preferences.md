# NEX-P3-09 — Watchlist and Monitoring Preferences

Status: **Candidate — requires same-SHA CI acceptance**

P3-09 adds durable, owner-scoped watchlists for local organization and bounded
monitoring presentation. A watchlist is metadata for attention and research; it
is not a trading instruction, provider subscription or notification channel.

## Aggregate and concurrency

Each watchlist has an owner, stable identifier, name and monotonically
increasing `row_version`. Item registration and preference changes lock the
aggregate head and require `expected_version`, so concurrent writers cannot
silently overwrite one another.

Every write requires an `Idempotency-Key`. Exact replay returns the existing
watchlist without another mutation; reuse for a different operation or payload
fails closed. Registering the same item kind, reference and label is idempotent
even with a new key and does not increment the aggregate version.

## Bounded item kinds and preferences

Items are restricted to `asset`, `market`, `strategy` and `candidate_source`.
Each item contains only a bounded reference and optional presentation label.

Monitoring preferences are deliberately small:

- presentation order: newest, oldest or severity descending;
- minimum visible severity: information, warning or critical;
- include resolved evidence: true or false.

These preferences affect only Nexora presentation. Notification delivery and
provider subscription management remain disabled.

## Private API and Web experience

The authenticated API lists and creates watchlists, registers items and updates
preferences under `/v1/watchlists`. All reads and writes are owner-scoped and
list size is bounded.

The bilingual Web panel exposes explicit loading, empty and error states,
stable idempotent retry, item registration, aggregate version and bounded
preferences. Its safety boundary remains visible beside the controls.

## Security boundary

A watchlist cannot create an OrderIntent, post a Portfolio Transaction, submit
an order, move funds, deliver a notification, manage a provider subscription or
add exchange and wallet credentials. Live trading remains outside Nexora v0.1.

## Transition

P3-09 is accepted only when its dedicated workflow and required regression
gates pass on the implementation SHA. Under the unified Implementation +
Acceptance policy, no separate per-stage Freeze commit is required. Successful
CI acceptance opens `NEX-P3-10`; the Real Local Provider Smoke gate remains
deferred to the Phase 3 acceptance sequence.
