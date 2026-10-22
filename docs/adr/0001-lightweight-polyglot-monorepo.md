# ADR-0001 - Lightweight Polyglot Monorepo and Modular Monolith

وضعیت: **Accepted and frozen by NEX-P0-02**

تاریخ: `2026-10-22`

## Context

Nexora یک محصول مستقل از TRD Bot است، اما Web، API، Worker، قراردادهای Integration و Export آن
باید با یک release و یک acceptance record تحویل شوند. نسخه `v0.1.0` تک‌مالک است و پیچیدگی عملیاتی
Microservice، Kubernetes و چند repository برای آن توجیه ندارد.

## Decision

Nexora به‌صورت یک `lightweight polyglot monorepo` نگهداری می‌شود:

- `apps/web` برای رابط Next.js؛
- `apps/server` برای FastAPI و Worker مشترک؛
- `packages/contracts` برای قراردادهای مستقل از زبان؛
- `packages/ui` و `packages/config` برای اجزای مشترک Web؛
- `infra/compose` برای محیط Local و VPS خصوصی.

Backend یک Modular Monolith است. API و Worker دو process مستقل، اما دو entry point از یک codebase و
یک مدل دامنه‌اند. ایجاد service مستقل تنها با شاهد bottleneck، security isolation یا deployment cadence
مستقل مجاز است.

برای orchestration اولیه از package managerهای native، scriptهای repository و GitHub Actions استفاده
می‌شود. Turborepo یا Nx در baseline اجباری نیستند.

## Consequences

### Positive

- یک commit و یک CI برای تغییرهای cross-boundary؛
- contract fixtureها کنار consumer و producer Nexora قرار می‌گیرند؛
- bootstrap و توسعه شخصی ساده می‌ماند؛
- جداسازی processهای API و Worker بدون تکرار Domain ممکن است.

### Negative

- CI باید Python و Node را هم‌زمان مدیریت کند؛
- discipline لایه‌ها باید با test و import rule حفظ شود؛
- monorepo به معنی shared database با TRD Bot نیست.

## Rejected alternatives

- repository جدا برای Web و API: هزینه هماهنگی و release را زودهنگام افزایش می‌دهد.
- microservice per domain: برای v0.1 پیچیدگی عملیاتی بدون ارزش متناظر ایجاد می‌کند.
- full-stack Next.js به‌عنوان تنها backend: برای Worker، Export، Integration و ML آینده مرز مناسبی
  ایجاد نمی‌کند.
