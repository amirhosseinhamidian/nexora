# NEX-P0-01 - تثبیت Scope، بازار هدف و مرز Nexora/TRD Bot

وضعیت: **Frozen**

تاریخ تصمیم: `2026-10-22`

نسخه هدف: `Nexora v0.1.0`

شاخه پیشنهادی: `feature/v0.1-foundation`

قرارداد ماشین‌خوان:
[`contracts/nexora-v0.1-scope.json`](../../contracts/nexora-v0.1-scope.json)

این سند نخستین گیت اجرایی Nexora است. هدف آن جلوگیری از مخلوط‌شدن مسئولیت‌های محصول شخصی
Nexora با موتور تحقیق و معامله TRD Bot و جلوگیری از ورود زودهنگام SaaS، اجرای واقعی یا AI
تصمیم‌گیر به نسخه اول است.

Freeze این سند فقط اجازه ادامه Phase 0 را می‌دهد و به معنی تکمیل معماری، انتخاب Stack، آماده
بودن دیتابیس یا شروع پیاده‌سازی رابط کاربری نیست.

## 1. تصمیم محصول

`Nexora v0.1.0` یک **Personal Portfolio Foundation تک‌مالک** است. محصول داده‌های نسخه‌دار TRD
Bot را در قالب Portfolio، Decision، Risk، Alert، Journal و Export قابل استفاده می‌کند، اما موتور
پیش‌بینی بازار یا اجرای معامله را در Nexora بازنویسی نمی‌کند.

مرزهای ثابت نسخه:

- Nexora و TRD Bot دو پروژه، repository و چرخه انتشار مستقل دارند.
- Nexora در v0.1 فقط `single-owner` است؛ ثبت‌نام عمومی و Multi-tenant وجود ندارد.
- TRD Bot منبع حقیقت Market Data، Strategy، Signal، Candidate، Risk و simulation evidence است.
- Nexora منبع حقیقت Profile، Preference، Watchlist، Portfolio Workspace، Human Review، Journal
  و Export history است.
- ارتباط فقط از API و Event Contract نسخه‌دار انجام می‌شود؛ اتصال مستقیم دیتابیس ممنوع است.
- مسیر مجاز `Observe -> Review -> Shadow/Paper -> Journal -> Export` است.
- Export و AI-readiness قابلیت پایه‌اند؛ AI داخلی و Predictive ML در v0.1 فعال نمی‌شوند.
- Live Execution، حساب صرافی، credential معاملاتی، wallet و انتقال وجه خارج از محدوده‌اند.

## 2. کاربر و مدل عملیاتی

| موضوع | تصمیم فریز شده |
| --- | --- |
| کاربر هدف | مالک پروژه؛ معامله‌گر یا پژوهشگر مستقل |
| tenancy | یک Owner و یک فضای شخصی اصلی |
| deployment | Local یا VPS خصوصی؛ topology نهایی در P0-04 |
| دسترسی | ورود امن بدون public registration |
| زبان | فارسی و انگلیسی |
| theme | روشن و تاریک |
| timezone ذخیره‌سازی | UTC |
| timezone نمایش | قابل تنظیم؛ پیش‌فرض کاربر در Nexora |
| واحد پول | نسخه‌دار در هر Portfolio/Snapshot؛ بدون فرض پنهان |

مدل داده از ابتدا owner-aware است تا مهاجرت آینده ممکن باشد، اما organization، invitation، team،
role hierarchy، billing، subscription و quota در v0.1 پیاده‌سازی نمی‌شوند.

## 3. بازار و Portfolio هدف

بازار مرجع نسخه اول **Crypto Spot** است. Nexora فقط projectionها و evidenceهای تولیدشده توسط
TRD Bot v0.3.x را برای Portfolioهای شبیه‌سازی‌شده مصرف می‌کند.

| موضوع | تصمیم فریز شده |
| --- | --- |
| asset class | Crypto |
| market type | Spot |
| portfolio mode | Shadow و Paper |
| live trading | غیرفعال و ممنوع |
| market source | TRD Bot API/Event؛ بدون تماس مستقیم Nexora با provider |
| provider baseline | همان providerهای allowlisted در TRD Bot v0.3.x |
| timeframe baseline | همان timeframeهای منتشرشده توسط TRD Bot v0.3.x |
| data freshness | از evidence موتور خوانده می‌شود؛ Nexora freshness جعل نمی‌کند |

پشتیبانی عمومی از سهام، فلزات، املاک، حساب بانکی، دارایی فیزیکی یا Multi-asset Portfolio در نسخه
اول تعهد نمی‌شود. مدل Portfolio نباید به Crypto hard-code شود، اما adapter و UX بازار جدید فقط
با قرارداد مستقل همان بازار اضافه خواهند شد.

## 4. مسئولیت دامنه‌ها

### Nexora مالک است

- Owner profile، locale، timezone، theme و preferences؛
- Watchlist و انتخاب view شخصی Market Universe؛
- Portfolio Workspace و snapshotهای محصولی؛
- Decision Review، پذیرش یا رد انسانی برای Paper/Shadow؛
- Alert Inbox state شامل acknowledgement و snooze شخصی؛
- Journal، note، tag و human feedback؛
- Export Job، Export Manifest، checksum و history؛
- AI analysis record در نسخه‌های آینده.

### TRD Bot مالک است

- provider، market observation و normalized data؛
- Dataset، Feature Set، Market Context و Regime؛
- Strategy، Experiment، Signal، Candidate و Ranking؛
- Risk Gate، Position Sizing و Decision Intelligence؛
- Paper/Shadow simulation، Position evidence و Outcome؛
- policy، model و lineage تخصصی موتور.

### قواعد مالکیت مشترک

- Nexora فقط `SourceReference` و projection موردنیاز UI/Export را نگه می‌دارد.
- immutable evidence در Nexora بازنویسی نمی‌شود.
- User note یا review در TRD Bot به‌عنوان market truth ثبت نمی‌شود.
- sync دوباره باید idempotent باشد و duplicate منطقی نسازد.
- حذف projection در Nexora نباید داده منبع TRD Bot را حذف کند.

## 5. قابلیت‌های داخل محدوده v0.1

### Access

- ورود و خروج امن Owner؛
- session lifecycle قابل audit؛
- تنظیم locale، timezone و theme؛
- نبود public registration.

### Observe

- نمایش health و compatibility اتصال TRD Bot؛
- Watchlist شخصی؛
- freshness، quality و degraded state از evidence موتور؛
- Dashboard خلاصه Portfolio، Risk، Decision و Alert.

### Review

- Decision Feed با confidence، uncertainty، reason code و evidence reference؛
- جزئیات Candidate و Risk Gate؛
- نمایش اثر Candidate روی Portfolio شبیه‌سازی‌شده؛
- ثبت accept، reject یا defer انسانی فقط برای Shadow/Paper.

### Track

- Portfolio و Positionهای Shadow/Paper؛
- Alert Inbox با acknowledgement و snooze؛
- Journal و note؛
- ارتباط Decision با Outcome بدون بازنویسی evidence موتور.

### Export

- Export کامل و incremental؛
- فیلتر بر اساس زمان، entity، Portfolio و status؛
- JSON، JSONL، CSV، Parquet و ZIP Bundle؛
- manifest، schema version، source version و checksum؛
- خروجی Private و AI-safe؛
- تاریخچه job و نتیجه verification.

## 6. Export Contract پایه

Export یک قابلیت جانبی نیست و هر Domain تحویلی باید Export coverage مشخص داشته باشد.

هر Bundle حداقل شامل موارد زیر است:

- `schema_version`؛
- `export_id` و `generated_at`؛
- `mode`: یکی از `full`، `incremental` یا `selected`؛
- scope و filterهای اعمال‌شده؛
- timezone و currency/unit context؛
- Nexora و TRD Bot source version؛
- lineage references؛
- فهرست فایل‌ها، media type، row count و SHA-256؛
- redaction profile؛
- completion status.

خروجی ناقص، checksum نامعتبر یا schema ناشناخته نباید به‌عنوان Export موفق منتشر شود.

### Private Export

برای backup و بازیابی شخصی است و داده‌های مجاز کامل Nexora را دارد، اما حتی این حالت نیز secret،
password hash، session token، encryption key یا raw exchange credential را صادر نمی‌کند.

### AI-safe Export

فقط داده لازم برای هدف تحلیل را شامل می‌شود. redaction و pseudonymization باید قبل از انتشار فایل
اعمال شوند. Prompt، model/provider reference، input export ID و نتیجه تحلیل آینده نیز قابل audit و
Export خواهند بود.

## 7. مرز AI و Machine Learning

هر دو پروژه در نسخه‌های آینده ML خواهند داشت، اما مسئولیت آن‌ها جداست.

| مسئله | مالک |
| --- | --- |
| regime، volatility و trend probability | TRD Bot |
| signal quality و candidate ranking | TRD Bot |
| strategy drift و execution quality | TRD Bot |
| Portfolio health و personal risk trend | Nexora |
| تحلیل رفتار تصمیم‌گیری و Human Feedback | Nexora |
| گزارش، RAG و پرسش‌وپاسخ روی داده شخصی | Nexora |

در v0.1 فقط لایه `AI-ready Data` ساخته می‌شود: schema، lineage، Export، Outcome reference و Human
Feedback. AI Copilot و Predictive ML خارج از محدوده‌اند.

قواعد ثابت آینده:

- خروجی AI باید source، model version، input snapshot، uncertainty و زمان داشته باشد.
- کمبود داده باید `insufficient_data` تولید کند، نه پیش‌بینی اجباری.
- مدل جدید ابتدا Research و سپس Shadow ارزیابی می‌شود.
- LLM یا predictive model مجاز به تغییر policy یا ارسال مستقیم سفارش نیست.
- promotion مدل نیازمند benchmark، temporal validation، calibration، drift monitoring و تأیید
  انسانی است.

## 8. مرز Integration با TRD Bot

Baseline سازگاری اولیه `TRD Bot v0.3.x` است. Compatibility Matrix دقیق در P0-03 تولید می‌شود.

قراردادهای ثابت:

- REST API برای query و commandهای allowlisted Shadow/Paper؛
- Event Contract برای Decision، Alert و Outcome؛
- schema version در تمام payloadها؛
- correlation ID برای ردگیری بین دو سیستم؛
- idempotency key برای commandهای تکرارپذیر؛
- health، freshness و compatibility status قابل مشاهده؛
- timeout یا schema ناسازگار به degraded/unavailable منجر می‌شود؛
- fallback پنهان یا خواندن مستقیم دیتابیس مجاز نیست.

اگر Nexora فقط به اصلاح سازگار یا endpoint کوچک نیاز داشته باشد، تغییر باید به شکل TRD Bot
`v0.3.1` یا `v0.3.2` منتشر شود. توسعه TRD Bot v0.4 برای جبران یک شکاف کوچک Integration مجاز نیست.

## 9. موارد صریحاً خارج از محدوده

- SaaS، Multi-tenant، organization و team collaboration؛
- billing، subscription، plan، quota و public registration؛
- native mobile application؛
- اتصال مستقیم Nexora به database داخلی TRD Bot؛
- دریافت مستقیم Market Data از exchange/provider توسط Nexora؛
- اتصال حساب صرافی یا کارگزاری؛
- نگهداری credential دارای مجوز معامله؛
- موجودی واقعی، wallet، deposit، withdrawal، custody یا transfer؛
- ارسال، اصلاح یا لغو سفارش واقعی؛
- portfolio واقعی Multi-asset و Asset Registry کامل؛
- AI Copilot داخلی؛
- Predictive ML و recommendation شخصی‌سازی‌شده production؛
- تغییر policy یا اجرای خودکار توسط AI؛
- تضمین سود یا حذف uncertainty از نمایش تصمیم.

## 10. جریان ارزش مرجع

1. Owner وارد Nexora می‌شود و وضعیت اتصال نسخه‌دار TRD Bot را می‌بیند.
2. Nexora projectionهای allowlisted Portfolio، Decision، Alert و Outcome را sync می‌کند.
3. Owner Portfolio Shadow/Paper، exposure، risk و context را مرور می‌کند.
4. Decision Feed evidence، confidence، uncertainty و reason code را نمایش می‌دهد.
5. Owner برای Paper/Shadow تصمیم accept، reject یا defer ثبت می‌کند.
6. نتیجه و note در Journal ثبت و به SourceReference مرتبط می‌شود.
7. Owner یک Export کامل، selected یا AI-safe تولید و checksum آن را verify می‌کند.

شکست هر مرحله نباید evidence قبلی را معتبرتر جلوه دهد یا state منبع را تغییر دهد.

## 11. قراردادهای سازگاری و امنیت

- Public routeها از ابتدا زیر namespace نسخه‌دار قرار می‌گیرند.
- payload بدون schema version پذیرفته نمی‌شود.
- projectionها source ID، source version و observed-at مستقل دارند.
- زمان canonical برابر UTC است.
- پول و quantity بدون currency/unit معتبر نیستند.
- logging، metrics، trace و Export نباید secret ذخیره کنند.
- route inventory باید نبود live order، wallet و exchange credential را ثابت کند.
- تمام commandهای Shadow/Paper allowlisted، authenticated و idempotent هستند.
- immutable source evidence در Nexora update یا delete نمی‌شود.

## 12. تقسیم Phase 0

| مرحله | خروجی | گیت خروج |
| --- | --- | --- |
| NEX-P0-01 | Scope، بازار هدف، ownership، Export و AI boundary | همین سند و contract معتبر |
| NEX-P0-02 | baseline، Stack، repository layout و debt inventory | ADRهای Stack و bootstrap plan |
| NEX-P0-03 | API/Event/Export contracts و compatibility matrix | fixture و failure semantics |
| NEX-P0-04 | SLO، retention، backup، threat model و capacity budget | targetهای قابل اندازه‌گیری |
| NEX-P0-05 | acceptance matrix و Freeze نهایی Phase 0 | تمام تصمیم‌ها شاهد و owner دارند |

## 13. تصمیم‌های عمداً باز

موارد زیر در P0-01 انتخاب یا hard-code نمی‌شوند:

- Frontend و Backend stack نهایی؛
- monorepo package layout؛
- authentication mechanism و session store؛
- sync بر پایه polling، webhook یا message transport؛
- API endpoint inventory دقیق؛
- PostgreSQL schema و migration tooling؛
- object storage انتخابی؛
- retention و حجم Export؛
- SLO، capacity و performance budget؛
- deployment topology و reverse proxy؛
- design system و navigation نهایی؛
- provider یا مدل AI آینده؛
- SaaS migration plan.

## 14. معیار خروج NEX-P0-01

- [x] Nexora به‌عنوان پروژه مستقل Single-owner تعریف شد.
- [x] Crypto Spot و Portfolioهای Shadow/Paper هدف نسخه اول شدند.
- [x] مالکیت داده Nexora و TRD Bot تفکیک شد.
- [x] اتصال مستقیم دیتابیس ممنوع و Integration نسخه‌دار شد.
- [x] Export-first، فرمت‌ها و redaction baseline ثبت شدند.
- [x] مرز AI/ML دو پروژه و ممنوعیت AI autonomous execution ثبت شد.
- [x] SaaS، Live Execution و credential معاملاتی خارج از محدوده ماندند.
- [x] تصمیم‌های باز به مراحل بعد Phase 0 ارجاع شدند.
- [x] Scope Contract ماشین‌خوان و verifier بدون dependency اضافه شدند.

## 15. شاهد بررسی

روی checkout این مرحله باید فرمان‌های زیر موفق باشند:

```bash
python3 scripts/verify_scope_contract.py
python3 -m unittest discover -s tests -v
git diff --check
```

نتیجه verifier باید دقیقاً شامل این marker باشد:

```text
NEX_P0_01_SCOPE_CONTRACT=PASS
NEX_P0_01_FREEZE=PASS
```

## 16. Freeze evidence

این مرحله بر اساس candidate و اجرای CI زیر فریز شد:

| شاهد | مقدار |
| --- | --- |
| repository | `amirhosseinhamidian/nexora` |
| candidate commit | `da7b9d5c2f04129c055aaf403b196bac4bd7f992` |
| commit message | `docs(nexora): establish v0.1 scope and system boundary` |
| GitHub Actions run | `https://github.com/amirhosseinhamidian/nexora/actions/runs/39763668108` |
| workflow job | `scope-contract` |
| conclusion | `success` |
| Scope Contract checksum | `9ca6c10fb916861bab9a3e8facf7f24e5a84855e97a1f689a48954625377217c` |

GitHub در همان run، verifier و هشت تست Scope Contract را با نتیجه موفق اجرا کرده است. رکورد
ماشین‌خوان Freeze در [`artifacts/p0-01/scope-freeze.json`](../../artifacts/p0-01/scope-freeze.json)
نگهداری می‌شود و verifier تطابق SHA، run URL، checksum و next stage را fail-closed بررسی می‌کند.

گام مجاز بعدی فقط `NEX-P0-02 - baseline، Stack و repository layout` است؛ شروع runtime application
پیش از Freeze کامل Phase 0 مجاز نیست.
