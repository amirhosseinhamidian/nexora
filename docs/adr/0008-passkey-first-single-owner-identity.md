# ADR 0008: Passkey-first single-owner identity

Status: **Accepted and frozen by NEX-P0-04**

## Context

Nexora v0.1 is a personal, single-owner financial application. It does not need
self-registration, invitations, email delivery, social login, organization
membership, or a multi-tenant identity provider. A reusable web password would
create password storage, reset, phishing, and credential-stuffing risks without
providing product value.

## Decision

The owner authenticates with a WebAuthn passkey and required user verification.
The relying-party ID and origin must exactly match the canonical private HTTPS
origin. Web password login, email reset, and security questions do not exist.

Initial enrollment uses a 256-bit, single-use CLI bootstrap token valid for ten
minutes on loopback or the private network. Recovery uses pre-generated,
single-use recovery codes stored only as digests, or an operator CLI reset that
requires host access. Recovery revokes all sessions and requires immediate
enrollment of a new passkey.

## Consequences

- The initial product has no password database or email recovery dependency.
- A stable HTTPS origin is required even on the private production network.
- Losing every authenticator and offline recovery material requires direct host
  operator access.
- Federation and multi-user identity remain a future SaaS decision.
