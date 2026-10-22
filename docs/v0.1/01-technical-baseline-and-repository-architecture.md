# NEX-P0-02 - Technical Baseline and Repository Architecture

وضعیت: **Candidate آماده بررسی و Freeze**

تاریخ تصمیم: `2026-10-22`

نسخه هدف: `Nexora v0.1.0`

قرارداد ماشین‌خوان:
[`contracts/nexora-v0.1-technical-baseline.json`](../../contracts/nexora-v0.1-technical-baseline.json)

این مرحله Stack، شکل repository، مرز dependencyها و Bootstrap Plan را تثبیت می‌کند. هنوز application
runtime، database schema، authentication یا UI واقعی ایجاد نمی‌شود. شروع runtime فقط بعد از Freeze
کامل Phase 0 در `NEX-P0-05` مجاز است.

## 1. پیش‌شرط

`NEX-P0-01` با Scope Contract و Freeze Record معتبر بسته شده است. بنابراین تصمیم‌های این مرحله حق
تغییر موارد زیر را ندارند:

- محصول مستقل و single-owner؛
- Crypto Spot و Paper/Shadow؛
- ممنوعیت direct database access به TRD Bot؛
- Export-first و AI-ready Data؛
- نبود SaaS، Live Execution، wallet و exchange credential.

Verifier این مرحله ابتدا `NEX-P0-01` را fail-closed بررسی می‌کند.

## 2. خلاصه تصمیم

| موضوع | تصمیم |
| --- | --- |
| Repository | Lightweight polyglot monorepo مستقل از TRD Bot |
| Architecture | Modular Monolith با processهای جدا برای Web، API و Worker |
| Web | Node.js 24 LTS، Next.js 16 App Router، React 19، TypeScript 5 strict |
| Web tooling | pnpm 10، Tailwind CSS 4، Radix UI، Vitest، Testing Library، Playwright |
| Server | Python 3.13، FastAPI، Pydantic 2، SQLAlchemy 2، Alembic 1، psycopg 3 |
| Server tooling | uv، Ruff، mypy strict، pytest |
| Database | PostgreSQL 17 اختصاصی Nexora |
| Jobs | PostgreSQL durable jobs با lease، retry و idempotency |
| Event delivery | Transactional Outbox |
| Artifact storage | filesystem نسخه‌دار پشت adapter؛ S3-compatible در صورت نیاز آینده |
| Local/VPS | Docker Compose |
| CI | GitHub Actions با gate مستقل Web، Server، Contract، DB و Security |

Release line به‌جای patch version فریز می‌شود. exact resolution در `NEX-P1-01` داخل `pnpm-lock.yaml`
و `uv.lock` ثبت خواهد شد.

## 3. چرا Polyglot Monorepo؟

Nexora یک محصول است، نه مجموعه‌ای از محصولات مستقل. تغییر یک Portfolio projection معمولاً contract،
API، UI، Export و test را هم‌زمان درگیر می‌کند. نگهداری این اجزا در یک repository امکان می‌دهد یک
candidate SHA تمام مسیر را نمایندگی کند.

استفاده از دو runtime آگاهانه است:

- Next.js و TypeScript برای UI داده‌محور، accessibility و تجربه دو‌زبانه؛
- Python و FastAPI برای Integration، Worker، Export و مسیر AI/ML آینده.

این تصمیم به معنی Microservice نیست. API و Worker یک مدل دامنه و package مشترک دارند و فقط process
و scaling مستقل خواهند داشت.

## 4. Repository Layout فریز شده

```text
nexora/
├── apps/
│   ├── web/                    # Next.js App Router
│   └── server/                 # FastAPI + Worker entry points
├── packages/
│   ├── contracts/              # OpenAPI, JSON Schema, fixtures
│   ├── ui/                     # accessible primitives and design tokens
│   └── config/                 # shared web tooling configuration
├── infra/
│   └── compose/                # local/private single-host topology
├── docs/
│   ├── adr/
│   └── v0.1/
├── scripts/                    # deterministic verification/operations
├── tests/                      # repository and cross-boundary tests
├── artifacts/                  # committed acceptance/freeze evidence
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
├── pyproject.toml
└── uv.lock
```

در P0-02 فقط layout contract فریز می‌شود. مسیرهای runtime، manifestها و lockfileها در `NEX-P1-01`
ایجاد می‌شوند تا dependency resolution بخشی از همان candidate قابل build باشد.

## 5. Backend layering

ساختار داخلی `apps/server/src/nexora` در Bootstrap باید این جهت dependency را رعایت کند:

```text
domain <- application <- adapters <- api
                              └────── worker
```

- `domain`: entity، value object، policy و event بدون FastAPI/SQLAlchemy؛
- `application`: use case، port، transaction boundary و authorization intent؛
- `adapters`: PostgreSQL، TRD Bot client، filesystem/S3 و clock؛
- `api`: HTTP validation، authentication adapter و response mapping؛
- `worker`: job claim، lease، retry، sync و Export execution.

Domain نباید به framework، ORM یا transport وابسته باشد. API و Worker persistence logic موازی
نمی‌سازند و فقط composition root هستند.

## 6. Frontend boundary

`apps/web` مسئول rendering، interaction، accessibility، localization و client state محدود است.

- Server Component و Client Component بر اساس نیاز انتخاب می‌شوند؛
- domain command فقط از API versioned عبور می‌کند؛
- Web مستقیماً به PostgreSQL دسترسی ندارد؛
- Next.js Route Handler فقط same-origin transport/session adapter است؛
- business rule، ledger mutation و TRD Bot integration در Web ممنوع است؛
- generated type یا client باید از contract نسخه‌دار ساخته شود.

Design System و navigation دقیق در Phase 1 شکل می‌گیرند، اما پایه آن Tailwind CSS 4 و Radix UI است.

## 7. Data و durability

PostgreSQL 17 منبع حقیقت عملیاتی Nexora است. Database آن از TRD Bot جداست.

قواعد پایه:

- تمام migrationها با Alembic و دارای upgrade/downgrade تا release freeze هستند؛
- production startup اجازه `create_all` یا mutation خودکار schema ندارد؛
- timestamp ذخیره‌شده timezone-aware و canonical آن UTC است؛
- money بدون currency و quantity بدون unit معتبر نیست؛
- projection خارجی SourceReference و source version دارد؛
- evidence منبع update/delete نمی‌شود؛
- command و job قابل retry idempotency key دارد؛
- outbox در transaction همان تغییر دامنه نوشته می‌شود.

Redis، RabbitMQ، Kafka یا Kubernetes در v0.1 baseline نیستند. افزودن هرکدام به benchmark و ADR جدید
نیاز دارد.

## 8. Dependency و Toolchain policy

- فقط LTS یا release line پشتیبانی‌شده انتخاب می‌شود؛
- lockfileها commit می‌شوند؛
- تغییر major خودکار نیست؛
- dependency جدید باید owner، دلیل و impact داشته باشد؛
- security update پس از test پذیرفته می‌شود؛
- container base image با digest یا patch pin ثبت می‌شود؛
- script نصب نباید secret تولید یا از محیط developer استخراج کند؛
- package ناشناخته برای Live Trading، Wallet یا Exchange Credential ممنوع است.

انتخاب Node.js 24 به دلیل LTS بودن در تاریخ تصمیم است. Python 3.13 به‌صورت محافظه‌کارانه به‌جای
نسخه feature بسیار تازه انتخاب شد. PostgreSQL 17 با baseline عملیاتی موجود پروژه هم‌راستا است.

## 9. Quality gates برنامه‌ریزی‌شده

### Repository contract

- verifierهای P0؛
- schema و fixture validation؛
- forbidden capability inventory؛
- `git diff --check`.

### Server

- `ruff format --check`؛
- `ruff check`؛
- `mypy --strict`؛
- `pytest`؛
- OpenAPI snapshot و import boundary tests.

### Web

- Prettier؛
- ESLint؛
- TypeScript `--noEmit`؛
- Vitest و Testing Library؛
- Next.js production build؛
- Playwright برای مسیرهای پذیرش.

### Database

- upgrade تا head؛
- downgrade تا base؛
- rebuild تا head؛
- Alembic drift check؛
- PostgreSQL integration و concurrency test.

### Security

- dependency audit؛
- secret scan؛
- route/OpenAPI inventory؛
- اثبات نبود live-order، wallet و credential capability.

## 10. Bootstrap Plan برای P1

Bootstrap فقط بعد از `NEX-P0-05` انجام می‌شود:

1. root workspace و lockfileها ایجاد شوند؛
2. `apps/web` با Next.js و strict TypeScript ساخته شود؛
3. `apps/server` با Python package و health endpoint ساخته شود؛
4. PostgreSQL 17 و migration صفر راه‌اندازی شود؛
5. API و Worker composition root جدا ایجاد شوند؛
6. contract package و fixture validation وارد build شود؛
7. Docker Compose برای local/private host ایجاد شود؛
8. CI gateهای واقعی جای contract plan را بگیرند؛
9. fresh clone و deterministic install اثبات شود؛
10. هیچ integration با TRD Bot قبل از contractهای P0-03 نوشته نشود.

## 11. Debt Inventory

| ID | موضوع | Risk | Owner/Due | رفتار موقت |
| --- | --- | --- | --- | --- |
| NEX-DEBT-P0-02-001 | exact dependency pin و lockfile هنوز وجود ندارد | Medium | P1-01 | فقط release line فریز است |
| NEX-DEBT-P0-02-002 | schemaهای TRD Bot هنوز فریز نشده‌اند | High | P0-03 | runtime integration ممنوع |
| NEX-DEBT-P0-02-003 | auth/session و topology انتخاب نشده | High | P0-04 | production access ادعا نمی‌شود |
| NEX-DEBT-P0-02-004 | SLO/retention/backup/capacity عددی نیست | Medium | P0-04 | operational readiness=false |
| NEX-DEBT-P0-02-005 | acceptance matrix نهایی Phase 0 وجود ندارد | Medium | P0-05 | Phase 1 مسدود است |

این موارد debt پنهان نیستند. هرکدام owner، due stage و رفتار fail-closed دارند.

## 12. تصمیم‌های منتقل‌شده به مراحل بعد

### P0-03

- endpoint inventory؛
- Event و Export schema؛
- cursor، retry و idempotency semantics؛
- compatibility matrix با TRD Bot v0.3.x.

### P0-04

- mechanism دقیق login و session؛
- secret storage؛
- deployment topology و reverse proxy؛
- SLO، capacity، retention، backup و restore؛
- object storage production decision.

### P0-05

- Phase 0 acceptance runner؛
- traceability matrix؛
- candidate SHA/CI evidence و Freeze نهایی.

## 13. موارد ردشده

- Full-stack Next.js به‌عنوان تنها backend؛
- NestJS برای Backend نسخه اول؛
- repository جدا برای Web و API؛
- Microservice per domain؛
- Redis یا broker خارجی از روز اول؛
- Kubernetes؛
- database مشترک یا query مستقیم به TRD Bot؛
- runtime schema auto-create؛
- business logic داخل Frontend؛
- dependency بدون lockfile یا contract خارجی بدون version.

رد NestJS به معنی نامناسب‌بودن آن به‌صورت عمومی نیست؛ FastAPI برای نزدیکی به TRD Bot، workloadهای
داده‌ای، Export و ML آینده در Nexora انتخاب شده است.

## 14. معیار خروج NEX-P0-02 candidate

- [x] Stack Web و Server انتخاب و دلیل آن ثبت شد.
- [x] Repository layout و deployment unitها مشخص شدند.
- [x] Backend layering و Frontend boundary تعریف شد.
- [x] PostgreSQL، durable jobs و outbox baseline مشخص شد.
- [x] dependency و quality gate policy ثبت شد.
- [x] debt inventory دارای owner و due stage است.
- [x] Bootstrap Plan بدون ایجاد runtime آماده شد.
- [x] قرارداد ماشین‌خوان و verifier بدون dependency اضافه ایجاد شد.
- [x] ADRهای اصلی ثبت شدند.

## 15. شاهد بررسی candidate

فرمان‌های زیر باید موفق باشند:

```bash
python3 scripts/verify_scope_contract.py
python3 scripts/verify_technical_baseline.py
python3 -m unittest discover -s tests -v
git diff --check
```

خروجی verifier باید شامل marker زیر باشد:

```text
NEX_P0_02_TECHNICAL_BASELINE=PASS
```

پس از commit، push و سبزشدن CI همان candidate، فقط Freeze Record مرحله
`NEX-P0-02-FREEZE` اضافه می‌شود.
تا قبل از آن `NEX-P0-03` و runtime bootstrap مجاز نیستند.

## 16. منابع snapshot تصمیم

Baseline در تاریخ تصمیم با منابع رسمی Next.js، Node.js، Python و PostgreSQL بررسی شده است. URLها
داخل contract ثبت شده‌اند تا منشأ تصمیم قابل audit باشد؛ آن‌ها dependency resolution یا lockfile
محسوب نمی‌شوند.
