# NEX-P3-10 — Decision and Outcome Journal

Status: **Candidate — requires same-SHA CI acceptance**

P3-10 adds an owner-scoped, append-only journal that links human notes,
review rationale, observed outcomes, expectation comparisons, lessons and
corrections to immutable Decision evidence.

## Immutable entries and corrections

Every entry records owner, Decision, kind, content, visible uncertainty,
occurrence time, recording time and the exact source snapshot of the Decision.
Entries cannot be updated or deleted. A correction is another immutable entry
that names the entry it supersedes; only one direct correction can supersede a
given entry, while a later correction may supersede the previous correction.

Every write requires an `Idempotency-Key`. Exact replay returns the original
entry, while reuse for different content fails closed.

## References and lineage

A Decision reference is mandatory. Review, Portfolio and simulated-position
references are optional and owner-scoped. An `observed_outcome` additionally
requires a versioned source identifier, observation time and checksum. The
source lineage remains visible beside the uncertainty level and optional note.

## Authorship and security boundary

Journal entries are owner-authored. AI-generated entries and provider rewrites
are forbidden. Provider synchronization cannot rewrite a human note. A Journal
entry cannot authorize execution, create an OrderIntent, post a Portfolio
Transaction, submit an order, move funds or introduce exchange credentials.

## Private API and Web experience

The authenticated API lists and appends entries under
`/v1/decisions/{decision_id}/journal`; it exposes no update or delete endpoint.
The bilingual Web panel provides initial, loading, empty and error states,
stable idempotent retry, visible lineage and explicit append-only boundaries.

## Transition

P3-10 is accepted only when its dedicated workflow and regression gates pass
on the implementation SHA. Successful CI acceptance opens `NEX-P3-11`; the
Real Local Provider Smoke gate remains deferred to Phase 3 acceptance.
