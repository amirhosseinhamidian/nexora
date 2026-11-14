# NEX-P3-04 — Decision Feed and Candidate Details

This stage exposes the active owner-scoped Decision and Candidate projection as
read-only API and product views. It does not implement Risk Gate explanation,
Portfolio what-if, human review, alerts or execution behavior.

## API boundary

`GET /v1/decisions` returns a bounded, newest-first feed from the single active
projection generation. Its opaque cursor binds both the generation and the
canonical evidence SHA-256; pagination fails with a bounded conflict when
activation or an event changes the feed instead of mixing two snapshots. The
page size is limited to 100.

`GET /v1/candidates/{candidate_id}` returns one Candidate from that same active
owner projection. An existing active projection with no matching Candidate is a
404. A missing or invalid active projection instead returns a successful,
explicitly degraded envelope with no Candidate so the UI can distinguish
provider recovery from absence.

Every item includes provider release, source schema, observed time, source
checksum, event and aggregate lineage when present, plus the independently
checksummed provider evidence. Stored records are revalidated against the P3-03
projection model before exposure. One invalid visible record makes the complete
feed fail closed as degraded and empty.

## Provider and product states

The response states are `ready`, `degraded` and `disabled_incompatible`.
Historical active evidence may remain visible read-only while an incompatible
provider is disabled; the response never presents that provider as ready.

The bilingual responsive workspace exposes loading, empty, error and degraded
states. Decision/Candidate evidence and full source checksums remain visible,
with an explicit statement that the view cannot submit an order, move funds or
authorize execution.

## Isolation and security

The API derives `owner_id` only from the authenticated server-side session and
passes it to a repository query that selects `status=active`. Client input
cannot select another owner or a staging generation. Generation metadata and
projection content are read in the same database snapshot.

No service token, exchange credential, wallet key or direct TRD Bot database
access is introduced. Provider evidence is not mutated. Risk policy reasoning
remains owned by `NEX-P3-05`; human review remains owned by `NEX-P3-07`.

## Failure recovery and transition

Failed, cancelled or incomplete CI does not accept this candidate and does not
open `NEX-P3-05`. Correct the P3-04 candidate and rerun its contract, backend,
Web and repository regression gates. Provider incompatibility remains explicit
and cannot be converted into a compatibility claim by UI state.
