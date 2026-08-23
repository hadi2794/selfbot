"""۵) سرگرمی: write / type / reverse / mock / dice / coin / random / choose / rps
/ guess / slot / 8ball / love / wyr / quiz / fal"""
import asyncio
import hashlib
import logging
import random
import re
import urllib.parse

import aiohttp
from telethon import errors, events
from telethon.tl.types import InputMediaDice

from ..config import PREFIX
from ..runtime import client, get_http_session
from ..repositories import hafez_repo
from ..storage.stats_store import record_error as _record_error
from ..utils import pat
from .. import ai

logger = logging.getLogger(__name__)

@client.on(events.NewMessage(outgoing=True, pattern=pat(["تایپ‌زنده", "write"])))
async def write_handler(event):
    text = event.pattern_match.group(1)
    if not text:
        return await event.edit(f"مثال: `{PREFIX}تایپ‌زنده سلام دنیا`")
    current = ""
    msg = await event.edit("▌")
    for ch in text:
        current += ch
        try:
            await msg.edit(current + "▌")
            await asyncio.sleep(0.05)
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
    await msg.edit(current)


@client.on(events.NewMessage(outgoing=True, pattern=pat(["پیش‌تایپ", "type"])))
async def type_handler(event):
    text = event.pattern_match.group(1)
    if not text:
        return await event.edit(f"مثال: `{PREFIX}پیش‌تایپ سلام`")
    await event.delete()
    async with client.action(event.chat_id, "typing"):
        await asyncio.sleep(min(len(text) * 0.05, 5))
    await client.send_message(event.chat_id, text)


@client.on(events.NewMessage(outgoing=True, pattern=pat(["معکوس", "reverse"])))
async def reverse_handler(event):
    text = event.pattern_match.group(1)
    if not text and event.is_reply:
        reply = await event.get_reply_message()
        text = reply.raw_text
    if not text:
        return await event.edit(f"مثال: `{PREFIX}معکوس سلام`")
    await event.edit(text[::-1])


@client.on(events.NewMessage(outgoing=True, pattern=pat(["طنز", "mock"])))
async def mock_handler(event):
    text = event.pattern_match.group(1)
    if not text and event.is_reply:
        reply = await event.get_reply_message()
        text = reply.raw_text
    if not text:
        return await event.edit(f"مثال: `{PREFIX}طنز متن شما`")
    mocked = "".join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(text))
    await event.edit(mocked)


DICE_MAX_ATTEMPTS = 60  # سقف تلاش - میانگین لازم ۶ باره، این حاشیه‌ی امن کافیه


async def _roll_real_dice(chat_id):
    """
    یه تاس واقعی می‌فرسته. برای اطمینان از خوندن درستِ عدد نتیجه، به‌جای اتکا
    به آبجکتی که مستقیم از send_file برمی‌گرده (که بعضی‌وقت‌ها media توش کامل
    پر نشده)، پیام رو یک‌بار دیگه از خودِ سرور تلگرام می‌خونیم.
    """
    sent = await client.send_file(chat_id, InputMediaDice("🎲"))
    fresh = await client.get_messages(chat_id, ids=sent.id)
    value = getattr(getattr(fresh, "media", None), "value", None)
    return fresh, value


@client.on(events.NewMessage(outgoing=True, pattern=pat(["تاس", "dice"])))
async def dice_handler(event):
    arg = (event.pattern_match.group(1) or "").strip()
    if not arg.isdigit() or not (1 <= int(arg) <= 6):
        return await event.edit(f"مثال: `{PREFIX}تاس 4` (عدد باید بین ۱ تا ۶ باشه)")
    target = int(arg)
    chat_id = event.chat_id
    await event.delete()

    last_value = None
    for _ in range(DICE_MAX_ATTEMPTS):
        try:
            msg, value = await _roll_real_dice(chat_id)
        except errors.FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            continue
        except Exception as e:
            _record_error()
            return await client.send_message(chat_id, f"❌ خطا در ارسال تاس: {e}")

        last_value = value
        if value == target:
            return  # تاس با عدد درست موند، تمام

        try:
            await msg.delete()
        except Exception:
            pass
        await asyncio.sleep(0.5)

    await client.send_message(
        chat_id,
        f"❌ بعد از {DICE_MAX_ATTEMPTS} تلاش نتونستم عدد {target} رو بیارم "
        f"(آخرین عددی که اومد: {last_value})",
    )


@client.on(events.NewMessage(outgoing=True, pattern=pat(["شیرخط", "coin"], arg=False)))
async def coin_handler(event):
    result = random.choice(["🦁 شیر", "✍️ خط"])
    await event.edit(f"🪙 {result}")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["تصادفی", "random"])))
async def random_handler(event):
    arg = (event.pattern_match.group(1) or "").strip()
    nums = arg.split()
    if len(nums) != 2 or not all(n.lstrip("-").isdigit() for n in nums):
        return await event.edit(f"مثال: `{PREFIX}تصادفی 1 100`")
    lo, hi = int(nums[0]), int(nums[1])
    if lo > hi:
        lo, hi = hi, lo
    await event.edit(f"🎯 عدد تصادفی: **{random.randint(lo, hi)}**")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["انتخاب", "choose"])))
async def choose_handler(event):
    arg = event.pattern_match.group(1)
    if not arg:
        return await event.edit(f"مثال: `{PREFIX}انتخاب پیتزا, برگر, سوشی`")
    options = [o.strip() for o in re.split(r",|\|", arg) if o.strip()]
    if len(options) < 2:
        options = [o.strip() for o in arg.split() if o.strip()]
    if len(options) < 2:
        return await event.edit("حداقل ۲ گزینه لازمه (با کاما یا فاصله جداشون کن)")
    await event.edit(f"🎲 انتخاب شد: **{random.choice(options)}**")


_RPS_CHOICES = {
    "سنگ": "🪨", "rock": "🪨",
    "کاغذ": "📄", "paper": "📄",
    "قیچی": "✂️", "scissors": "✂️",
}
_RPS_CANONICAL = {"سنگ": "سنگ", "rock": "سنگ", "کاغذ": "کاغذ", "paper": "کاغذ", "قیچی": "قیچی", "scissors": "قیچی"}
_RPS_BEATS = {"سنگ": "قیچی", "قیچی": "کاغذ", "کاغذ": "سنگ"}


@client.on(events.NewMessage(outgoing=True, pattern=pat(["سنگ‌کاغذقیچی", "rps"])))
async def rps_handler(event):
    arg = (event.pattern_match.group(1) or "").strip().lower()
    if arg not in _RPS_CANONICAL:
        return await event.edit(f"مثال: `{PREFIX}سنگ‌کاغذقیچی سنگ` (یا کاغذ/قیچی)")
    user_choice = _RPS_CANONICAL[arg]
    bot_choice = random.choice(["سنگ", "کاغذ", "قیچی"])
    if user_choice == bot_choice:
        result = "🤝 مساوی شد!"
    elif _RPS_BEATS[user_choice] == bot_choice:
        result = "🎉 بردی!"
    else:
        result = "😅 باختی!"
    await event.edit(
        f"شما: {_RPS_CHOICES[user_choice]} {user_choice}\n"
        f"من: {_RPS_CHOICES[bot_choice]} {bot_choice}\n\n"
        f"{result}"
    )


GUESS_GAMES = {}  # chat_id -> {"target": int, "max": int, "attempts": int} - بازیِ فعالِ هر چت


@client.on(events.NewMessage(outgoing=True, pattern=pat(["حدس", "guess"])))
async def guess_handler(event):
    arg = (event.pattern_match.group(1) or "").strip()
    chat_id = event.chat_id
    parts = arg.split()
    sub = parts[0].lower() if parts else ""

    if not arg or sub in ("شروع", "start"):
        max_n = 100
        if len(parts) > 1 and parts[1].isdigit():
            max_n = max(10, min(int(parts[1]), 1_000_000))
        GUESS_GAMES[chat_id] = {"target": random.randint(1, max_n), "max": max_n, "attempts": 0}
        return await event.edit(
            f"🎯 یه عدد بین ۱ تا {max_n} توی ذهنم انتخاب کردم.\n"
            f"حدس بزن: `{PREFIX}حدس <عدد>` — برای لغو: `{PREFIX}حدس لغو`"
        )

    if sub in ("لغو", "cancel", "stop"):
        if GUESS_GAMES.pop(chat_id, None) is not None:
            return await event.edit("🚫 بازی لغو شد")
        return await event.edit("بازی‌ای در حال اجرا نیست")

    if not arg.lstrip("-").isdigit():
        return await event.edit(f"مثال: اول `{PREFIX}حدس شروع` بعد `{PREFIX}حدس 50`")

    game = GUESS_GAMES.get(chat_id)
    if not game:
        return await event.edit(f"بازی‌ای شروع نشده. اول بزن: `{PREFIX}حدس شروع`")

    guess = int(arg)
    game["attempts"] += 1
    if guess == game["target"]:
        attempts = game["attempts"]
        del GUESS_GAMES[chat_id]
        return await event.edit(f"🎉 درست حدس زدی! عدد **{guess}** بود (با {attempts} تلاش)")
    if not (1 <= guess <= game["max"]):
        game["attempts"] -= 1  # حدسِ خارج از بازه، به‌عنوان تلاش واقعی حساب نشه
        return await event.edit(f"عدد باید بین ۱ تا {game['max']} باشه")
    hint = "بالاتر برو 🔼" if guess < game["target"] else "پایین‌تر بیا 🔽"
    await event.edit(f"❌ نه. {hint} (تلاش شماره {game['attempts']})")


_SLOT_EMOJIS = ["🍒", "🍋", "🍇", "🍉", "⭐", "7️⃣", "🔔"]


@client.on(events.NewMessage(outgoing=True, pattern=pat(["اسلات", "slot"], arg=False)))
async def slot_handler(event):
    reels = [random.choice(_SLOT_EMOJIS) for _ in range(3)]
    result = " | ".join(reels)
    if reels[0] == reels[1] == reels[2]:
        msg = "🎉 جکپات! هر سه یکی شدن!"
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        msg = "✨ دوتاش یکی شدن، یه‌کم شانس آوردی!"
    else:
        msg = "😅 این دفعه نه، شانس بعدی!"
    await event.edit(f"🎰 [ {result} ]\n{msg}")


_MAGIC8BALL_ANSWERS = [
    "بله، مطمئنم ✅", "به احتمال زیاد آره", "علائم می‌گن بله",
    "آره، ولی شک نکن که باید تلاش هم بکنی", "قطعاً همینطوره",
    "بعیده", "من که بهش شک دارم", "نه، فکر نکنم", "قطعاً نه ❌",
    "الان نمی‌تونم بگم، دوباره بپرس 🌀", "روی این حساب نکن",
    "آینده مبهمه، بعداً بپرس", "تمرکز کن و دوباره بپرس",
]


@client.on(events.NewMessage(outgoing=True, pattern=pat(["جادوگر", "8ball"])))
async def magic8ball_handler(event):
    q = event.pattern_match.group(1)
    if not q and event.is_reply:
        reply = await event.get_reply_message()
        q = reply.raw_text
    if not q:
        return await event.edit(f"مثال: `{PREFIX}جادوگر فردا هوا خوبه؟`")
    answer = random.choice(_MAGIC8BALL_ANSWERS)
    await event.edit(f"🔮 سوال: {q}\nپاسخ جادوگر: **{answer}**")


@client.on(events.NewMessage(outgoing=True, pattern=pat(["عشق‌سنج", "love"])))
async def love_calc_handler(event):
    arg = event.pattern_match.group(1)
    if not arg:
        return await event.edit(f"مثال: `{PREFIX}عشق‌سنج علی و سارا`")
    names = re.split(r"\s+و\s+|\s*[+&]\s*", arg, maxsplit=1)
    if len(names) != 2 or not all(n.strip() for n in names):
        words = arg.split()
        if len(words) < 2:
            return await event.edit(f"مثال: `{PREFIX}عشق‌سنج علی و سارا`")
        names = [words[0], " ".join(words[1:])]
    a, b = names[0].strip(), names[1].strip()
    # نتیجه بر اساس هش دو اسم محاسبه می‌شه، پس برای یه جفتِ ثابت همیشه یکسانه
    key = "|".join(sorted([a.lower(), b.lower()]))
    percent = int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16) % 101
    if percent >= 80:
        note = "عالیه! 💞"
    elif percent >= 50:
        note = "بدک نیست 🙂"
    elif percent >= 20:
        note = "یه‌کم ضعیفه 😅"
    else:
        note = "شاید دوستیِ ساده بهتر باشه 😬"
    filled = percent // 10
    bar = "❤️" * filled + "🤍" * (10 - filled)
    await event.edit(f"💘 {a} + {b}\n{bar}\n**{percent}%** — {note}")


_WYR_PROMPTS = [
    # اصلی
    ("همیشه یک ساعت زودتر همه‌جا برسی", "همیشه یک ساعت دیرتر همه‌جا برسی"),
    ("بتونی پرواز کنی", "بتونی نامرئی بشی"),
    ("همیشه گرمت باشه", "همیشه سردت باشه"),
    ("پول زیاد ولی وقت کم داشته باشی", "وقت زیاد ولی پول کم داشته باشی"),
    ("هر روز پیتزا بخوری", "هر روز سوشی بخوری"),
    ("بتونی گذشته رو ببینی", "بتونی آینده رو ببینی"),
    ("توی جنگل زندگی کنی", "توی وسط شهر شلوغ زندگی کنی"),
    ("همیشه حقیقت رو بشنوی، حتی تلخ", "همیشه چیزی که دوست داری رو بشنوی"),
    ("بتونی ذهن بقیه رو بخونی", "بتونی هر زبونی رو بلد باشی"),
    ("هیچ‌وقت خسته نشی", "هیچ‌وقت گرسنه نشی"),
    # قدرت‌ها و ابرقهرمانی
    ("بتونی زمان رو متوقف کنی", "بتونی زمان رو برگردونی"),
    ("قدرت فوق‌العاده داشته باشی ولی تنها باشی", "قدرت معمولی داشته باشی ولی دوستان زیاد"),
    ("بتونی هر شبی که بخوای رویای دلخواهت رو ببینی", "هیچ‌وقت خواب نبینی و همیشه خواب راحت داشته باشی"),
    ("قدرت پرواز با سرعت کم", "قدرت دویدن با سرعت نور"),
    ("بتونی به حیوونا حرف بزنی", "بتونی به هر زبون انسانی حرف بزنی"),
    ("نامرئی بشی فقط شب‌ها", "پرواز کنی فقط روزها"),
    ("بتونی هر چیزی رو با فکر جابه‌جا کنی", "بتونی هر چیزی رو با لمس آتیش بزنی"),
    ("قدرت شفای خودت رو داشته باشی", "قدرت شفای دیگران رو داشته باشی"),
    ("بتونی سایز خودتو کوچیک کنی", "بتونی سایز خودتو بزرگ کنی"),
    ("قدرت کنترل آب داشته باشی", "قدرت کنترل باد داشته باشی"),
    # غذا و خوراکی
    ("تا آخر عمر فقط کباب بخوری", "تا آخر عمر فقط پیتزا بخوری"),
    ("هیچ‌وقت نتونی شیرینی بخوری", "هیچ‌وقت نتونی غذای شور بخوری"),
    ("غذاهای خیلی تند بخوری", "غذاهای کاملاً بی‌مزه بخوری"),
    ("همه‌ی غذات سرد باشه", "همه‌ی غذات خیلی داغ باشه"),
    ("فقط صبحونه بخوری تا آخر عمر", "فقط شام بخوری تا آخر عمر"),
    ("چای همیشه در دسترست باشه ولی بدون قند", "قهوه همیشه در دسترست باشه ولی تلخ"),
    ("هیچ‌وقت گشنه نشی ولی طعم غذا حس نکنی", "همیشه گشنه باشی ولی هر غذایی خوشمزه‌ترین چیز دنیا باشه"),
    ("فقط با دست غذا بخوری", "فقط با نی غذا بخوری"),
    ("آب‌میوه‌ی طبیعی رایگان تا آخر عمر", "قهوه‌ی مجانی تا آخر عمر"),
    ("هر روز آش رشته بخوری", "هر روز قورمه‌سبزی بخوری"),
    # زندگی روزمره و سبک زندگی
    ("صبح‌ها زود بیدار بشی ولی سرحال باشی", "دیر بیدار بشی ولی همیشه خسته باشی"),
    ("خونه‌ی بزرگ دور از شهر", "آپارتمان کوچیک وسط شهر"),
    ("همیشه پیاده بری سرکار", "همیشه با ترافیک سنگین بری سرکار"),
    ("هر روز باران ببارید", "هیچ‌وقت باران نباره"),
    ("توی گرمای شدید زندگی کنی", "توی سرمای شدید زندگی کنی"),
    ("همیشه تنها زندگی کنی", "همیشه با هم‌خونه زندگی کنی"),
    ("هیچ‌وقت نیاز به خواب نداشته باشی", "هیچ‌وقت نیاز به غذا نداشته باشی"),
    ("همیشه توی صف بمونی", "همیشه دیر برسی و صف رو از دست بدی"),
    ("هر روز صبح دویدن کنی", "هر شب یک ساعت پیاده‌روی کنی"),
    ("خونه‌ای با استخر داشته باشی", "خونه‌ای با باغ بزرگ داشته باشی"),
    # تکنولوژی
    ("گوشیت همیشه شارژ کم داشته باشه", "گوشیت همیشه اینترنت کند داشته باشه"),
    ("هیچ‌وقت نتونی پیام صوتی بفرستی", "هیچ‌وقت نتونی استیکر بفرستی"),
    ("یک هفته بدون اینترنت", "یک هفته بدون تلویزیون"),
    ("همیشه گوشیت رینگ صدا کنه", "همیشه گوشیت روی حالت بی‌صدا گیر کنه"),
    ("رمز عبورهات رو یادت بره", "همیشه با کپچا گیر کنی"),
    ("لپ‌تاپ خیلی قوی ولی بدون اینترنت", "اینترنت خیلی سریع ولی لپ‌تاپ ضعیف"),
    ("هر اپلیکیشنی که نصب کنی پر از تبلیغ باشه", "هر اپلیکیشنی که نصب کنی حجم خیلی زیادی بگیره"),
    ("بتونی هر فیلمی رو رایگان ببینی ولی با کیفیت پایین", "فقط یک فیلم با کیفیت عالی ببینی ولی پولی"),
    ("هوش مصنوعیِ شخصیت داشته باشه ولی گاهی اشتباه کنه", "هوش مصنوعیِ خیلی دقیق باشه ولی خشک و بی‌روح"),
    ("همیشه باتری پاوربانکت پر باشه", "همیشه سیم شارژرت همراهت باشه"),
    # حیوانات
    ("سگ نگه داری", "گربه نگه داری"),
    ("پرنده‌ی خونگی داشته باشی", "ماهی تزئینی داشته باشی"),
    ("بتونی مثل عقاب ببینی", "بتونی مثل سگ بو بکشی"),
    ("با یه شیر دوست بشی", "با یه پلنگ دوست بشی"),
    ("بتونی زیر آب مثل ماهی نفس بکشی", "بتونی روی زمین مثل پرنده پرواز کنی"),
    # سفر و ماجراجویی
    ("سفر به کوهستان", "سفر به ساحل"),
    ("سفر به گذشته‌ی تاریخی", "سفر به آینده‌ی دور"),
    ("دور دنیا با قطار", "دور دنیا با کشتی"),
    ("چادر زدن توی طبیعت", "اقامت توی هتل پنج‌ستاره"),
    ("سفر تنها", "سفر گروهی"),
    ("زندگی توی یه جزیره‌ی دورافتاده", "زندگی توی یه کلان‌شهر شلوغ"),
    ("سفر بدون برنامه‌ریزی", "سفر با برنامه‌ی دقیق از قبل"),
    ("رفتن به فضا", "رفتن به اعماق اقیانوس"),
    # پول و کار
    ("حقوق بالا با کار سخت", "حقوق متوسط با کار راحت"),
    ("رئیس خودت باشی با درآمد نامشخص", "کارمند باشی با درآمد ثابت"),
    ("پول زیاد یک‌باره ولی بعدش هیچی", "پول کم ولی هر ماه ثابت تا آخر عمر"),
    ("شغلی که دوستش داری با حقوق کم", "شغلی که ازش خوشت نمیاد با حقوق زیاد"),
    ("همیشه دورکار باشی", "همیشه توی دفتر کار کنی"),
    ("رئیس سخت‌گیر با تیم خوب", "رئیس خوب با تیم بد"),
    # روابط و اجتماعی
    ("یک دوست خیلی صمیمی داشته باشی", "چند تا دوست معمولی داشته باشی"),
    ("همیشه راستشو بگی حتی اگه بد باشه", "گاهی دروغ مصلحتی بگی"),
    ("مهمونیِ بزرگ و شلوغ", "دورهمیِ کوچیک و صمیمی"),
    ("همیشه توی جمع باشی", "بیشتر وقتت رو تنها باشی"),
    ("دوستی که همیشه دیر میاد", "دوستی که همیشه لغو می‌کنه"),
    ("همه چیزتو با یه نفر در میون بذاری", "چیزی رو با هیچکس در میون نذاری"),
    # سرگرمی و فرهنگ
    ("فیلم دیدن", "کتاب خوندن"),
    ("موسیقی گوش دادن", "پادکست گوش دادن"),
    ("بازی کامپیوتری", "بازی فکری روی میز"),
    ("کنسرت زنده", "سینمای خانگی"),
    ("فیلم ترسناک", "فیلم کمدی"),
    ("رمان عاشقانه", "رمان علمی‌تخیلی"),
    ("نقاشی کردن", "آواز خوندن"),
    ("رقصیدن جلوی جمع", "آواز خوندن جلوی جمع"),
    # فرضی و خنده‌دار
    ("همیشه با صدای بلند حرف بزنی", "همیشه خیلی آروم حرف بزنی"),
    ("هیچ‌وقت نخندی", "همیشه بی‌موقع بخندی"),
    ("هر دفعه عطسه کنی رعد و برق بزنه", "هر دفعه خمیازه بکشی چراغ‌ها خاموش بشن"),
    ("بتونی فقط دروغ بگی", "بتونی فقط راست بگی"),
    ("موهات همیشه رنگ عوض کنه", "چشمات همیشه رنگ عوض کنه"),
    ("هر روز لباس یکسان بپوشی", "هر روز مجبور باشی لباس عجیب بپوشی"),
    ("صدات مثل کارتون بشه", "قدت نصف بشه"),
    ("همیشه بوی نون تازه بدی", "همیشه بوی قهوه بدی"),
    ("بتونی فقط با آواز حرف بزنی", "بتونی فقط با رقص حرف بزنی"),
    ("سایه‌ت زندگی مستقل داشته باشه", "انعکاست توی آینه حرف بزنه"),
    # ورزش
    ("فوتبال بازی کنی", "بسکتبال بازی کنی"),
    ("شنا کردن", "دوچرخه‌سواری"),
    ("ورزش انفرادی", "ورزش تیمی"),
    ("کوهنوردی", "دویدن ماراتن"),
    ("یوگا", "بدنسازی"),
    # آب‌وهوا و فصل
    ("زندگی توی تابستون همیشگی", "زندگی توی زمستون همیشگی"),
    ("بهار همیشگی", "پاییز همیشگی"),
    ("برف‌بازی", "شنا توی دریا"),
    ("هوای مه‌آلود", "هوای آفتابیِ خیلی داغ"),
    # تصمیم‌های بزرگ زندگی
    ("زودتر ازدواج کنی", "دیرتر ازدواج کنی"),
    ("توی شهر زادگاهت بمونی", "به یه کشور دیگه مهاجرت کنی"),
    ("دنبال علاقه‌ت بری با ریسک بالا", "شغل امن انتخاب کنی با ریسک کم"),
    ("خانواده‌ی بزرگ داشته باشی", "خانواده‌ی کوچیک داشته باشی"),
    ("همیشه توی یه شهر زندگی کنی", "هر چند سال یه‌بار جابه‌جا بشی"),
]


@client.on(events.NewMessage(outgoing=True, pattern=pat(["این‌یا‌اون", "wyr"], arg=False)))
async def wyr_handler(event):
    a, b = random.choice(_WYR_PROMPTS)
    await event.edit(f"🤔 **این یا اون؟**\n\n1️⃣ {a}\n\nیا\n\n2️⃣ {b}")


# ---------------------------------------------------------------------------
# کوییز عمومی — با Open Trivia Database (opentdb.com، رایگان و بدون کلید)
# ---------------------------------------------------------------------------

QUIZ_GAMES = {}   # chat_id -> {"correct": int (۱ تا ۴), "answer_text": str}
QUIZ_SCORES = {}  # chat_id -> {"correct": int, "total": int} - فقط توی حافظه (ری‌استارت پاک می‌شه)

_QUIZ_TRANSLATE_SYSTEM_PROMPT = (
    "شما مترجمی هستید که سوالِ کوییزهای انگلیسی رو به فارسیِ روان و طبیعی "
    "ترجمه می‌کنه. اسم‌های خاص (افراد، مکان‌ها، فیلم‌ها، بازی‌ها و...) رو "
    "همون‌طور نگه دار یا فقط تلفظِ فارسیش رو بنویس. خروجی رو دقیقاً و فقط "
    "در همون قالبی که خواسته شده بده، بدون هیچ توضیحِ اضافه."
)


async def _translate_quiz(category: str, question: str, options: list[str]):
    """
    دسته/سوال/گزینه‌های کوییز رو (که از OpenTDB انگلیسی میان) با هسته‌ی
    هوش‌مصنوعیِ داخلیِ ربات (همون bot/ai.py که `.پرسش` ازش استفاده می‌کنه)
    به فارسی ترجمه می‌کنه. اگه AI غیرفعال باشه، خطا بده، یا خروجی قابلِ
    پارس‌کردن نباشه، None برمی‌گردونه (یعنی نسخه‌ی انگلیسیِ اصلی نمایش داده بشه)
    - هیچ‌وقت کوییز رو به‌خاطرِ خطای ترجمه از کار نمی‌ندازه.
    """
    prompt = (
        f"دسته: {category}\n"
        f"سوال: {question}\n"
        "گزینه‌ها:\n"
        + "\n".join(f"{i}) {opt}" for i, opt in enumerate(options, start=1))
        + "\n\n"
        "همه‌ی این‌ها رو به فارسیِ روان ترجمه کن. خروجی رو دقیقاً به همین "
        "قالب بده (فقط ترجمه، خط به خط، بدونِ هیچ توضیحِ اضافه):\n"
        "دسته: <ترجمه>\n"
        "سوال: <ترجمه>\n"
        + "\n".join(f"{i}) <ترجمه>" for i in range(1, len(options) + 1))
    )
    try:
        answer = await ai.ask_ai(
            [
                {"role": "system", "content": _QUIZ_TRANSLATE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )
    except (ai.AIDisabledError, ai.AIRequestError):
        return None
    if not answer:
        return None

    t_category = None
    t_question = None
    t_options = {}
    for line in answer.splitlines():
        line = line.strip()
        m_cat = re.match(r"^دسته\s*[:：]\s*(.+)$", line)
        m_q = re.match(r"^سوال\s*[:：]\s*(.+)$", line)
        m_opt = re.match(r"^(\d+)\s*[)\.]\s*(.+)$", line)
        if m_cat:
            t_category = m_cat.group(1).strip()
        elif m_q:
            t_question = m_q.group(1).strip()
        elif m_opt:
            idx = int(m_opt.group(1))
            t_options[idx] = m_opt.group(2).strip()

    if not t_question or len(t_options) != len(options):
        return None
    try:
        ordered_options = [t_options[i] for i in range(1, len(options) + 1)]
    except KeyError:
        return None
    return (t_category or category), t_question, ordered_options


@client.on(events.NewMessage(outgoing=True, pattern=pat(["کوییز", "quiz"])))
async def quiz_handler(event):
    """
    `.کوییز` یه سوالِ چهارگزینه‌ایِ تصادفی از Open Trivia Database می‌گیره،
    `.کوییز <۱ تا ۴>` به سوالِ فعالِ همون چت جواب می‌ده.
    """
    arg = (event.pattern_match.group(1) or "").strip()
    chat_id = event.chat_id

    if arg.isdigit() and 1 <= int(arg) <= 4:
        game = QUIZ_GAMES.get(chat_id)
        if not game:
            return await event.edit(
                f"سوالِ فعالی نیست. بزن `{PREFIX}کوییز` تا یه سوالِ جدید بیاد."
            )
        chosen = int(arg)
        del QUIZ_GAMES[chat_id]
        score = QUIZ_SCORES.setdefault(chat_id, {"correct": 0, "total": 0})
        score["total"] += 1
        if chosen == game["correct"]:
            score["correct"] += 1
            return await event.edit(
                f"✅ درسته! جواب «{game['answer_text']}» بود.\n"
                f"📊 امتیازِ این چت: {score['correct']}/{score['total']}"
            )
        return await event.edit(
            f"❌ نه. جوابِ درست، گزینه‌ی {game['correct']} («{game['answer_text']}») بود.\n"
            f"📊 امتیازِ این چت: {score['correct']}/{score['total']}"
        )

    await event.edit("🎲 در حالِ گرفتنِ سوال...")
    try:
        session = await get_http_session()
        async with session.get(
            "https://opentdb.com/api.php",
            params={"amount": 1, "type": "multiple", "encode": "url3986"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            data = await r.json(content_type=None)
    except errors.FloodWaitError:
        raise
    except Exception:
        _record_error()
        return await event.edit("❌ خطا در ارتباط با سرویسِ کوییز (opentdb.com)")

    if data.get("response_code") != 0 or not data.get("results"):
        return await event.edit("⚠️ سوالی پیدا نشد، دوباره امتحان کن")

    q = data["results"][0]
    unquote = urllib.parse.unquote
    category = unquote(q.get("category", ""))
    question = unquote(q.get("question", ""))
    correct = unquote(q.get("correct_answer", ""))
    options = [unquote(a) for a in q.get("incorrect_answers", [])] + [correct]
    random.shuffle(options)
    correct_index = options.index(correct) + 1

    # نمایشِ سوال/گزینه‌ها به فارسی (اگه AI فعال باشه و ترجمه جواب بده)؛
    # correct_index از رویِ متنِ اصلیِ انگلیسی حساب شده و دست‌نخورده می‌مونه،
    # چون فقط متنِ نمایشی عوض می‌شه نه ترتیبِ گزینه‌ها.
    await event.edit("🌐 در حالِ ترجمه...")
    translated = await _translate_quiz(category, question, options)
    if translated:
        display_category, display_question, display_options = translated
    else:
        display_category, display_question, display_options = category, question, options

    QUIZ_GAMES[chat_id] = {"correct": correct_index, "answer_text": display_options[correct_index - 1]}

    lines = [f"❓ **کوییز** — _{display_category}_", "", display_question, ""]
    for i, opt in enumerate(display_options, start=1):
        lines.append(f"{i}) {opt}")
    lines.append("")
    lines.append(f"جواب رو با `{PREFIX}کوییز <عدد>` بده")
    await event.edit("\n".join(lines))


# ---------------------------------------------------------------------------
# فال حافظ — از PostgreSQL (جدولِ hafez_poems)، نه import در لحظه
# ---------------------------------------------------------------------------
# دیتا با `scripts/seed_hafez.py` (یک‌بار، خارج از خودِ ربات) پر می‌شه؛ اینجا
# فقط یه ردیفِ رندوم می‌خونیم - نه importِ زمانِ‌اجرا، نه pip، نه شبکه.

@client.on(events.NewMessage(outgoing=True, pattern=pat(["فال", "hafez"], arg=False)))
async def hafez_fal_handler(event):
    """یه فالِ حافظِ تصادفی از جدولِ hafez_poems (PostgreSQL) می‌گیره."""
    try:
        row = await hafez_repo.random_poem()
    except Exception:
        _record_error()
        logger.exception("خطا در خوندنِ فال از دیتابیس")
        return await event.edit("❌ خطا در ارتباط با دیتابیس")

    if row is None:
        return await event.edit(
            "⚠️ جدولِ فال هنوز خالیه. یه‌بار (فقط یه‌بار، نه هر دفعه) از روی "
            "سرور این رو اجرا کن:\n"
            "`pip install hafez && python scripts/seed_hafez.py`\n\n"
            "بعدش `.فال` همیشه مستقیم از دیتابیسِ خودمون جواب می‌ده، بدون "
            "هیچ نصب/شبکه‌ای."
        )

    body = f"🔮 **فالِ حافظ**\n\n{row.poem}"
    if row.interpretation:
        body += f"\n\n💬 **تفسیر:**\n{row.interpretation}"
    await event.edit(body)

