"""
تنظیمات پروژه - همه‌چیز از متغیرهای محیطی (.env) خونده می‌شه.
هیچ ماژول دیگه‌ای مستقیم os.getenv صدا نمی‌زنه؛ همه از اینجا import می‌کنن.
"""
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING", "")

PREFIX = os.getenv("PREFIX", ".")

# --- بات کمکیِ پنل (اختیاری) ---
# چون تلگرام دکمه‌های شیشه‌ای (inline) رو فقط برای پیام‌های ارسالی از طرف یه
# بات واقعی نمایش می‌ده (نه از طرف اکانت شخصی)، دستور «.پنل» از طریق این بات
# جدا (که با توکن BotFather بالا میاد) پنلِ دکمه‌ای رو نشون می‌ده. اگه این
# متغیر خالی بمونه، «.پنل» فقط یه پیام راهنما می‌ده و بقیه‌ی دستورات سلف‌بات
# مثل قبل عادی کار می‌کنن.
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TIMEZONE_OFFSET = float(os.getenv("TIMEZONE_OFFSET", "3.5"))  # پیش‌فرض: تهران (UTC+3:30)
CLOCK_INTERVAL = max(int(os.getenv("CLOCK_INTERVAL", "60")), 30)  # حداقل ۳۰ ثانیه
CLOCK_STYLE_ENV = os.getenv("CLOCK_STYLE", "default")

# --- PostgreSQL (منبع اصلیِ داده‌های دائمی) ---
# فقط از DATABASE_URL خونده می‌شه؛ هیچ Secret/هاست/یوزر/پسورد دیتابیس داخل
# کد نیست. روی Railway وقتی یه Plugin پستگرس اضافه می‌کنی، این متغیر خودکار
# توی سرویس ست می‌شه.
DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "5"))
DB_POOL_RECYCLE_SECONDS = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800"))
DB_ECHO = os.getenv("DB_ECHO", "false").strip().lower() in ("1", "true", "yes", "on")

# --- مسیرهای JSON قدیمی ---
# این فایل‌ها دیگه در زمان اجرا برای ذخیره‌سازی استفاده نمی‌شن (PostgreSQL
# جایگزینشون شده). فقط برای دو مورد نگه داشته شدن:
#   ۱) اسکریپت یک‌بارِ scripts/migrate_json_to_postgres.py که این فایل‌های
#      قدیمی رو می‌خونه و به PostgreSQL منتقل می‌کنه.
#   ۲) سازگاری با مسیر پیش‌فرضِ بکاپ/ایمپورت دستیِ کاربر (دستور پشتیبان/بازیابی).
NOTES_FILE = os.getenv("NOTES_FILE", "notes.json")  # اگه Volume وصل کردی: مثلاً /data/notes.json
AUTOPOST_FILE = os.getenv("AUTOPOST_FILE", "autopost.json")
AUTOPOST_MIN_INTERVAL_MINUTES = 1  # حداقل فاصله مجاز - برای کاهش ریسک اسپم بهتره کمتر از ۵ نذاری
ASSISTANT_FILE = os.getenv("ASSISTANT_FILE", "assistant.json")
FONT_STATE_FILE = os.getenv("FONT_STATE_FILE", "font_state.json")
STATS_FILE = os.getenv("STATS_FILE", "stats.json")

ASSISTANT_ONLINE_THRESHOLD = int(os.getenv("ASSISTANT_ONLINE_THRESHOLD", "180"))  # ثانیه سکوت تا «آفلاین» حساب بشی
ASSISTANT_CHECK_INTERVAL = max(int(os.getenv("ASSISTANT_CHECK_INTERVAL", "30")), 15)  # هر چند ثانیه یک‌بار بازبینیِ محلی (بدون تماس با تلگرام)
ASSISTANT_SCHEDULE_MAX_WINDOWS = max(int(os.getenv("ASSISTANT_SCHEDULE_MAX_WINDOWS", "20")), 1)  # سقفِ تعدادِ بازه‌های زمان‌بندیِ منشی

STATS_SAVE_INTERVAL = 60  # هر چند ثانیه آمار توی PostgreSQL ذخیره بشه

BACKUP_MAX_MESSAGES = 2000
BACKUP_MAX_MEDIA = 50

# --- هوش مصنوعی (اختیاری: .پرسش / .خلاصه / اتصال به .منشی) ---
# یه wrapper سبک روی APIِ چت‌تکمیلیِ سازگار با OpenAI (`/chat/completions`).
# اگه AI_API_KEY خالی بمونه، این قابلیت‌ها فقط یه پیامِ راهنما می‌دن و بقیه‌ی
# دستورات سلف‌بات مثل همیشه عادی کار می‌کنن. AI_API_BASE رو می‌تونی روی هر
# سرویسِ دیگه‌ای (نه فقط OpenAI) که همون فرمتِ درخواست/پاسخ رو داشته باشه ست کنی.
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_API_BASE = os.getenv("AI_API_BASE", "https://api.openai.com/v1")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "600"))
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "30"))
AI_SUMMARY_MAX_MESSAGES = int(os.getenv("AI_SUMMARY_MAX_MESSAGES", "300"))

# برچسبِ مخفیِ «نوشته‌شده با AI» - به انتهای هر پیامی که واقعاً توسطِ
# هوش‌مصنوعی تولید و ارسال می‌شه (پاسخِ `.پرسش`/`.خلاصه`/`.ترجمه‌هوشمند`،
# پاسخِ خودکارِ منشی وقتی `.منشی هوش‌مصنوعی روشن`ه، و ارسالِ `.جواب ارسال`)
# اضافه می‌شه؛ به‌صورتِ اسپویلِ تلگرام (پیش‌فرض محو/جمع‌شده، فقط با تپ دیده
# می‌شه) - نه یه پیشوندِ همیشه‌نمایان - تا هم خودتون بعداً موقعِ مرورِ چت، هم
# طرفِ مقابل (اگه تپ کنه) بتونن تشخیص بدن پیام واقعاً از طرفِ خودِ owner
# نبوده. برای غیرفعال‌کردنِ کامل: AI_TAG_ENABLED=false
AI_TAG_ENABLED = os.getenv("AI_TAG_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
AI_TAG_TEXT = os.getenv("AI_TAG_TEXT", "🤖")

# چند پیامِ آخرِ هر مکالمه (کاربر+منشی، جمعاً) به‌عنوانِ context برای پاسخِ
# هوش‌مصنوعیِ منشی نگه داشته بشه - تا جواب‌ها به همدیگه ربط داشته باشن، نه
# این‌که هر پیام کاملاً مستقل و بدونِ حافظه جواب داده بشه. این حافظه فقط
# درون‌حافظه‌ایه (نه دیتابیس) و با ری‌استارتِ پروسه پاک می‌شه.
ASSISTANT_HISTORY_LIMIT = max(int(os.getenv("ASSISTANT_HISTORY_LIMIT", "10")), 0)

# --- خلاصه‌ی روزانه (`.خلاصه‌روز`) ---
# ساعت/دقیقه‌ی پیش‌فرضِ ارسالِ خودکارِ خلاصه‌ی هر شب (به‌وقتِ محلی، طبقِ
# TIMEZONE_OFFSET) - با `.خلاصه‌روز زمان HH:MM` هم از داخلِ ربات قابلِ تغییره.
DAILY_DIGEST_DEFAULT_HOUR = max(min(int(os.getenv("DAILY_DIGEST_DEFAULT_HOUR", "23")), 23), 0)
DAILY_DIGEST_DEFAULT_MINUTE = max(min(int(os.getenv("DAILY_DIGEST_DEFAULT_MINUTE", "0")), 59), 0)
# سقفِ تعدادِ پیام‌های بررسی‌شده به‌ازای هر چت (برای جلوگیری از هزینه/تایم‌اوتِ AI)
DAILY_DIGEST_MAX_MESSAGES_PER_CHAT = int(os.getenv("DAILY_DIGEST_MAX_MESSAGES_PER_CHAT", "150"))
# سقفِ تعدادِ چت‌هایی که توی حالتِ «کلی» یک‌جا پردازش می‌شن (برای گروه/کانال/پیویِ زیاد)
DAILY_DIGEST_MAX_CHATS = int(os.getenv("DAILY_DIGEST_MAX_CHATS", "40"))

# --- صوت و متن (اختیاری: .رونویسی / .متن‌به‌صوت) ---
# پیش‌فرض: از همون AI_API_KEY/AI_API_BASE بالا استفاده می‌کنن. ولی چون خیلی
# از سرویس‌های واسط/proxy (مثلاً OpenRouter و مشابه‌ها) endpointهای صوتی
# (/audio/speech ، /audio/transcriptions) رو پیاده‌سازی نمی‌کنن - حتی اگه
# برای چت (/chat/completions) کار کنن - این دو متغیرِ جدا رو هم اضافه
# کردیم: اگه ست بشن، فقط بخشِ صوت (.رونویسی/.متن‌به‌صوت) از این‌ها استفاده
# می‌کنه (مثلاً می‌تونی برای AI_API_BASE یه proxy ارزون بذاری ولی برای صوت
# یه کلیدِ واقعیِ OpenAI اینجا بدی). اگه ست نشن، دقیقاً مثلِ قبل از همون
# AI_API_KEY/AI_API_BASE بالا استفاده می‌کنن.
AI_AUDIO_API_KEY = os.getenv("AI_AUDIO_API_KEY", AI_API_KEY)
AI_AUDIO_API_BASE = os.getenv("AI_AUDIO_API_BASE", AI_API_BASE)

AI_STT_MODEL = os.getenv("AI_STT_MODEL", "whisper-1")
AI_TTS_MODEL = os.getenv("AI_TTS_MODEL", "tts-1")
AI_TTS_VOICE = os.getenv("AI_TTS_VOICE", "alloy")
AI_TTS_TIMEOUT = int(os.getenv("AI_TTS_TIMEOUT", "60"))

# --- صوت و متن، نسخه‌ی رایگان/بدونِ AI (bot/local_speech.py) ---
# پیش‌فرض: رونویسی از موتورِ رایگانِ گوگل، متن‌به‌صوت از edge-tts - هیچ‌کدوم
# نیاز به AI_API_KEY ندارن. اگه می‌خوای زبان/صدا رو عوض کنی:
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "fa-IR")
TTS_VOICE = os.getenv("TTS_VOICE", "fa-IR-FaridNeural")

# --- مدیریت گروه پیشرفته: فیلترِ پورن/اسپم (.فیلترپورن / .فیلتراسپم) ---
# فیلترِ پورن از همون سرویسِ هوش‌مصنوعیِ بالا (AI_API_KEY/AI_MODEL) برای
# تحلیلِ تصویر استفاده می‌کنه - پس AI_MODEL باید از ورودیِ تصویر (Vision)
# پشتیبانی کنه (پیش‌فرضِ بالا، gpt-4o-mini، این قابلیت رو داره). اگه
# AI_API_KEY ست نباشه یا مدل تصویر رو پشتیبانی نکنه، فیلترِ پورن fail-open
# می‌کنه (یعنی به‌جای حذفِ اشتباهیِ عکس‌های سالم، کاری نمی‌کنه).
GROUP_PORN_FILTER_MAX_BYTES = int(
    os.getenv("GROUP_PORN_FILTER_MAX_BYTES", str(8 * 1024 * 1024))
)  # عکس‌های بزرگ‌تر از این چک نمی‌شن (برای جلوگیری از دانلودهای سنگین/کند)

# فیلترِ اسپم کاملاً محلیه (بدونِ نیاز به AI): تشخیصِ فلادِ پیام (تعداد زیاد
# توی یه بازه‌ی کوتاه) و تکرارِ عینِ یه متن از طرفِ یک نفر.
GROUP_SPAM_WINDOW_SECONDS = int(os.getenv("GROUP_SPAM_WINDOW_SECONDS", "10"))
GROUP_SPAM_MAX_MESSAGES = int(os.getenv("GROUP_SPAM_MAX_MESSAGES", "6"))
GROUP_SPAM_DUPLICATE_THRESHOLD = int(os.getenv("GROUP_SPAM_DUPLICATE_THRESHOLD", "3"))
GROUP_SPAM_WARN_COOLDOWN_SECONDS = int(os.getenv("GROUP_SPAM_WARN_COOLDOWN_SECONDS", "20"))
