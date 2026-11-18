# NEX-P4-01 — UI Foundation and Micro Components

Status: **Candidate — opens only `NEX-P4-01-FREEZE`**

P4-01 establishes the shared product-interface foundation used by every later
Phase 4 page. It does not add routes or domain workflows. The accepted P4-00
roadmap is frozen, and its successful verifier run on commit
`079efb63e7b57b32c9d1902da30b27f75edddbe0` authorizes this stage.

## Package boundary

Reusable controls live in `@nexora/ui`, not in feature pages. The package
exports design tokens, primitive styles and React components. Components do not
own domain logic, network requests, financial data or product-specific copy.

The Web application imports the two shared style entrypoints once from its root
locale layout. Later pages import components from `@nexora/ui/primitives`.

## Delivered foundation

### Actions and forms

- Button variants cover primary, secondary, quiet and dangerous actions, three
  sizes, disabled state and duplicate-submission-safe loading state.
- Icon buttons require an accessible name.
- Inputs, text areas, selects, search, checkboxes, radio buttons and switches use
  shared size, focus, invalid and disabled behavior.
- Form fields keep labels, optional descriptions and contextual errors together.

### Feedback and data states

- Alerts retain persistent information in context.
- Toast regions announce transient success, warning and operation failure.
- Progress, spinners and skeletons distinguish determinate, indeterminate and
  loading states.
- Empty, error, offline and degraded panels give later pages consistent recovery
  surfaces.

### Overlays

- Modal, confirmation dialog, Drawer and Sheet share one accessible overlay
  implementation.
- Open overlays lock background scrolling, receive keyboard focus, contain Tab
  focus, close on Escape and restore focus after closing.
- Tooltips work with pointer and keyboard focus. Popovers and dropdown menus use
  shared visual surfaces.

### Data presentation

- Tables use local overflow rather than causing page-level overflow.
- Responsive record lists provide a card alternative for narrow viewports.
- Pagination, tabs, filters and search establish shared navigation controls.
- Stat cards, chart containers, legends and comparisons provide reusable
  analytical composition without fabricating values.
- Charts require a visible text or table equivalent.

## Direction, themes and responsive behavior

Styles use logical CSS properties so Persian RTL and English LTR do not need
duplicated layouts. Switch motion, drawers, spacing and alignment follow the
document direction. Tokens cover light and dark semantic colors, Persian and
English fonts, spacing, radius, focus and control sizes.

Motion is reduced when the operating system requests it. Narrow viewports stack
comparison values and overlay actions. Responsive tables can switch to labelled
record rows while wide tables scroll only inside their own container.

## Content policy

Primitives contain no domain copy. Feature callers provide simple messages that
say what happened and how to recover. Persian callers avoid unnecessary English;
technical identifiers remain secondary and use their appropriate direction.

## Acceptance boundary

P4-01 accepts the shared foundation only. Real routes, Sidebar behavior,
first-run onboarding and all domain pages remain assigned to P4-02 through
P4-10. Authentication, authorization, backend domains, immutable evidence and
the deferred private-server gate remain unchanged.

The candidate opens only `NEX-P4-01-FREEZE`. P4-02 remains blocked until this
candidate passes owner-run checks, same-SHA CI and a checksummed Freeze record.
