"""۱۴) پنل: نمایش گرافیکی/دکمه‌ای دستورات (.پنل)"""
from telethon import events, Button

from .. import runtime
from ..config import PREFIX
from ..runtime import client
from ..utils import pat

CB_PREFIX = "p:"


def _cb(action: str) -> bytes:
    return f"{CB_PREFIX}{action}".encode()


# هر بخش: کلید (برای callback)، ایموجی، عنوان، و لیست دستورات (دقیقاً هماهنگ با راهنما).
CATEGORIES = [
    {
        "key": "general",
        "emoji": "🧩",
        "title": "عمومی",
        "commands": [
            f"`{PREFIX}پینگ` — تست پینگ",
            f"`{PREFIX}فعال` — وضعیت بات",
            f"`{PREFIX}آیدی` — آیدی چت/کاربر/پیام",
            f"`{PREFIX}اطلاعات` — اطلاعات کاربر (ریپلای اختیاری)",
        ],
    },
    {
        "key": "tools",
        "emoji": "🛠",
        "title": "ابزار",
        "commands": [
            f"`{PREFIX}حساب` `<عبارت>` — ماشین‌حساب (sqrt, sin, log, pi, ...)",
            f"`{PREFIX}کیوآر` `<متن>` — ساخت کیو‌آر کد",
            f"`{PREFIX}کوتاه` `<لینک>` — کوتاه‌کردن لینک",
            f"`{PREFIX}هوا` `<شهر>` — آب‌وهوا",
            f"`{PREFIX}ترجمه` `<زبان> <متن>` — ترجمه",
            f"`{PREFIX}جستجو` `<عبارت>` — جستجوی گوگل",
            f"`{PREFIX}رمزعبور` `<طول اختیاری>` — ساخت رمز عبور تصادفی",
            f"`{PREFIX}هش` `<الگوریتم اختیاری> <متن>` — md5/sha1/sha256/sha512 (یا ریپلای)",
            f"`{PREFIX}بیس64` `انکد/دیکد <متن>` — تبدیل بیس۶۴ (یا ریپلای)",
            f"`{PREFIX}نویسه‌شمار` `<متن>` — شمارش حروف/کلمات/خط (یا ریپلای)",
            f"`{PREFIX}ارز` `<عدد> <از> <به>` — تبدیل نرخ ارز",
            f"`{PREFIX}قیمت` — قیمت لحظه‌ای دلار/یورو/طلا/سکه به ریال (tgju.org)",
            f"`{PREFIX}قیمت` `<طلا/ارز/سکه>` — فقط یه بخش",
            f"`{PREFIX}قیمت` `<اسم کالا>` — جستجوی یه قلم خاص (مثلاً `{PREFIX}قیمت دلار`)",
        ],
    },
    {
        "key": "notes",
        "emoji": "🗒",
        "title": "یادداشت",
        "commands": [
            f"`{PREFIX}یادداشت` `<کلید> <متن>` — ذخیره یادداشت",
            f"`{PREFIX}یادداشت‌ها` — لیست یادداشت‌ها",
            f"`{PREFIX}نمایش‌یادداشت` `<کلید>` — نمایش یادداشت",
            f"`{PREFIX}حذف‌یادداشت` `<کلید>` — حذف یادداشت",
        ],
    },
    {
        "key": "msg",
        "emoji": "🧹",
        "title": "مدیریت پیام",
        "commands": [
            f"`{PREFIX}حذف` — حذف پیام ریپلای‌شده",
            f"`{PREFIX}پاکسازی` `<عدد>` — حذف چند پیام آخر (یا ریپلای)",
            f"`{PREFIX}سنجاق` / `{PREFIX}برداشتن‌سنجاق` — پین/آنپین پیام ریپلای‌شده",
        ],
    },
    {
        "key": "fun",
        "emoji": "🎉",
        "title": "سرگرمی",
        "commands": [
            f"`{PREFIX}تایپ‌زنده` `<متن>` — افکت تایپ زنده",
            f"`{PREFIX}پیش‌تایپ` `<متن>` — شبیه‌سازی تایپ قبل از ارسال",
            f"`{PREFIX}معکوس` `<متن>` — معکوس کردن متن",
            f"`{PREFIX}طنز` `<متن>` — حروف بزرگ‌وکوچکِ متناوب",
            f"`{PREFIX}تاس` `<۱ تا ۶>` — انداختن تاس واقعی",
            f"`{PREFIX}شیرخط` — شیر یا خط",
            f"`{PREFIX}تصادفی` `<min> <max>` — عدد تصادفی",
            f"`{PREFIX}انتخاب` `<گزینه۱, گزینه۲, ...>` — انتخاب تصادفی",
            f"`{PREFIX}سنگ‌کاغذقیچی` `<سنگ/کاغذ/قیچی>` — بازی با بات",
            f"`{PREFIX}حدس شروع` `<سقف اختیاری>` — شروع بازیِ حدسِ عدد",
            f"`{PREFIX}حدس` `<عدد>` — حدس‌زدن توی بازیِ فعال",
            f"`{PREFIX}حدس لغو` — لغو بازیِ فعال",
            f"`{PREFIX}اسلات` — ماشین اسلات",
            f"`{PREFIX}جادوگر` `<سوال>` — پاسخ تصادفیِ توپ جادویی",
            f"`{PREFIX}عشق‌سنج` `<اسم۱> و <اسم۲>` — عشق‌سنجِ شوخی",
            f"`{PREFIX}این‌یا‌اون` — یه سوالِ «این یا اون» تصادفی",
            f"`{PREFIX}کوییز` — سوالِ عمومیِ چهارگزینه‌ای (Open Trivia DB)",
            f"`{PREFIX}کوییز` `<۱ تا ۴>` — جواب‌دادن به سوالِ فعال",
            f"`{PREFIX}فال` — فالِ حافظِ تصادفی با تفسیر",
        ],
    },
    {
        "key": "font",
        "emoji": "🔤",
        "title": "فونت پیام",
        "commands": [
            f"`{PREFIX}قلم فهرست` — لیست فونت‌های موجود",
            f"`{PREFIX}قلم` `<نام> <متن>` — تبدیل یه‌بارِ متن",
            f"`{PREFIX}قلم تنظیم` `<نام>` — فونت پیش‌فرض خودکار",
            f"`{PREFIX}قلم روشن/خاموش` — اعمال خودکار فونت روی پیام‌ها",
            f"`{PREFIX}قلم وضعیت` — وضعیت فونت خودکار",
        ],
    },
    {
        "key": "profile",
        "emoji": "👤",
        "title": "پروفایل",
        "commands": [
            f"`{PREFIX}بیو` `<متن>` — تغییر بیو",
            f"`{PREFIX}نام` `<متن>` — تغییر نام پایه",
            f"`{PREFIX}عکس` — تغییر عکس پروفایل (ریپلای روی عکس)",
            f"`{PREFIX}ساعت روشن/خاموش` — ساعت زنده در نام",
            f"`{PREFIX}مدل‌ساعت` — لیست مدل‌های ساعت",
            f"`{PREFIX}مدل‌ساعت` `<نام>/بعدی` — تغییر مدل ساعت",
        ],
    },
    {
        "key": "assistant",
        "emoji": "🤖",
        "title": "منشی چت",
        "commands": [
            f"`{PREFIX}منشی روشن/خاموش` — روشن/خاموش دستی",
            f"`{PREFIX}منشی خودکار` — تشخیص خودکار آنلاین/آفلاین",
            f"`{PREFIX}منشی وضعیت` — نمایش وضعیت منشی",
            f"`{PREFIX}منشی متن` `<متن>` — تنظیم پیام پاسخ",
            f"`{PREFIX}منشی تأخیر` `<ثانیه>` — تنظیم تأخیر",
            f"`{PREFIX}منشی حالت` `<خودکار/منشن/پیوی/گروه‌ها>`",
            f"`{PREFIX}منشی مستثنی` / `{PREFIX}منشی شامل` — چت فعلی",
            f"`{PREFIX}منشی پاک` — حذف لیست چت‌ها",
        ],
    },
    {
        "key": "assistant_schedule",
        "emoji": "🗓",
        "title": "زمان‌بندیِ منشی",
        "commands": [
            f"`{PREFIX}منشی زمان‌بندی` — نمایش لیستِ بازه‌ها",
            f"`{PREFIX}منشی زمان‌بندی افزودن` `<شروع> <پایان> [برچسب]` — مثلاً `23:00 08:00 خواب`",
            f"`{PREFIX}منشی زمان‌بندی حذف` `<شماره>` — حذفِ یه بازه",
            f"`{PREFIX}منشی زمان‌بندی پاک` — حذفِ همه‌ی بازه‌ها",
            f"`{PREFIX}منشی زمان‌بندی روشن/خاموش` — کلِ لایه (بدونِ پاک‌کردنِ بازه‌ها)",
        ],
    },
    {
        "key": "admin",
        "emoji": "👮",
        "title": "مدیریت گروه",
        "commands": [
            f"`{PREFIX}اخراج` / `{PREFIX}مسدود` / `{PREFIX}رفع‌مسدود` — ریپلای روی کاربر",
            f"`{PREFIX}ارتقا` / `{PREFIX}تنزل` — ریپلای روی کاربر",
            f"`{PREFIX}بی‌صدا` `<دقیقه اختیاری>` / `{PREFIX}رفع‌سکوت`",
            f"`{PREFIX}ادمین‌ها` — لیست ادمین‌های گروه",
            f"`{PREFIX}لینک‌گروه` — لینک دعوت گروه",
            f"`{PREFIX}قفل‌گروه` / `{PREFIX}بازکردن‌گروه`",
            f"`{PREFIX}فیلترلینک روشن/خاموش/وضعیت` — حذف خودکار پیام‌های لینک‌دار از غیرادمین‌ها",
            f"`{PREFIX}خوش‌آمد روشن/خاموش/متن` `<متن>` — خوش‌آمدگویی خودکار برای عضو جدید",
            f"`{PREFIX}فیلترپورن روشن/خاموش/وضعیت` — حذفِ خودکارِ عکسِ نامناسب با AI (نیازمندِ `AI_API_KEY` با مدلِ Vision)",
            f"`{PREFIX}فیلترپورن تست` — ریپلای روی عکس؛ پاسخِ خامِ AI یا خطای دقیق برای عیب‌یابیِ سریع",
            f"`{PREFIX}فیلتراسپم روشن/خاموش/وضعیت` — حذفِ خودکارِ فلاد/تکرارِ پیام از غیرادمین‌ها (بدونِ نیاز به AI)",
            f"`{PREFIX}برچسب‌همه` `<متن اختیاری>` — تگ‌کردنِ همه‌ی اعضا (با احتیاط، ریسکِ اسپم)",
            "⚠️ فقط جایی که خودتون ادمین هستید",
        ],
    },
    {
        "key": "backup",
        "emoji": "💾",
        "title": "بکاپ‌گیری",
        "commands": [
            f"`{PREFIX}پشتیبان` `<عدد>` — بکاپ متنی به Saved Messages",
            f"`{PREFIX}پشتیبان json` `<عدد>` — همون، خروجی JSON",
            f"`{PREFIX}پشتیبان رسانه` `<عدد>` — دانلود/فوروارد رسانه",
            f"`{PREFIX}پشتیبان چت‌ها` — بکاپ لیست همه‌ی چت‌ها",
            f"`{PREFIX}پشتیبان تنظیمات` — بکاپ کامل تنظیمات بات",
            f"`{PREFIX}بازیابی` — ریپلای روی فایل بکاپِ تنظیمات",
        ],
    },
    {
        "key": "settings_center",
        "emoji": "⚙️",
        "title": "تنظیماتِ یکپارچه",
        "commands": [
            f"`{PREFIX}تنظیمات` — وضعیتِ زنده‌ی منشی/AI/زمان‌بند/ارسالِ‌خودکار/فونت/آمار/اعلان",
            f"`{PREFIX}تنظیمات تنظیم` `<key> <true|false>` — روشن/خاموش‌کردنِ مستقیمِ همون بخش",
            "🛡 محافظِ گروه اینجا نیست؛ سراسری نیست، هر گروه جدا تنظیم می‌شه",
        ],
    },
    {
        "key": "automation",
        "emoji": "⚡",
        "title": "موتورِ اتوماسیون",
        "commands": [
            f"`{PREFIX}اتوماسیون` — لیستِ قوانین",
            f"`{PREFIX}اتوماسیون جدید` `<نام> <رویداد> <عملیات> <مقدار>` — فعلاً فقط رویدادِ message وصله",
            f"`{PREFIX}اتوماسیون فعال/غیرفعال/حذف/اطلاعات` `<id>`",
        ],
    },
    {
        "key": "notifications",
        "emoji": "🔔",
        "title": "مرکزِ اعلان‌ها",
        "commands": [
            f"`{PREFIX}اعلان` — لیستِ قوانینِ اعلان",
            f"`{PREFIX}اعلان جدید` `<نام> <نوع> <مقدار> <عملیات>` — نوعِ time فعلاً پشتیبانی نمی‌شه",
            f"`{PREFIX}اعلان فعال/غیرفعال/حذف/اطلاعات` `<id>`",
        ],
    },
    {
        "key": "inbox",
        "emoji": "📥",
        "title": "اینباکسِ داخلی",
        "commands": [
            f"`{PREFIX}ذخیره` — با ریپلای روی یه پیام، ذخیره‌ش می‌کنه (اختیاری: مهم/فوری)",
            f"`{PREFIX}اینباکس` — نمایش (یا `مهم`/`خوانده`/`نخوانده`/`پاک <id>`)",
        ],
    },
    {
        "key": "ai_memory",
        "emoji": "🧠",
        "title": "حافظه‌ی AI",
        "commands": [
            f"`{PREFIX}حافظه` — آمارِ حافظه",
            f"`{PREFIX}حافظه افزودن/جستجو/حذف/لیست/پاک` — مدیریتِ آیتم‌های حافظه",
        ],
    },
    {
        "key": "user_profile",
        "emoji": "👤",
        "title": "پروفایلِ کاربر",
        "commands": [
            f"`{PREFIX}کاربر` — با ریپلای یا `<شناسه>`، نمایشِ پروفایلِ داخلی",
            f"`{PREFIX}برچسب` `<شناسه> <برچسب>` — افزودنِ تگ",
            f"`{PREFIX}یادداشت‌کاربر` `<شناسه> <متن>` — یادداشتِ خصوصی روی یه کاربر",
        ],
    },
    {
        "key": "global_search",
        "emoji": "🔍",
        "title": "جستجوی جهانی",
        "commands": [
            f"`{PREFIX}جستجو` `<عبارت>` — یادداشت‌ها، حافظه‌ی AI، پروفایل‌ها، اینباکس، زمان‌بندی + پیام‌های تلگرام + کانال/گروه/کاربرِ کلِ تلگرام",
        ],
    },
    {
        "key": "smart_reply",
        "emoji": "💬",
        "title": "پاسخِ هوشمند",
        "commands": [
            f"`{PREFIX}جواب` `<رسمی|دوستانه|طنز|کوتاه>` — با ریپلای، پیش‌نویسِ پاسخ با AI",
            "⚠️ نیازمندِ `AI_API_KEY`",
        ],
    },
    {
        "key": "health",
        "emoji": "🩺",
        "title": "سلامتِ سیستم",
        "commands": [
            f"`{PREFIX}سلامت` — وضعیتِ دیتابیس و ورکرهای پس‌زمینه + uptime",
        ],
    },
    {
        "key": "plugins_cmd",
        "emoji": "🧩",
        "title": "پلاگین‌ها",
        "commands": [
            f"`{PREFIX}پلاگین` — لیستِ پلاگین‌های فعال (داخلی + نصب‌شده)",
            f"`{PREFIX}پلاگین نصب` `<لینکِ فایلِ .py در گیت‌هاب>` — نصب و بارگذاریِ آنی، بدونِ ری‌استارت",
            f"`{PREFIX}پلاگین حذف` `<نام>` — حذفِ پلاگینِ نصب‌شده",
            f"`{PREFIX}پلاگین reload` `<نام>` — Unload/Load دوباره، بدونِ ری‌استارتِ کلِ بات",
            "⚠️ پلاگین با سطحِ دسترسیِ خودِ اکانت اجرا می‌شه؛ فقط کدِ مطمئن نصب کن",
        ],
    },
    {
        "key": "autopost",
        "emoji": "📤",
        "title": "ارسال خودکار",
        "commands": [
            f"`{PREFIX}ارسال‌خودکار` — نمایش وضعیت کامل",
            f"`{PREFIX}ارسال‌خودکار روشن/خاموش`",
            f"`{PREFIX}ارسال‌خودکار فاصله` `<دقیقه>`",
            f"`{PREFIX}ارسال‌خودکار متن` `<متن>` (یا ریپلای)",
            f"`{PREFIX}ارسال‌خودکار افزودن/حذف` — گروه فعلی",
            f"`{PREFIX}ارسال‌خودکار پاک` — پاک‌کردن مقصدها",
            f"`{PREFIX}ارسال‌خودکار فوری` — تست فوری",
        ],
    },
    {
        "key": "scheduler",
        "emoji": "⏰",
        "title": "زمان‌بندی و یادآوری",
        "commands": [
            f"`{PREFIX}زمان‌بند` `<زمان> <متن>` — ارسال متن سرِ وقت توی همین چت (یا ریپلای)",
            f"`{PREFIX}زمان‌بند لیست` — پیام‌های زمان‌بندی‌شده‌ی این چت",
            f"`{PREFIX}زمان‌بند لغو` `<شناسه>` — لغوِ یک زمان‌بندی",
            f"`{PREFIX}یادآوری` `<زمان> <متن>` — یادآوری سرِ وقت به Saved Messages (یا ریپلای)",
            f"`{PREFIX}یادآوری لیست` — یادآوری‌های ثبت‌شده",
            f"`{PREFIX}یادآوری لغو` `<شناسه>` — لغوِ یک یادآوری",
            "فرمتِ زمان: نسبی (`10m`/`2h`/`1d`/`10دقیقه`/`2ساعت`)، ساعتِ امروز/فردا (`14:30`)، یا کامل (`2026-08-25 14:30`)",
        ],
    },
    {
        "key": "daily_digest",
        "emoji": "🌙",
        "title": "خلاصه‌ی روزانه",
        "commands": [
            f"`{PREFIX}خلاصه‌روز` — نمایشِ وضعیت",
            f"`{PREFIX}خلاصه‌روز روشن/خاموش` — فعال/غیرفعال‌کردنِ ارسالِ خودکارِ شبانه",
            f"`{PREFIX}خلاصه‌روز حالت کلی/سفارشی` — خلاصه‌ی همه‌ی چت‌ها یا فقط چت‌های انتخابی",
            f"`{PREFIX}خلاصه‌روز زمان` `<HH:MM>` — ساعتِ ارسال (وقتِ محلی)",
            f"`{PREFIX}خلاصه‌روز افزودن/حذف` `<آیدیِ چت اختیاری>` — مدیریتِ لیستِ سفارشی",
            f"`{PREFIX}خلاصه‌روز لیست` / `{PREFIX}خلاصه‌روز پاک` — نمایش/پاک‌کردنِ لیستِ سفارشی",
            f"`{PREFIX}خلاصه‌روز الان` — اجرای فوری برای تست",
        ],
    },
    {
        "key": "media",
        "emoji": "🖼",
        "title": "رسانه و فایل",
        "commands": [
            f"`{PREFIX}واترمارک` `<متن>` — واترمارکِ متنی روی عکسِ ریپلای‌شده",
            f"`{PREFIX}فشرده‌سازی` — کوچیک‌کردنِ عکس/ویدیوِ ریپلای‌شده",
            f"`{PREFIX}تبدیل` `<فرمت>` — تبدیل فرمتِ فایلِ ریپلای‌شده (webp→png، ogg→mp3، ...)",
            f"`{PREFIX}استیکر` `<نامِ‌پک> <ایموجی اختیاری>` — ساختِ استیکر از عکسِ ریپلای‌شده",
            f"`{PREFIX}استخراج‌متن` — استخراج متن از عکسِ ریپلای‌شده (پیش‌فرض: محلی/رایگان، فارسی+انگلیسی)",
            f"`{PREFIX}استخراج‌متن` `<en/fa>` — فقط یه زبانِ خاص (محلی)",
            f"`{PREFIX}استخراج‌متن ai` — با هوشِ مصنوعیِ Vision (بهتر برای دست‌نویس/کیفیتِ پایین، نیازمندِ AI_API_KEY)",
        ],
    },
    {
        "key": "ai",
        "emoji": "🤖",
        "title": "هوش مصنوعی",
        "commands": [
            f"`{PREFIX}پرسش` `<سوال>` — سوال از مدل زبانی (یا با ریپلای روی متن/صوت: خلاصه/تحلیلِ همون پیام)",
            f"`{PREFIX}خلاصه` `<عدد>` — خلاصه‌ی N پیامِ آخرِ همین چت (پیش‌فرض ۵۰)",
            f"`{PREFIX}ترجمه‌هوشمند` `<زبان> <متن>` — ترجمه با مدلِ زبانی (کیفیتِ بهتر، جدا از `{PREFIX}ترجمه`ی معمولی)",
            f"`{PREFIX}منشی هوش‌مصنوعی روشن/خاموش` — اتصالِ پاسخِ خودکارِ منشی به هوش مصنوعی",
            "⚠️ نیازمندِ متغیر محیطیِ `AI_API_KEY`؛ بدون اون فقط پیامِ راهنما می‌دن",
        ],
    },
    {
        "key": "command_router",
        "emoji": "🧠",
        "title": "روترِ دستوریِ هوشمند",
        "commands": [
            f"`{PREFIX}هوش` `<جمله‌ی آزاد>` — تشخیصِ خودکارِ دستور (یادآوری، یادداشت، ابزار، پروفایل، فونت، سرگرمی، ...)",
            f"`{PREFIX}هوش تایید` / `{PREFIX}هوش لغو` — تاییدِ صریح قبل از هر اجرایی",
            "⚠️ نیازمندِ همون `AI_API_KEY`",
        ],
    },
    {
        "key": "audio",
        "emoji": "🔊",
        "title": "صوت و متن",
        "commands": [
            f"`{PREFIX}رونویسی` — پیامِ صوتیِ ریپلای‌شده رو به متن تبدیل می‌کنه",
            f"`{PREFIX}رونویسی` `<سوال>` — رونویسی + پرسیدن از AI درباره‌ی همون متن",
            f"`{PREFIX}متن‌به‌صوت` `<متن>` — متن رو به پیامِ صوتی تبدیل می‌کنه",
            "⚠️ از همون `AI_API_KEY` یِ بخشِ هوش مصنوعی استفاده می‌کنه",
        ],
    },
    {
        "key": "stats",
        "emoji": "📊",
        "title": "آمار",
        "commands": [
            f"`{PREFIX}آمار` — آمار کلی (دستورات، پیام‌ها، uptime، ...)",
            f"`{PREFIX}آمار چت‌ها` — آمار به‌تفکیک هر چت",
            f"`{PREFIX}آمار بازنشانی` — پاک‌کردن همه‌ی آمار",
        ],
    },
]

_CATEGORY_BY_KEY = {c["key"]: c for c in CATEGORIES}


def _divider():
    return "◈─────────────────◈"


def build_home_text():
    total_commands = sum(len(c["commands"]) for c in CATEGORIES)
    return (
        "👑 **پـنـل مـدیـریـت سـلـف‌بـات** 👑\n"
        f"{_divider()}\n"
        f"📂 **{len(CATEGORIES)}** بخش   •   ⚙️ **{total_commands}** دستور   •   🔡 پیشوند `{PREFIX}`\n\n"
        "یک بخش رو از دکمه‌های زیر انتخاب کن تا قابلیت‌ها و دستوراتش نمایش داده بشه. ✨\n"
        "⚠️ دستورها رو با اکانت خودت (نه این ربات) توی چت مقصد بفرست."
    )


def build_home_buttons():
    rows = []
    row = []
    for cat in CATEGORIES:
        row.append(Button.inline(f"{cat['emoji']} {cat['title']}", _cb(f"cat:{cat['key']}")))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([Button.inline("✖️ بستن پنل", _cb("close"))])
    return rows


def build_category_text(cat):
    body = "\n".join(f"› {line}" for line in cat["commands"])
    return (
        f"{cat['emoji']} **{cat['title']}**\n"
        f"{_divider()}\n\n"
        f"{body}\n\n"
        f"{_divider()}\n"
        "➜ برای اجرا، دستور رو با اکانت خودت (نه این ربات) توی چت مقصد بفرست."
    )


def build_category_buttons():
    return [[
        Button.inline("🔙 بازگشت", _cb("home")),
        Button.inline("✖️ بستن", _cb("close")),
    ]]


# ---------------------------------------------------------------------------
# نکته‌ی مهم: تلگرام دکمه‌های شیشه‌ای (inline keyboard) رو فقط برای پیام‌های
# ارسالی از طرف یه بات واقعی (BotFather) نمایش می‌ده، نه پیام‌های اکانت
# شخصی/سلف‌بات. برای همین یه بات کمکی (runtime.bot_client، با BOT_TOKEN) لازمه.
#
# برای اینکه پنل توی همون چتی که «.پنل» زده می‌شه نمایش داده بشه (نه فقط توی
# چت خصوصیِ خود بات کمکی)، از حالت inline بات کمکی استفاده می‌کنیم:
#   ۱) اکانتِ خودِ سلف‌بات (client) با client.inline_query(...) یه نتیجه‌ی
#      inline از بات کمکی می‌گیره و با result.click(event.chat_id) همون
#      نتیجه (که دکمه‌های واقعی داره، چون منشأش باته) رو توی همین چت می‌فرسته؛
#      پیام با برچسبِ «via @نام‌بات» ولی با دکمه‌های کاملاً کاربردی نمایش داده
#      می‌شه، و بعد پیامِ دستورِ «.پنل» پاک می‌شه.
#   ۲) این کار فقط وقتی جواب می‌ده که حالت inline روی بات کمکی فعال باشه
#      (توی @BotFather → بات موردنظر → Bot Settings → Inline Mode → روشن).
#      اگه فعال نباشه (یا هر خطای دیگه‌ای پیش بیاد)، به‌جاش یه لینکِ باز کردنِ
#      چتِ خصوصیِ بات کمکی فرستاده می‌شه (روش قدیمی، به‌عنوان fallback).
#   ۳) کلیک‌های داخلِ پنل (دکمه‌ها) چه توی چتِ خصوصیِ بات باشن چه inline توی
#      یه چتِ دیگه، همگی از طریق همون CallbackQuery پایین مدیریت می‌شن -
#      تلتون خودش تشخیص می‌ده پیام عادیه یا inline و edit رو درست انجام می‌ده.
# ---------------------------------------------------------------------------


@client.on(events.NewMessage(outgoing=True, pattern=pat(["پنل", "panel"], arg=False)))
async def panel_open_handler(event):
    if runtime.bot_client is None or not runtime.BOT_USERNAME:
        await event.edit(
            "⚠️ **پنل دکمه‌ای غیرفعاله**\n"
            f"{_divider()}\n"
            "برای فعال‌سازی:\n"
            "۱. توی @BotFather یه بات جدید بساز.\n"
            "۲. توکنش رو توی متغیر محیطی `BOT_TOKEN` بذار.\n"
            "۳. سلف‌بات رو ری‌استارت کن."
        )
        return

    try:
        results = await client.inline_query(runtime.BOT_USERNAME, "panel")
        if not results:
            raise RuntimeError("no inline results")
        await results[0].click(
            event.chat_id,
            reply_to=event.reply_to_msg_id,
            silent=False,
        )
        await event.delete()
    except Exception:
        # حالت inline روی بات کمکی فعال نیست (یا خطای دیگه‌ای پیش اومده) -
        # fallback به لینکِ باز کردنِ چتِ خصوصیِ بات کمکی.
        link = f"https://t.me/{runtime.BOT_USERNAME}?start=panel"
        text = (
            "👑 **پنل مدیریت سلف‌بات** 👑\n"
            f"{_divider()}\n\n"
            "برای نمایش پنل همین‌جا، اول باید حالت Inline Mode بات کمکی رو توی\n"
            "@BotFather → botموردنظر → Bot Settings → Inline Mode روشن کنی.\n\n"
            f"فعلاً می‌تونی از طریق چتِ خصوصیِ بات باز کنیش: {link}"
        )
        await event.edit(text, link_preview=False)


if runtime.bot_client is not None:

    @runtime.bot_client.on(events.NewMessage(incoming=True, pattern=r"^/(start|panel)\b"))
    async def panel_bot_start_handler(event):
        if runtime.SELF_ID is not None and event.sender_id != runtime.SELF_ID:
            await event.respond("⛔️ این ربات فقط برای صاحب اکانت است.")
            return
        await event.respond(build_home_text(), buttons=build_home_buttons())

    @runtime.bot_client.on(events.InlineQuery)
    async def panel_bot_inline_handler(event):
        # فقط صاحب اکانت (خود سلف‌بات) اجازه‌ی گرفتنِ نتیجه‌ی inline رو داره.
        if runtime.SELF_ID is not None and event.sender_id != runtime.SELF_ID:
            await event.answer([])
            return

        builder = event.builder
        result = builder.article(
            title="👑 باز کردن پنل مدیریت",
            description=f"{len(CATEGORIES)} بخش را همین‌جا نمایش بده",
            text=build_home_text(),
            buttons=build_home_buttons(),
        )
        await event.answer([result])

    @runtime.bot_client.on(events.CallbackQuery(pattern=rb"^p:"))
    async def panel_bot_callback_handler(event):
        # فقط صاحب اکانت (خود سلف‌بات) اجازه‌ی تعامل با پنل رو داره
        if runtime.SELF_ID is not None and event.sender_id != runtime.SELF_ID:
            await event.answer("⛔️ این پنل فقط برای مالک اکانت است.", alert=True)
            return

        data = event.data.decode()
        action = data[len(CB_PREFIX):]

        if action == "home":
            await event.edit(build_home_text(), buttons=build_home_buttons())
            await event.answer()
            return

        if action == "close":
            # نکته‌ی مهم: `event.delete()` فقط وقتی کار می‌کنه که پیامِ پنل یه
            # پیامِ عادیِ خودِ بات کمکی باشه (یعنی توی چتِ خصوصیِ خودِ بات).
            # وقتی پنل با ترفندِ inline (client.inline_query(...).click(...))
            # توی یه چت/گروهِ دیگه فرستاده می‌شه، تلگرام فقط یه inline_message_id
            # به بات می‌ده - و API ای برای حذفِ پیام از طریقِ همون شناسه وجود
            # نداره (فقط edit ازش پشتیبانی می‌شه)، برای همین `event.delete()`
            # اونجا سرِ همچین پیام‌هایی fail می‌شه و دکمه‌ی «بستن» بی‌اثر
            # به‌نظر می‌رسید. راه‌حل: اول با edit (که هم توی چتِ خصوصی هم
            # inline کار می‌کنه) دکمه‌ها رو برمی‌داریم و متن رو «بسته‌شد» می‌کنیم،
            # و فقط اگه واقعاً یه پیامِ عادی (نه inline) بود، تلاش می‌کنیم
            # کاملاً حذفش هم بکنیم (برای تمیزیِ بیشتر توی چتِ خودِ بات).
            try:
                await event.edit("✖️ پنل بسته شد.", buttons=None)
            except Exception:
                pass
            try:
                if getattr(event.query, "msg_id", None):
                    await event.delete()
            except Exception:
                pass
            await event.answer()
            return

        if action.startswith("cat:"):
            key = action[len("cat:"):]
            cat = _CATEGORY_BY_KEY.get(key)
            if cat is None:
                await event.answer("یافت نشد.", alert=True)
                return
            await event.edit(build_category_text(cat), buttons=build_category_buttons())
            await event.answer()
            return

        await event.answer()
