# ADR 0010: Private-network deployment and service authentication

Status: **Accepted and frozen by NEX-P0-04**

## Context

The first Nexora release is for one owner and does not need public discovery.
Exposing application, database, worker, or TRD Bot integration ports directly
to the internet would expand the attack surface before SaaS controls exist.

## Decision

Production uses the `private_single_host` profile. Remote access enters through
an authenticated WireGuard-compatible overlay network and one HTTPS reverse
proxy. Only TCP 443 is exposed to that private network. PostgreSQL, worker, web,
and API service ports remain on segmented container networks. Public-internet
production is unsupported in v0.1.

Nexora calls the TRD Bot integration boundary only from its backend over TLS on
the private network. It uses a random 256-bit bearer token with explicit v1
scopes. Nexora reads the token from a mounted secret file; TRD Bot stores only
an HMAC-SHA-256 digest protected by a server pepper. Tokens rotate at least every
90 days, permit at most 24 hours overlap, and never reach the browser.

## Consequences

- Private-network membership is necessary but does not replace application
  authentication or authorization.
- The v0.1 deployment has no public registration, public API, or public admin
  surface.
- Public hosting later requires a separate threat model and acceptance gate.
- No live-order, wallet, or exchange-credential scope can be issued.
