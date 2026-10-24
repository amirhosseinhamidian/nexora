# NEX-P0-04 — مرز امنیت، هویت و استقرار خصوصی

وضعیت: **Candidate**

تاریخ تصمیم: `2026-10-24`

پیش‌نیاز: `NEX-P0-03` در وضعیت Frozen

گام مجاز بعدی: `NEX-P0-04-FREEZE`

## هدف

این مرحله مشخص می‌کند چه کسی و از چه مسیری به Nexora دسترسی دارد، session و
credential چگونه محافظت می‌شوند، ارتباط backend با TRD Bot چگونه احراز هویت
می‌شود و نسخه شخصی در چه topologyای اجازه استقرار دارد.

خروجی این مرحله contract، threat model، schema، fixture، ADR و verifier است.
هیچ login page، WebAuthn endpoint، reverse proxy، VPN، secret واقعی یا backup
runtime در `NEX-P0-04` ساخته نمی‌شود. ادعای امنیت production پیش از پیاده‌سازی
و acceptance مراحل runtime ممنوع است.

## مدل عملیاتی نسخه ۰.۱

Nexora در این نسخه:

- فقط یک مالک انسانی دارد؛
- self-registration، invitation و workspace ندارد؛
- به Identity Provider ابری وابسته نیست؛
- از اینترنت عمومی قابل دسترس نیست؛
- همچنان هیچ قابلیت live trading، wallet یا exchange credential ندارد؛
- frontend هیچ secret یا service token دریافت نمی‌کند.

اصل authorization برابر `deny by default` است. سه principal مستقل داریم:
`owner`، `nexora_worker` و `trd_bot_integration`. هرکدام فقط scopeهای لازم خود
را دریافت می‌کنند و service principal نمی‌تواند نقش مالک را به دست آورد.

## احراز هویت مالک

ورود اصلی `WebAuthn passkey` است و user verification باید انجام شود. RP ID و
Origin دقیقاً از canonical HTTPS origin خصوصی مشتق می‌شوند. الگوریتم‌های مجاز
`ES256` و `EdDSA` هستند و private key همیشه در authenticator باقی می‌ماند.

در web هیچ password login، email password reset یا security question وجود
ندارد. این تصمیم علاوه بر کاهش سطح حمله، نیاز به email provider را از نسخه
شخصی حذف می‌کند.

### Bootstrap اولیه

CLI محلی یک token تصادفی ۲۵۶ بیتی تولید می‌کند که:

- فقط یک بار قابل استفاده است؛
- ده دقیقه اعتبار دارد؛
- فقط روی loopback یا private network پذیرفته می‌شود؛
- بعد از ثبت اولین passkey برای همیشه غیرفعال می‌شود.

### Recovery

در زمان enrollment ده recovery code مستقل تولید می‌شود. هر code حداقل ۱۲۸ بیت
entropy دارد، فقط یک بار نمایش داده می‌شود و در پایگاه داده فقط digest آن
نگهداری می‌شود. استفاده از recovery، تمام sessionها را revoke می‌کند و ثبت
فوری passkey جدید را اجباری می‌سازد. اگر recovery code هم در دسترس نباشد، تنها
مسیر باقی‌مانده CLI محلی با دسترسی مستقیم به host است.

## Session و حفاظت درخواست

sessionها opaque و server-side هستند؛ JWT طولانی‌عمر به browser داده نمی‌شود.
token تصادفی ۲۵۶ بیتی است و server فقط SHA-256 digest آن را نگهداری می‌کند.
cookie قرارداد زیر را دارد:

```text
__Host-nexora_session; Secure; HttpOnly; SameSite=Strict; Path=/
```

ویژگی `Domain` تنظیم نمی‌شود. session credential در localStorage،
sessionStorage یا IndexedDB قرار نمی‌گیرد.

| کنترل | مقدار |
| --- | --- |
| idle timeout | ۳۰ دقیقه |
| absolute timeout | ۱۲ ساعت |
| rotation interval | ۱۵ دقیقه |
| rotation grace | ۳۰ ثانیه |
| concurrent sessions | حداکثر ۵ |
| recent reauthentication | حداکثر ۵ دقیقه قبل از عملیات حساس |

تمام mutationها علاوه بر SameSite به synchronizer CSRF token و تطبیق دقیق
Origin نیاز دارند. CORS برای origin خارجی خالی است و mutation فقط
`application/json` می‌پذیرد. پاسخ‌های authenticated با `Cache-Control: no-store`
ارسال می‌شوند.

## عملیات حساس

موارد زیر فقط برای مالک و پس از reauthentication تازه مجازند:

- ثبت یا revoke کردن passkey؛
- چرخش recovery code؛
- چرخش service token؛
- ایجاد و restore کردن backup؛
- export گزارش security audit.

هیچ scope مربوط به سفارش واقعی، کیف پول یا credential صرافی در authorization
مدل وجود ندارد.

## ارتباط امن با TRD Bot

قرارداد `NEX-P0-03` اکنون transport و authentication مشخص دارد. Nexora server
از TLS روی private network و یک bearer token تصادفی ۲۵۶ بیتی استفاده می‌کند.
token:

- فقط در backend و از mounted secret file خوانده می‌شود؛
- هرگز به browser یا export وارد نمی‌شود؛
- در TRD Bot فقط به شکل HMAC-SHA-256 digest همراه server pepper ذخیره می‌شود؛
- با constant-time comparison بررسی می‌شود؛
- حداکثر ۹۰ روز عمر و ۲۴ ساعت overlap چرخش دارد؛
- فقط scopeهای snapshot/event/export و decision review نوع Paper/Shadow دارد.

capability negotiation قرارداد v1 قبل از sync همچنان اجباری است. private
network جای schema validation، checksum، idempotency یا authorization را
نمی‌گیرد.

## پروفایل‌های استقرار

| Profile | وضعیت | شبکه | داده production |
| --- | --- | --- | --- |
| `local_development` | مجاز | loopback | ممنوع |
| `private_single_host` | پروفایل production | private overlay + HTTPS | مجاز |
| `public_internet` | غیرمجاز در v0.1 | — | ممنوع |

در production فقط reverse proxy روی پورت `443` در private overlay در دسترس
است. PostgreSQL و worker هیچ host port ندارند و web/API/database/worker روی
container networkهای بخش‌بندی‌شده قرار می‌گیرند. TLS حداقل نسخه `1.3`، disk
encryption و canonical origin allowlist الزامی هستند. outbound traffic نیز به
صورت پیش‌فرض بسته و فقط برای dependencyهای ثبت‌شده مانند endpoint دقیق TRD Bot
باز می‌شود.

## Security headers

سیاست machine-readable در `contracts/security/v1/security-headers.json` ثبت
شده و حداقل شامل CSP nonce-based، HSTS، `nosniff`، منع frame،
`Referrer-Policy: no-referrer`، Permissions Policy محدود، COOP/CORP و no-store
است. `unsafe-inline`، `unsafe-eval` و report-only به‌عنوان وضعیت نهایی production
پذیرفته نیستند. هدرهای افشاگر `Server` و `X-Powered-By` حذف می‌شوند.

## Secret boundary

production secret فقط از فایل read-only با permission برابر `0400` inject
می‌شود. فایل environment محلی صرفاً برای development و خارج از Git مجاز است.
secret در موارد زیر ممنوع است:

- repository و lock artifact؛
- container image یا build argument؛
- database application row؛
- log، trace و error response؛
- browser bundle و browser storage؛
- exportهای `private` و `ai_safe`.

CI باید secret scan داشته باشد، هر secret owner و برنامه rotation داشته باشد و
logging بعداً بر پایه allowlist و redaction ساختاری پیاده شود.

## Backup و Restore

database و artifact backup با `age X25519` برای recipient آفلاین رمز می‌شوند.
private key recipient روی runtime host قرار نمی‌گیرد. هر backup manifest و
SHA-256 checksum دارد. export جای backup نیست.

restore فقط با حضور مالک و reauthentication تازه انجام می‌شود. پس از restore،
تمام sessionها revoke و service tokenها rotate می‌شوند. پیش از release نهایی،
restore drill واقعی باید ثبت شود.

## Audit امنیتی

رویدادهای امنیتی append-only، UTC و دارای actor، target، correlation ID، outcome
و reason code هستند. raw IP ذخیره نمی‌شود؛ در صورت نیاز فقط HMAC آن ثبت می‌شود.
password، passkey challenge، recovery code، cookie، bearer token، private key و
payload مالی در audit metadata ممنوع‌اند.

رویدادهای اجباری شامل bootstrap، موفقیت/شکست ورود، ایجاد/چرخش/revoke session،
تغییر credential، recovery، چرخش service token، authorization denial، rate
limit و عملیات backup/restore هستند.

## Threat model

Threat model ماشین‌خوان ده سناریوی اصلی را پوشش می‌دهد:

- جعل هویت مالک؛
- سرقت و replay کردن session؛
- CSRF و تغییر غیرمجاز state؛
- نشت secret از Git/log/browser/export؛
- privilege escalation توسط worker یا integration token؛
- payload ناسازگار یا مخرب TRD Bot؛
- exposure پورت database یا worker؛
- نبود قابلیت attribution؛
- abuse روی authentication/recovery؛
- backup ناقص یا بدون رمزنگاری.

این مدل در برابر compromise کامل دستگاه مالک یا root compromise کامل host
ادعای حفاظت نمی‌کند. این موارد residual risk عملیاتی هستند و باید با امنیت
دستگاه، patching، disk encryption و backup آفلاین کاهش یابند.

## مرجع استانداردها

snapshot تصمیم بر پایه منابع رسمی زیر در تاریخ `2026-10-24` ثبت شده است:

- OWASP ASVS `5.0.0`؛
- OWASP Authentication، Session Management و Authorization Cheat Sheets؛
- NIST SP 800-63B-4.

این منابع baseline طراحی هستند، نه ادعای certification یا انطباق کامل. هدف
نسخه شخصی، selected controls نزدیک به ASVS Level 2 است و verification واقعی
در مراحل runtime و acceptance انجام خواهد شد.

## موارد خارج از محدوده

- اجرای واقعی WebAuthn و session store؛
- نصب VPN، reverse proxy یا certificate؛
- secret provisioning و backup automation؛
- OAuth/OIDC و identity federation؛
- multi-user RBAC و tenant isolation؛
- public internet hardening؛
- HSM؛
- امنیت live trading.

## معیار پذیرش NEX-P0-04

- Freeze مرحله `NEX-P0-03` معتبر باشد؛
- فقط یک owner انسانی و دو service principal تعریف شده باشند؛
- password login، self-registration و email reset غیرمجاز باشند؛
- WebAuthn، bootstrap و recovery بدون secret persistence خام تعریف شده باشند؛
- server-side session، cookie flags، timeout، rotation و revoke کامل باشند؛
- CSRF، exact origin و same-origin policy اجباری باشند؛
- TRD Bot token محدود، backend-only و قابل‌چرخش باشد؛
- public deployment، public DB و public worker رد شوند؛
- secret در Git/log/export/browser/database رد شود؛
- encrypted backup، checksum و restore drill تعریف شوند؛
- threat model، audit schema و fixture بدون secret معتبر باشند؛
- همه verifierها و تست‌ها سبز باشند.

دستور بررسی:

```bash
python3 scripts/verify_scope_contract.py
python3 scripts/verify_technical_baseline.py
python3 scripts/verify_integration_contracts.py
python3 scripts/verify_security_boundary.py
python3 -m unittest discover -s tests -v
```

خروجی مورد انتظار:

```text
NEX_P0_04_SECURITY_BOUNDARY=PASS
```
