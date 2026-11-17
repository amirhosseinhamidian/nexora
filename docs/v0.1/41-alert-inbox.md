# NEX-P3-08 — Alert Inbox, Acknowledge and Snooze

Status: **Candidate — requires same-SHA CI acceptance**

P3-08 adds a durable, owner-scoped inbox for compatible TRD Bot alert
evidence. The owner may acknowledge an alert or snooze it until a future time.
The workflow changes only Nexora's local presentation state and never mutates
the provider event.

## Source evidence boundary

Only alerts in the active owner projection are exposed. Each local transition
is bound to the exact projection generation and source checksum. If either has
changed, the request fails with a conflict rather than applying an action to
stale evidence. The complete immutable source reference remains attached to
every history entry.

## Append-only local lifecycle

Nexora records owner alert transitions in append-only history and maintains a
locked per-alert head for optimistic concurrency. Exact idempotent replay
returns the existing transition; reusing a key for a different request fails
closed. Acknowledge produces `acknowledged`; snooze produces `snoozed` and
requires a future `snooze_until` value.

`open` is the default presentation state. Once a snooze time passes, the alert
is presented as open again without rewriting history. Provider-owned terminal
`resolved` or `expired` states take precedence when present in the immutable
source evidence.

## Private API and Web experience

The authenticated `GET /v1/alerts` endpoint returns a bounded owner inbox with
provider health, source lineage, current local state and transition history.
`POST /v1/alerts/{alert_id}/state-transitions` records acknowledge or snooze
using an `Idempotency-Key`, expected version, evidence generation and checksum.

The bilingual Web inbox includes explicit loading, empty, error and degraded
states. A failed client retry retains its idempotency key. Notification
delivery remains disabled and is stated explicitly in the API and interface.

## Security boundary

Alert state is presentation and owner-attention evidence only. It cannot
authorize execution, create an OrderIntent, post a Portfolio Transaction,
submit an order, transfer funds or add exchange or wallet credentials.
Notification delivery and provider subscription management remain deferred.

## Transition

P3-08 is accepted only when its dedicated workflow and required regression
gates pass on the implementation SHA. Under the unified Implementation +
Acceptance policy, no separate per-stage Freeze commit is required. Successful
CI acceptance opens `NEX-P3-09`; the Real Local Provider Smoke gate remains
deferred to the Phase 3 acceptance sequence.
