# NEX-P3-07 — Human Accept, Reject and Defer Workflow

Status: **Candidate — requires same-SHA CI acceptance**

P3-07 adds an owner-scoped, immutable review journal for active TRD Bot
Decision evidence. The owner may accept, reject or defer a Decision. This is a
human evidence workflow, not an execution workflow.

## Source of truth and evidence binding

Nexora is the source of truth for owner reviews. Every review is bound to the
active owner projection generation and the exact `decision_evaluation` source
checksum. A changed generation or checksum fails with a conflict so an owner
cannot unknowingly review stale evidence.

Reviews are append-only. A correction creates a new review that names the
current review in `supersedes_review_id`. The per-Decision head is locked and
uses `expected_version`; concurrent writers cannot silently overwrite one
another. Exact idempotent replay returns the existing record, while reuse of a
key for another payload fails closed.

## Reasons and defer policy

Reason codes use the frozen `owner.accept.*`, `owner.reject.*` and
`owner.defer.*` namespaces. Provider reasons remain separate. An
`other_with_note` reason requires a non-blank owner note. A deferred review may
include a future `revisit_at` timestamp.

## Provider feedback

After the local transaction commits, Nexora may send the matching versioned
review command to a compatible TRD Bot 0.3.1 provider. Provider unavailability
does not erase or mutate the local owner review: delivery remains `pending` and
an exact idempotent retry may deliver it later. Stored delivery failures use a
bounded reason code and never retain secrets or raw upstream error bodies.

## Security boundary

Accepting evidence does not authorize execution, create an OrderIntent, post a
Portfolio Transaction, submit an order, transfer funds or add exchange/wallet
credentials. Only `paper` and `shadow` feedback modes are accepted. `NEX-P3-03`
remains blocked until P3-10 and Real Local Provider Smoke are complete.

## Transition

P3-07 is accepted only when its dedicated workflow and required regression
gates pass on the implementation SHA. Under the unified Implementation +
Acceptance policy, no separate per-stage Freeze commit is required. Successful
CI acceptance opens `NEX-P3-08`.
