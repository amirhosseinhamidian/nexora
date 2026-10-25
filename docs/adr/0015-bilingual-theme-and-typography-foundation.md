# ADR 0015: Bilingual theme and typography foundation

- Status: Accepted by NEX-P1-01 candidate
- Date: 2026-10-24

## Context

Nexora requires Persian and English from the beginning, and its financial
workspace must support both dark and light presentation. Direction, typography,
and color semantics are architectural concerns.

## Decision

Persian (`fa`) is the default locale and renders right-to-left with the owner's
local variable Vazirmatn file. English (`en`) renders left-to-right with the
self-hosted Inter Variable package. Both catalogs must have an identical nested
key structure.

Theme selection supports `light`, `dark`, and the operating-system preference.
Reusable semantic tokens live in `packages/ui/src/tokens.css`. The foundation
includes visible keyboard focus and reduced-motion behavior.

## Consequences

- Locale determines both language and document direction.
- No production page depends on a remote font request.
- New messages must be added to both catalogs.
- Later UI primitives and charts must verify both directions and themes.
