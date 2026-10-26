# NEX-P1-06 — Single-owner identity, session and private runtime

وضعیت: **Frozen**

این مرحله مرز امنیتی فریز‌شده‌ی P0-04 را به runtime واقعی تبدیل می‌کند. هویت
Nexora همچنان دقیقاً یک owner دارد و هیچ password، self-registration، invitation
یا multi-user RBAC اضافه نشده است.

## WebAuthn و bootstrap

- verification رمزنگاری با `webauthn==2.7.0` انجام می‌شود؛
- `cbor2==5.7.1` به‌صورت صریح pin شده است تا Python 3.13 روی macOS Intel نیز از
  wheel ازپیش‌ساخته‌شده استفاده کند و برای نصب runtime به Rust نیاز نباشد؛
- فقط ES256 و EdDSA و `userVerification=required` مجازند؛
- origin و RP ID از canonical origin خصوصی و به‌صورت exact بررسی می‌شوند؛
- challengeها ۲۵۶ بیتی، پنج‌دقیقه‌ای و single-use هستند؛
- دستور `nexora-identity create-bootstrap-token` یک token ۲۵۶ بیتی و ده‌دقیقه‌ای
  می‌سازد؛ بعد از ثبت اولین passkey، bootstrap دوباره مجاز نیست؛
- private key هرگز به Nexora نمی‌رسد و فقط public key، credential ID، counter و
  transportهای محدود ذخیره می‌شوند.

## Session و recovery

فقط digest SHA-256 توکن session و CSRF در PostgreSQL ذخیره می‌شود. cookie برابر
`__Host-nexora_session; Secure; HttpOnly; SameSite=Strict; Path=/` است. timeout
idle برابر ۳۰ دقیقه، timeout مطلق ۱۲ ساعت، rotation برابر ۱۵ دقیقه، grace برابر
۳۰ ثانیه و سقف session فعال برابر پنج است.

ده recovery code مستقل با ۱۲۸ بیت entropy فقط یک بار نمایش داده می‌شوند و تنها
digest آن‌ها ذخیره می‌شود. recovery همه‌ی sessionها و passkeyهای فعال را revoke
می‌کند و بلافاصله یک registration challenge جدید لازم دارد.

## PostgreSQL و audit

migration `20261026_0003` جدول‌های `webauthn_credentials`،
`webauthn_challenges`، `bootstrap_tokens`، `recovery_codes`، `sessions`،
`service_tokens` و `security_audit_events` را اضافه می‌کند. audit با trigger در
برابر UPDATE و DELETE immutable است. هیچ raw token، recovery code یا private key
در schema وجود ندارد.

## private runtime

فایل `infra/compose/private-single-host.yml` فقط port 443 را روی آدرس private
overlay صریح bind می‌کند. API، web، worker و PostgreSQL روی networkهای داخلی
می‌مانند. TLS certificate/key و secretهای runtime فقط از فایل‌های read-only
operator mount می‌شوند. startup هیچ migration خودکاری انجام نمی‌دهد.

متغیرهای `NEXORA_DEV_DB_PASSWORD_FILE` و
`NEXORA_MIGRATION_DATABASE_DSN_FILE` متعلق به orchestration و migration هستند؛
loader پایه فقط همین دو نام دقیق را نادیده می‌گیرد و هر متغیر ناشناخته یا typo
دیگری با پیشوند `NEXORA_` همچنان fail-closed رد می‌شود.

این مرحله live trading، wallet، exchange credential، دسترسی مستقیم به دیتابیس
TRD Bot، public-internet deployment یا autonomous AI execution اضافه نمی‌کند.

## اجرای گیت‌ها

```bash
uv run ruff format --check apps/server alembic
uv run ruff check apps/server alembic
uv run mypy
uv run pytest -m "not integration" -q
uv run alembic upgrade head
uv run pytest apps/server/tests/test_postgresql_integration.py \
  apps/server/tests/test_identity_integration.py -m integration -q
uv run alembic downgrade base
uv run alembic upgrade head
uv run alembic check
uv run python scripts/verify_single_owner_identity_runtime.py
uv run python -m unittest discover -s tests -v
docker compose -f infra/compose/private-single-host.yml config --quiet
```

## شواهد Freeze

- Candidate SHA: `e7ea5484aaac6a9b2a60e25282044ad4c9649e20`
- قرارداد: `003936dfdde1bcfdc46075d698e41e550d1ce99d6b51e32b0aa2d0fa7dc940e2`
- اجرای اصلی CI: `40322981155`
- شش workflow رگرسیون نیز روی همان Candidate SHA با نتیجه `success` ثبت شدند.

گام بعد فقط `NEX-P1-ACCEPTANCE` است. این Freeze هنوز ادعای آمادگی production،
public-internet deployment، live execution، wallet یا autonomous AI ندارد.
