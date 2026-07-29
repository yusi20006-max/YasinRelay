# YasinRelay Core v2

پلی بین کانال‌های تلگرام و ایتا: محتوا را دریافت می‌کند، با AI پردازش می‌کند، و در یک کانال ایتا منتشر می‌کند.

در نسخه ۲ هسته، قابلیت‌های کلیدی جدیدی مانند **موتور پایپ‌لاین پیشرفته (Pipeline Engine)**، **ذخیره‌سازی دیتابیس محلی (SQLite)**، **سیستم هوشمند حذف تکراری‌ها (Deduplication)**، **زمان‌بند سبک بومی (Scheduler)**، **پیکربندی منعطف** و **سیستم لاگینگ ساختاریافته** پیاده‌سازی شده‌اند.

---

## نمودار معماری هسته v2 به همراه موتور پایپ‌لاین (Pipeline Engine)

```
                       [Telegram Channels]
                                |
                                v
                       +----------------+
                       | CollectorStage |  <- Subprocess Go CLI
                       +--------+-------+
                                |
                                v (Raw Post Contexts)
                       +--------+-------+
                       |NormalizerStage |  <- پاک‌سازی و تراز متن
                       +--------+-------+
                                |
                                v
                       +--------+-------+
                       | ValidatorStage |  <- صحت‌سنجی ساختار پیام
                       +--------+-------+
                                |
                                v
                       +--------+-------+
                       |DuplicateStage  |  <- تطبیق با پایگاه‌داده SQLite
                       +--------+-------+
                                |
                                v (پست‌های یکتا)
                       +--------+-------+
                       |AIProcessorStage|  <- بهبود و ترجمه با هوش مصنوعی
                       +--------+-------+
                                |
                                v
                       +--------+-------+
                       | MediaPrepStage |  <- پیش‌پردازش تصاویر و رسانه‌ها
                       +--------+-------+
                                |
                                v
                       +--------+-------+
                       | PublisherStage |  <- انتشار نهایی در ایتا
                       +----------------+
```

---

## نصب و راه‌اندازی

### ۱. پیش‌نیازها
مطمئن شوید پایتون ۳.۸+ و Go روی سیستم شما نصب هستند.

### ۲. شبیه‌سازی و نصب وابستگی‌ها
```bash
git clone https://github.com/yusi20006-max/YasinRelay.git
cd YasinRelay
pip install -r requirements.txt
```

### ۳. کامپایل باینری دریافت‌کننده (Go CLI)
```bash
cd fetcher
go build -o openfeed-fetch main.go
cd ..
```

### ۴. ساخت فایل تنظیمات محیطی (.env)
یک فایل `.env` بر اساس نمونه بسازید و مقادیر را پر کنید:
```bash
cp .env.example .env
```

---

## متغیرهای پیکربندی (Environment Variables)

پروژه به طور کامل از متغیرهای محیطی زیر پشتیبانی می‌کند:

| متغیر | مقدار پیش‌فرض | توضیحات |
| :--- | :--- | :--- |
| `EITAA_TOKEN` | - | توکن بات/حساب کاربری ایتایار |
| `EITAA_CHANNEL` | - | کانال مقصد ایتا (مانند `@my_channel`) |
| `SOURCE_CHANNELS` | - | کانال‌های منبع تلگرام (جداشده با کاما) |
| `DATABASE_PATH` | `relay.db` | مسیر فایل دیتابیس SQLite |
| `LOG_LEVEL` | `INFO` | سطح لاگینگ سیستم (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `FETCH_INTERVAL_SECONDS` | `3600` | بازه زمان‌بندی قدیمی در حالت `--loop` |
| `SCHEDULE_INTERVAL` | `1800` | بازه زمان‌بندی جدید در حالت `--schedule` (ثانیه) |
| `AI_PROVIDER` | `passthrough` | ارائه‌دهنده سرویس هوش مصنوعی |
| `AI_API_KEY` | - | کلید دسترسی API برای هوش مصنوعی |
| `AI_BASE_URL` | `https://api.openai.com/v1` | آدرس پایه API هوش مصنوعی |
| `AI_MODEL` | `gpt-4o-mini` | مدل زبان مورد استفاده |

---

## نحوه اجرا و حالت‌های کاربری

هسته YasinRelay سه حالت اصلی برای اجرا ارائه می‌دهد:

### ۱. اجرای تکی و ساده (Single Run)
کل پایپ‌لاین را برای تمام کانال‌های منبع یک بار اجرا کرده و متوقف می‌شود:
```bash
python3 -m yasinrelay.cli run
```

برای اعمال محدودیت در تعداد دریافت هر کانال:
```bash
python3 -m yasinrelay.cli run --limit 5
```

برای اجرای اختصاصی روی یک کانال خاص:
```bash
python3 -m yasinrelay.cli run --channel @some_channel
```

### ۲. اجرای زمان‌بندی شده جدید (Recommended - Scheduled Run)
اجرا با استفاده از سیستم زمان‌بند بومی و سبک نسخه ۲ (استفاده از بازه `SCHEDULE_INTERVAL`):
```bash
python3 -m yasinrelay.cli run --schedule
```

### ۳. اجرای دوره‌ای قدیمی (Legacy Loop Run)
اجرای دوره‌ای بر اساس زمان‌بندی قدیمی (`FETCH_INTERVAL_SECONDS`):
```bash
python3 -m yasinrelay.cli run --loop
```

---

## مستندات توسعه و تست‌ها

### ساختار دایرکتوری‌های پروژه
```
yasinrelay/
├── yasinrelay/
│   ├── storage/          # لایه پایگاه‌داده SQLite و مدل‌ها
│   ├── pipeline_engine.py# موتور ماژولار و مراحل پایپ‌لاین (Phase 2)
│   ├── ai_processor.py   # رابط AIProcessor و پردازشگرها
│   ├── media_processor.py# رابط پردازش تصویر، ویدیو و فایل
│   ├── logging_config.py # پیکربندی لاگ‌ها روی کنسول و فایل
│   ├── scheduler.py      # زمان‌بند بومی سبک
│   ├── pipeline.py       # رابط سازگار پایپ‌لاین به همراه موتور پیشرفته داخلی
│   └── cli.py            # رابط خط فرمان (CLI)
├── fetcher/              # لایه دریافت Go (فرانت-اند تلگرام به صورت subprocess)
├── tests/                # تست‌های تستی و یکپارچه‌سازی کامل
└── logs/                 # محل ذخیره‌سازی فایل‌های لاگ (relay.log, error.log)
```

### اجرای تست‌ها
تست‌های خودکار پایتون را با دستور زیر اجرا کنید:
```bash
python3 -m pytest -v
```

تست‌های Go بخش فچر تلگرام:
```bash
cd fetcher
go test -v
cd ..
```


---

## پلتفرم پیشرفته و یکپارچه ایجنت (Agent Platform - نسخه ویژه)

پلتفرم ایجنت یا **Yasin Agent Platform** یک معماری مدولار، با قابلیت توسعه بالا و مناسب برای محیط‌های پروداکشن است که به عنوان زیرساخت اصلی برای کارهای پیشرفته‌ی آینده اضافه شده است.

### ۱. سیستم چرخه حیات و هوک‌ها (Lifecycle Hooks)
چرخه‌ی حیات ایجنت شامل هوک‌های اختیاری مختلفی است که به توسعه‌دهندگان اجازه می‌دهد رفتارهای دلخواه را در بخش‌های مختلف فرآیند تزریق کنند. هوک‌ها تاثیری در ساختار قبلی سیستم ایجاد نمی‌کنند.

هوک‌های موجود:
- `before_plan`: قبل از ایجاد برنامه‌ی اولیه توسط Planner.
- `after_plan`: پس از نهایی شدن برنامه‌ی اجرایی.
- `before_execute`: درست قبل از شروع اجرای فرآیند کلی یا گام‌های ورک‌فلو.
- `after_execute`: پس از تکمیل کامل اجرای فرآیند.
- `before_tool`: قبل از اجرای هر ابزار یا پلاگین خاص.
- `after_tool`: پس از دریافت پاسخ از ابزار یا پلاگین.
- `on_retry`: در هنگام تلاش مجدد برای اجرای کارهای ناموفق.
- `on_error`: وقوع هرگونه خطا در زمان اجرا.
- `on_success`: اجرای کاملاً موفق کارهای واگذار شده.
- `on_finish`: اتمام نهایی (موفقیت‌آمیز یا ناموفق).

**نمونه کد استفاده از هوک‌ها:**
```python
from yasinrelay.agent import LifecycleHooks

hooks = LifecycleHooks()
hooks.register("before_plan", lambda task: print(f"در حال برنامه‌ریزی برای: {task}"))
hooks.register("on_error", lambda exc: print(f"خطایی رخ داد: {exc}"))

# فراخوانی در زمان اجرا
hooks.trigger("before_plan", task="پردازش پست‌ها")
```

---

### ۲. گذرگاه رویدادها (Event Bus)
یک پیام‌رسان درون‌برنامه‌ای سبک و کاملاً مبتنی بر استاندارد پایتون برای باخبر کردن بخش‌های مختلف سیستم از رویدادها بدون ایجاد وابستگی مستقیم (Loose Coupling).

رویدادهای از پیش‌ تعریف شده (Built-in Events):
- `TaskStarted` (شروع تسک)
- `TaskFinished` (اتمام موفق تسک)
- `TaskFailed` (شکست تسک)
- `ToolStarted` (شروع اجرای ابزار)
- `ToolFinished` (پایان اجرای ابزار)
- `RetryStarted` (شروع تلاش مجدد)
- `RetryFinished` (پایان تلاش مجدد)
- `StateChanged` (تغییر وضعیت داخلی کانتکست)

**مثال اشتراک و انتشار رویداد:**
```python
from yasinrelay.agent import EventBus, TASK_STARTED

bus = EventBus()

# ثبت شنونده
def log_task_start(task_name):
    print(f"رویداد: تسک {task_name} شروع شد.")

bus.subscribe(TASK_STARTED, log_task_start)

# انتشار رویداد
bus.publish(TASK_STARTED, task_name="ارسال پیام به ایتا")
```

---

### ۳. تنظیمات مرکزی ایجنت (Central Configuration)
پلتفرم ایجنت دارای تنظیمات اختصاصی است که اولویت بارگذاری آن‌ها به صورت زیر است:
1. مقادیر پیش‌فرض هوشمند
2. خواندن از متغیرهای محیطی سیستم (Environment Variables)
3. خواندن از فایل کانفیگ فرمت JSON اختیاری (به عنوان ورودی سازنده کلاس)

تنظیمات پشتیبانی شده:
- `retry_count` (تعداد تلاش‌های مجدد برای اجرای ابزارها) - از طریق `AGENT_RETRY_COUNT`
- `retry_delay` (تاخیر بین تلاش‌ها) - از طریق `AGENT_RETRY_DELAY`
- `tool_timeout` (حداکثر زمان اجرای ابزار) - از طریق `AGENT_TOOL_TIMEOUT`
- `planner_timeout` (حداکثر زمان طراحی فرآیند) - از طریق `AGENT_PLANNER_TIMEOUT`
- `max_parallel_tools` (حداکثر ابزارهای موازی قابل اجرا) - از طریق `AGENT_MAX_PARALLEL_TOOLS`
- `log_level` (سطح ثبت لاگ‌ها) - از طریق `AGENT_LOG_LEVEL`

---

### ۴. معماری حافظه گسترش‌پذیر (Memory Architecture)
زیرساخت حافظه به صورت سلسله‌مراتبی و با واسط‌های استاندارد جهت پیاده‌سازی ساده و بومی حافظه‌های مختلف پیاده‌سازی شده است:

- `BaseMemory`: کلاس انتزاعی مادر برای تمام حافظه‌ها.
- `TaskMemory`: حافظه کوتاه‌مدت مخصوص ذخیره‌سازی داده‌های موقت یک تسک خاص.
- `SessionMemory`: حافظه در سطح جلسه اجرایی (Session) که در طول زمان زنده بودن ایجنت حفظ می‌شود.
- `ConversationMemory`: حافظه‌ی بهینه‌سازی شده برای چت‌ها و پیام‌های محاوره‌ای دوطرفه (شامل نقش‌های `user` و `assistant`) جهت اتصال به مدل‌های LLM.

---

### ۵. مدیریت زمینه و تاریخچه (Context Manager)
کلاس `ContextManager` مسئول نگه‌داری وضعیت لحظه‌ای، متغیرهای به اشتراک گذاشته شده، متادیتای اجرای تسک‌ها و تاریخچه کامل فرآیند (Execution History) است. کانتکست به نحوی طراحی شده که اطلاعات نهایی را کاملاً متناسب با ساختار ورودی ترنسفورمرها و مدل‌های LLM ارائه دهد.

**خروجی مخصوص LLM:**
```python
from yasinrelay.agent import ContextManager

ctx = ContextManager()
ctx.set_variable("user_id", 12345)
ctx.log_history_step("action_taken", {"tool": "translator"})

# دریافت کانتکست مناسب برای مدل هوش مصنوعی
llm_input = ctx.get_llm_context()
```

---

### ۶. سیستم برنامه‌ریز (Planner Interface)
رابط برنامه‌ریز به شکل چند پیاده‌سازی مجزا و سازگار طراحی شده است:
- `BasePlanner`: رابط مادر.
- `TemplatePlanner`: برنامه‌ریز مبتنی بر قوانین و قالب‌های پیش‌فرض (استاتیک).
- `StubLLMPlanner`: شبیه‌ساز برنامه‌ریزی پویا بر اساس هوش مصنوعی جهت یکپارچه‌سازی آسان با LLM در گام‌های بعدی.

---

### ۷. موتور ورک‌فلو و اجرای موازی (Workflow Engine)
سیستم اجرای فرآیندها توانایی مدیریت ساختارهای پیچیده از جمله:
- **اجرای شرطی (Conditional Execution):** تنها در صورت برآورده شدن شرطِ گام اجرا می‌شود.
- **اجرای موازی (Parallel Tasks):** با کمک `ThreadPool` و محدودیت `max_parallel_tools` چند گام را همزمان پیش می‌برد.
- **ورک‌فلوهای تودرتو (Nested Tasks & Sub-workflows):** امکان اختصاص دادن یک ساب‌ورک‌فلو کامل به عنوان یک گام اجرایی.

---

### ۸. راهنمای توسعه‌دهندگان پلاگین و کشف خودکار (Plugin Developer Guide)
پلتفرم ایجنت از قابلیت کشف خودکار پلاگین‌ها (**Automatic Plugin Discovery**) برخوردار است. کافی است فایل‌های پلاگین را در پوشه `plugins/` پروژه قرار دهید； سیستم به صورت کاملاً ایزوله و امن آن‌ها را لود می‌کند و در صورت شکست هر یک، اجرای کلی برنامه کرش نخواهد کرد.

#### نمونه ساختار یک پلاگین:
یک فایل پایتون در پوشه `plugins` ایجاد کنید (به عنوان مثال `plugins/my_tool.py`):

```python
from yasinrelay.agent import register_plugin

@register_plugin("my_custom_plugin")
class MyCustomPlugin:
    """توضیح کوتاه درباره کاربرد پلاگین شما"""

    def execute(self, text: str) -> str:
        return f"[پردازش‌شده] {text}"
```

سیستم به صورت خودکار با فراخوانی متد زیر پلاگین‌های جدید را شناسایی می‌کند:
```python
from yasinrelay.agent import discover_plugins, registry

# جستجو و لود پلاگین‌ها
discover_plugins("plugins")

# دسترسی به پلاگین ثبت شده
my_plugin = registry.get_plugin("my_custom_plugin")
```


---

## سیستم رویدادها و لایه یکپارچه‌سازی هسته (Core Event Bus & Integration Layer)

هسته v2 پروژه YasinRelay به یک گذرگاه رویداد داخلی (Event Bus) و لایه ادغام (Integration Layer) مجهز شده است تا سیستم‌های خارجی (همچون YasinPress-AI-Engine، Yasin Agent و پلاگین‌ها) بتوانند بدون تغییر در معماری پایپ‌لاین هسته، با آن تعامل داشته باشند.

### ۱. رویدادهای استاندارد هسته (Core Events)
رویدادهای زیر در بخش‌های مختلف فرآیند پردازش و ارسال تولید و منتشر می‌شوند:
- `ContentReceived` (دریافت پست خام در `CollectorStage`)
- `ContentNormalized` (نرمال‌سازی موفق متن در `NormalizerStage`)
- `DuplicateDetected` (تشخیص پست تکراری در `DuplicateDetectionStage`)
- `ProcessingStarted` (آغاز رسمی پردازش آیتم در پایپ‌لاین)
- `AIProcessingCompleted` (تکمیل فرآیند پردازش با هوش مصنوعی در `AIProcessorStage`)
- `MediaProcessingCompleted` (تکمیل پردازش تصویر یا رسانه در `MediaProcessorStage`)
- `PublishingStarted` (آغاز ارسال محتوا به مقصد در `PublisherStage`)
- `PublishingCompleted` (انتشار نهایی کاملاً موفق محتوا در ایتا)
- `ProcessingFailed` (وقوع استثنا یا بروز خطا و نامعتبر بودن در کل پایپ‌لاین)

### ۲. مثال نحوه عضویت و گوش دادن به رویدادها (Event Bus Subscription)
برای استفاده از گذرگاه رویداد، کافیست شنونده‌های خود را ثبت کنید. برای پایداری ۱۰۰٪ سیستم، وقوع خطا در هندلرها هرگز مانع اجرای ادامه فرآیند پایپ‌لاین نخواهد شد (Isolation):

```python
from yasinrelay import get_event_bus, EVENT_CONTENT_RECEIVED, PipelineEvent

bus = get_event_bus()

# ثبت شنونده برای یک رویداد خاص
def on_new_content(event: PipelineEvent):
    print(f"[شنونده] پست جدید دریافت شد: {event.content_id}")
    print(f"محتوا: {event.payload.get('post', {}).get('text')}")

bus.subscribe(EVENT_CONTENT_RECEIVED, on_new_content)

# ثبت شنونده سراسری برای تمام رویدادها (Wildcard)
def on_any_event(event: PipelineEvent):
    print(f"[شنونده سراسری] رویداد {event.name} رخ داد.")

bus.subscribe("*", on_any_event)
```

### ۳. لایه یکپارچه‌سازی و ثبت ارائه‌دهندگان سفارشی (Integration Layer & Custom Registry)
با استفاده از `integration_registry` سراسری، سیستم‌های دیگر و افزونه‌ها می‌توانند پیاده‌سازی‌های سفارشی خود را برای بخش‌های مختلف هسته (مانند هوش مصنوعی، منابع فید، پردازشگر رسانه و ناشران جدید) بدون دستکاری کدهای هسته رجیستر و تزریق کنند:

```python
from yasinrelay import integration_registry, ContentProcessor, Post, ProcessedContent

# ثبت یک ارائه‌دهنده هوش مصنوعی سفارشی با استفاده از دکوراتور
@integration_registry.register_ai_provider("my_advanced_ai")
class MyAdvancedAI(ContentProcessor):
    def process(self, post: Post) -> ProcessedContent:
        # پردازش سفارشی شما
        return ProcessedContent(source_post=post, text=f"[پردازش‌شده با هوش مصنوعی من] {post.text}")

# بازیابی ارائه‌دهنده
ai_provider_cls = integration_registry.get_ai_provider("my_advanced_ai")
```

### ۴. ساختار افزونه‌های کامل (Complete Plugins Structure)
برای افزودن قابلیت‌های چندگانه و بزرگ، می‌توانید کلاس افزونه‌ای تعریف کنید که از `IntegrationPlugin` ارث‌بری کرده و پس از ساخت، آن را رجیستر نمایید تا در زمان لود، هوک‌ها و شنونده‌های رویداد خود را متصل سازد:

```python
from yasinrelay import IntegrationPlugin, get_event_bus, EVENT_PUBLISHING_COMPLETED, PipelineEvent

class AnalyticsPlugin(IntegrationPlugin):
    @property
    def plugin_name(self) -> str:
        return "system_analytics"

    def initialize(self, event_bus) -> None:
        event_bus.subscribe(EVENT_PUBLISHING_COMPLETED, self.track_metrics)

    def track_metrics(self, event: PipelineEvent):
        # ذخیره آمارهای ارسال موفق
        print(f"محتوای با شناسه {event.content_id} در تحلیل آماری ثبت شد.")
```

### ۵. متغیرهای پیکربندی جدید رویدادها
می‌توانید قابلیت‌های فوق را از طریق فایل `.env` نیز شخصی‌سازی کنید:
- `EVENT_BUS_ENABLED`: فعال یا غیرفعال کردن کل سیستم رویدادها (پیش‌فرض: `true`)
- `EVENT_LOGGING_ENABLED`: ثبت لاگ‌های دیباگ ساختاریافته رویدادها در کنسول/فایل لاگ (پیش‌فرض: `true`)
