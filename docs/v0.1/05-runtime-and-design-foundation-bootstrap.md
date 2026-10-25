# NEX-P1-01 — زیرساخت اجرا و طراحی

وضعیت: **Frozen**
تاریخ تصمیم: ۲۰۲۶-۱۰-۲۴
تاریخ Freeze: ۲۰۲۶-۱۰-۲۵

## هدف

این مرحله اولین کد اجرایی Nexora را پس از Freeze کامل Phase 0 ایجاد می‌کند:
یک monorepo سبک با وب Next.js، سرور FastAPI، entry point جدا برای worker و
پایهٔ طراحی دوزبانه. این خروجی هنوز database، authentication، اتصال اجرایی به
TRD Bot یا production deployment نیست.

## پیش‌نیاز قطعی

`NEX-P0-05` در commit با شناسهٔ
`d75436eb859c8a2c31d93db740f0378314f89d92` Freeze شده است. checksum رکورد
Freeze برابر `5de46860c0ea0a5fd32951976f4e93639de316632a15d5b4c3ef4a9c3c4c476b`
است و `runtime_bootstrap_authorized=true` را ثبت می‌کند.

## خروجی فنی

| بخش | انتخاب قطعی | مرز این مرحله |
| --- | --- | --- |
| Web | Node.js 24.22.1، pnpm 10.34.8، Next.js 16.4.3، React 19.3.1 | shell و foundation page |
| Server | Python 3.13.16، uv 0.13.4، FastAPI 0.162.0 | فقط liveness API |
| Worker | composition root مستقل | فقط `--check`؛ اجرای job ممنوع |
| Dependencies | direct pin دقیق + `pnpm-lock.yaml` و `uv.lock` | نصب CI به‌صورت frozen |

health endpoint در `/health/live` قرار دارد. مستندات تعاملی API در bootstrap
عمداً غیرفعال است و worker تا `NEX-P1-05` هیچ jobای را claim نمی‌کند.

## پایهٔ UI

- ظاهر از تصویر مرجع dark financial dashboard الهام می‌گیرد.
- پوسته‌های `light`، `dark` و `system` از semantic tokenهای مشترک استفاده می‌کنند.
- فارسی locale پیش‌فرض است، `dir=rtl` دارد و از فایل متغیر محلی Vazirmatn استفاده می‌کند.
- انگلیسی `dir=ltr` دارد و Inter Variable به‌صورت self-hosted نصب می‌شود.
- کاتالوگ‌های فارسی و انگلیسی باید کلیدهای دقیقاً یکسان داشته باشند.
- keyboard focus و `prefers-reduced-motion` از همین مرحله بخشی از قراردادند.

## مرز امنیتی

live order، exchange credential، wallet، دسترسی مستقیم به database پروژه TRD Bot،
autonomous AI execution، public production و multi-tenant identity همچنان ممنوع‌اند.

## بدهی بسته‌شده و موارد deferred

`NEX-DEBT-P0-02-001` با pin دقیق dependencyها و ثبت هر دو lockfile بسته می‌شود.
مراحل بعدی `NEX-P1-02` تا `NEX-P1-06` به‌ترتیب composition و configuration،
database، adapter پروژه TRD Bot، durable jobs و private identity را تحویل می‌دهند.

## معیار پذیرش

```bash
python3 scripts/verify_phase_zero_acceptance.py
python3 scripts/verify_runtime_foundation.py
python3 -m unittest discover -s tests -v
uv sync --frozen --python 3.13
pnpm install --frozen-lockfile
pnpm format:check && pnpm lint && pnpm typecheck && pnpm test && pnpm build
```

```text
NEX_P0_05_PREREQUISITE=PASS
NEX_P1_01_RUNTIME_FOUNDATION=PASS
```

## Freeze نهایی

Candidate بدون تغییر به commit و اجرای موفق GitHub Actions زیر متصل شد:

| شاهد | مقدار |
| --- | --- |
| repository | `amirhosseinhamidian/nexora` |
| candidate commit | `611557dd95241d7c45513772601e58bc055f398f` |
| commit message | `feat(nexora): bootstrap P1-01 runtime and design foundation` |
| GitHub Actions run | `https://github.com/amirhosseinhamidian/nexora/actions/runs/40182361689` |
| required jobs | `foundation-contract`، `backend` و `web` |
| conclusion | `success` برای هر سه job |
| Runtime contract checksum | `3c12939120ca19dc5604d35ad9946122327cb5635dfd7c52949da6dbf1b87be3` |

رکورد ماشین‌خوان در
[`artifacts/p1-01/runtime-foundation-freeze.json`](../../artifacts/p1-01/runtime-foundation-freeze.json)
ثبت شده است. Verifier تطابق SHA، پیام commit، run، jobها، step evidence، checksum
قرارداد و Freeze پیش‌نیاز Phase 0 را fail-closed بررسی می‌کند.

خروجی نهایی شامل marker زیر است:

```text
NEX_P1_01_FREEZE=PASS
```

`NEX-P1-01` اکنون Frozen است و گام مجاز بعدی فقط
`NEX-P1-02 — Application Composition and Typed Runtime Configuration` است.
