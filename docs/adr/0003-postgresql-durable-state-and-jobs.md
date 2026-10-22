# ADR-0003 - PostgreSQL Durable State, Jobs, and Outbox

وضعیت: **Accepted and frozen by NEX-P0-02**

تاریخ: `2026-10-22`

## Context

Nexora باید sync، Journal، Export و lifecycleهای قابل retry را با audit و idempotency نگهداری کند.
مقیاس نسخه شخصی نیازمند broker جدا یا Redis به‌عنوان state store نیست، اما job درون حافظه نیز برای
restart و recovery کافی نیست.

## Decision

PostgreSQL `17.x` تنها source of truth عملیاتی Nexora در v0.1 است. API و Worker از database اختصاصی
Nexora استفاده می‌کنند و هیچ query مستقیمی به database داخلی TRD Bot ندارند.

- migration فقط با Alembic انجام می‌شود؛
- startup تولیدی schema را خودکار ایجاد یا اصلاح نمی‌کند؛
- jobهای durable، lease، retry و idempotency در PostgreSQL نگهداری می‌شوند؛
- eventهای خروجی با transactional outbox در همان transaction دامنه نوشته می‌شوند؛
- Redis و message broker خارجی در baseline الزامی نیستند؛
- Export artifact ابتدا پشت adapter روی filesystem نسخه‌دار ذخیره می‌شود و adapter سازگار S3 بعداً
  قابل جایگزینی است؛
- Parquet با PyArrow تولید می‌شود، اما فایل artifact منبع حقیقت transaction نیست.

## Consequences

- backup و restore یک پایگاه داده، state عملیاتی را پوشش می‌دهد؛
- worker restart و reclaim قابل تست می‌شود؛
- ظرفیت PostgreSQL باید در P0-04 بودجه‌بندی شود؛
- افزودن Redis تنها پس از benchmark و ADR جدید ممکن است.

## Rejected alternatives

- Redis queue از ابتدا: dependency عملیاتی اضافه بدون نیاز اثبات‌شده است.
- in-memory jobs: restart-safe و audit-friendly نیست.
- database مشترک با TRD Bot: ownership، migration و security boundary را نقض می‌کند.
