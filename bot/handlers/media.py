"""🖼 رسانه و فایل: واترمارک / فشرده‌سازی / تبدیل فرمت / استیکر"""
import os
import shutil
import subprocess
import tempfile
from io import BytesIO

from telethon import events, functions, types

from ..config import PREFIX
from ..runtime import client
from ..utils import pat

# فونت‌هایی که برای واترمارک امتحان می‌شن (اگه پکیج fonts-dejavu-core نصب
# باشه اولی پیدا می‌شه، وگرنه به فونت پیش‌فرض Pillow برمی‌گردیم)
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVuSans-Bold.ttf",
]

IMAGE_TARGETS = {"png", "jpg", "jpeg", "webp", "bmp", "gif"}
AUDIO_TARGETS = {"mp3", "ogg", "wav", "m4a", "opus", "flac"}
VIDEO_TARGETS = {"mp4", "webm", "mov", "mkv"}


def _human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def _load_font(size: int):
    from PIL import ImageFont
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return None


def _render_watermark_image(text: str, target_height: int):
    """
    متنِ واترمارک رو روی یه بومِ RGBAِ شفاف رسم می‌کنه و برمی‌گردونه.
    اگه هیچ فونتِ truetype‌ای روی سیستم پیدا نشه (مثلاً fonts-dejavu-core
    نصب نیست)، با فونتِ ریزِ پیش‌فرضِ Pillow رسم می‌کنه و بعد نتیجه رو با
    resize به اندازه‌ی هدف بزرگ می‌کنه - وگرنه متن اونقدر ریز می‌مونه که
    روی عکس‌های معمولی عملاً دیده نمی‌شه.
    """
    from PIL import Image, ImageDraw, ImageFont

    font = _load_font(target_height)
    use_scale = font is None
    if font is None:
        font = ImageFont.load_default()

    probe = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(probe)
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 4
    canvas = Image.new("RGBA", (max(tw, 1) + pad * 2, max(th, 1) + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    ox, oy = pad - bbox[0], pad - bbox[1]
    # سایه‌ی محو زیرِ متن تا روی هر پس‌زمینه‌ای خونا بمونه
    d.text((ox + 2, oy + 2), text, font=font, fill=(0, 0, 0, 170))
    d.text((ox, oy), text, font=font, fill=(255, 255, 255, 200))

    if use_scale and th > 0:
        scale = max(target_height / th, 1.0)
        new_size = (max(1, round(canvas.width * scale)), max(1, round(canvas.height * scale)))
        canvas = canvas.resize(new_size, Image.LANCZOS)
    return canvas


def _is_image_message(msg) -> bool:
    if msg.photo:
        return True
    if msg.document and (msg.document.mime_type or "").startswith("image/"):
        return True
    return False


def _is_video_message(msg) -> bool:
    if msg.video:
        return True
    if msg.document and (msg.document.mime_type or "").startswith("video/"):
        return True
    return False


def _guess_ext(msg) -> str:
    if msg.photo:
        return "jpg"
    if msg.document:
        name = None
        for attr in msg.document.attributes:
            if getattr(attr, "file_name", None):
                name = attr.file_name
                break
        if name and "." in name:
            return name.rsplit(".", 1)[-1].lower()
        mime = msg.document.mime_type or ""
        if "/" in mime:
            return mime.split("/")[-1].split(";")[0].lower()
    return "bin"


# ------------------------------------------------------------------ واترمارک
@client.on(events.NewMessage(outgoing=True, pattern=pat(["واترمارک", "watermark"])))
async def watermark_handler(event):
    if not event.is_reply:
        return await event.edit(
            f"روی یه عکس ریپلای کن. مثال: `{PREFIX}واترمارک © نام من`"
        )
    reply = await event.get_reply_message()
    if not _is_image_message(reply):
        return await event.edit("❌ پیام ریپلای‌شده عکس نیست")

    text = (event.pattern_match.group(1) or "").strip() or "@Telegram"

    msg = await event.edit("⏳ در حال ساخت واترمارک...")
    try:
        from PIL import Image

        raw = await client.download_media(reply, file=bytes)
        img = Image.open(BytesIO(raw)).convert("RGBA")

        font_size = max(int(min(img.size) * 0.05), 22)
        text_img = _render_watermark_image(text, font_size)

        margin = max(int(min(img.size) * 0.03), 10)
        x = img.width - text_img.width - margin
        y = img.height - text_img.height - margin

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        overlay.paste(text_img, (max(x, 0), max(y, 0)), text_img)

        result = Image.alpha_composite(img, overlay).convert("RGB")
        bio = BytesIO()
        bio.name = "watermarked.jpg"
        result.save(bio, "JPEG", quality=92)
        bio.seek(0)

        await client.send_file(
            event.chat_id, bio,
            caption=f"🖼 واترمارک اضافه شد: «{text}»",
            reply_to=reply.id,
        )
        await msg.delete()
    except Exception as e:
        await msg.edit(f"❌ خطا در ساخت واترمارک: {e}")


# --------------------------------------------------------------- فشرده‌سازی
@client.on(events.NewMessage(outgoing=True, pattern=pat(["فشرده‌سازی", "فشرده", "compress"], arg=False)))
async def compress_handler(event):
    if not event.is_reply:
        return await event.edit("روی یه عکس یا ویدیو ریپلای کن")
    reply = await event.get_reply_message()
    if not (_is_image_message(reply) or _is_video_message(reply)):
        return await event.edit("❌ پیام ریپلای‌شده عکس یا ویدیو نیست")

    msg = await event.edit("⏳ در حال فشرده‌سازی...")
    try:
        raw = await client.download_media(reply, file=bytes)
        original_size = len(raw)

        if _is_video_message(reply):
            if not _has_ffmpeg():
                return await msg.edit("❌ ffmpeg روی سرور نصب نیست؛ فشرده‌سازی ویدیو ممکن نیست")
            src_ext = _guess_ext(reply) or "mp4"
            with tempfile.TemporaryDirectory() as td:
                src = os.path.join(td, f"in.{src_ext}")
                dst = os.path.join(td, "out.mp4")
                with open(src, "wb") as f:
                    f.write(raw)
                proc = subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", src,
                        "-vcodec", "libx264", "-crf", "30", "-preset", "veryfast",
                        "-vf", "scale='min(854,iw)':-2",
                        "-acodec", "aac", "-b:a", "96k",
                        dst,
                    ],
                    capture_output=True, timeout=300,
                )
                if proc.returncode != 0 or not os.path.exists(dst):
                    return await msg.edit("❌ خطا در فشرده‌سازی ویدیو")
                with open(dst, "rb") as f:
                    out_bytes = f.read()
            bio = BytesIO(out_bytes)
            bio.name = "compressed.mp4"
        else:
            from PIL import Image
            img = Image.open(BytesIO(raw)).convert("RGB")
            max_side = 1280
            if max(img.size) > max_side:
                ratio = max_side / max(img.size)
                img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))))
            bio = BytesIO()
            bio.name = "compressed.jpg"
            img.save(bio, "JPEG", quality=70, optimize=True)

        out_size = bio.getbuffer().nbytes
        bio.seek(0)
        pct = (1 - out_size / original_size) * 100 if original_size else 0
        await client.send_file(
            event.chat_id, bio,
            caption=f"📉 فشرده شد: {_human_size(original_size)} ← {_human_size(out_size)} (کاهش {pct:.0f}٪)",
            reply_to=reply.id,
        )
        await msg.delete()
    except subprocess.TimeoutExpired:
        await msg.edit("❌ فشرده‌سازی بیش از حد طول کشید")
    except Exception as e:
        await msg.edit(f"❌ خطا در فشرده‌سازی: {e}")


# ------------------------------------------------------------------- تبدیل
@client.on(events.NewMessage(outgoing=True, pattern=pat(["تبدیل", "convert"])))
async def convert_handler(event):
    target = (event.pattern_match.group(1) or "").strip().lower().lstrip(".")
    if not event.is_reply or not target:
        return await event.edit(
            f"روی یه فایل ریپلای کن و فرمت مقصد رو بنویس.\n"
            f"مثال: `{PREFIX}تبدیل png` (روی استیکرِ webp) یا `{PREFIX}تبدیل mp3` (روی وویس)\n"
            f"عکس: {', '.join(sorted(IMAGE_TARGETS))}\n"
            f"صدا: {', '.join(sorted(AUDIO_TARGETS))}\n"
            f"ویدیو: {', '.join(sorted(VIDEO_TARGETS))}"
        )
    reply = await event.get_reply_message()
    if not (reply.photo or reply.document):
        return await event.edit("❌ پیام ریپلای‌شده فایل/عکس/صدا/ویدیو نیست")

    src_ext = _guess_ext(reply)
    msg = await event.edit(f"⏳ در حال تبدیل {src_ext} به {target}...")
    try:
        raw = await client.download_media(reply, file=bytes)

        if target in IMAGE_TARGETS and _is_image_message(reply):
            from PIL import Image
            img = Image.open(BytesIO(raw))
            fmt = "JPEG" if target in ("jpg", "jpeg") else target.upper()
            if fmt == "JPEG":
                img = img.convert("RGB")
            bio = BytesIO()
            bio.name = f"converted.{target}"
            img.save(bio, fmt)
            bio.seek(0)

        elif target in AUDIO_TARGETS or target in VIDEO_TARGETS:
            if not _has_ffmpeg():
                return await msg.edit("❌ ffmpeg روی سرور نصب نیست")
            with tempfile.TemporaryDirectory() as td:
                src = os.path.join(td, f"in.{src_ext}")
                dst = os.path.join(td, f"out.{target}")
                with open(src, "wb") as f:
                    f.write(raw)
                cmd = ["ffmpeg", "-y", "-i", src]
                if target in AUDIO_TARGETS:
                    cmd += ["-vn"]
                cmd.append(dst)
                proc = subprocess.run(cmd, capture_output=True, timeout=300)
                if proc.returncode != 0 or not os.path.exists(dst):
                    return await msg.edit("❌ خطا در تبدیل - فرمتِ مبدأ/مقصد پشتیبانی نمی‌شه")
                with open(dst, "rb") as f:
                    out_bytes = f.read()
            bio = BytesIO(out_bytes)
            bio.name = f"converted.{target}"

        else:
            return await msg.edit(
                "❌ فرمت مقصد پشتیبانی نمی‌شه یا با نوع فایل ریپلای‌شده جور نیست.\n"
                f"عکس: {', '.join(sorted(IMAGE_TARGETS))}\n"
                f"صدا: {', '.join(sorted(AUDIO_TARGETS))}\n"
                f"ویدیو: {', '.join(sorted(VIDEO_TARGETS))}"
            )

        await client.send_file(
            event.chat_id, bio,
            caption=f"🔄 تبدیل شد به {target}",
            reply_to=reply.id,
            force_document=True,
        )
        await msg.delete()
    except subprocess.TimeoutExpired:
        await msg.edit("❌ تبدیل بیش از حد طول کشید")
    except Exception as e:
        await msg.edit(f"❌ خطا در تبدیل: {e}")


# ------------------------------------------------------------------- استیکر
def _sanitize_short_name(name: str) -> str:
    cleaned = "".join(c for c in name if c.isalnum() or c == "_")
    if not cleaned:
        cleaned = "pack"
    if not cleaned[0].isalpha():
        cleaned = "s" + cleaned
    return cleaned[:60]


@client.on(events.NewMessage(outgoing=True, pattern=pat(["استیکر", "sticker"])))
async def sticker_handler(event):
    if not event.is_reply:
        return await event.edit(
            f"روی یه عکس ریپلای کن. مثال: `{PREFIX}استیکر my_pack 😄`\n"
            f"(اگه اسمِ پک رو ندی، یه پکِ شخصیِ پیش‌فرض ساخته/استفاده می‌شه)"
        )
    reply = await event.get_reply_message()
    if not (reply.photo or (reply.document and (reply.document.mime_type or "").startswith("image/"))):
        return await event.edit("❌ پیام ریپلای‌شده عکس نیست")

    args = (event.pattern_match.group(1) or "").split()
    from ..runtime import SELF_ID
    short_name = _sanitize_short_name(args[0]) if args else f"pack{SELF_ID or 0}"
    emoji = args[1] if len(args) > 1 else "🙂"
    title = f"پکِ {short_name}"

    msg = await event.edit("⏳ در حال ساخت استیکر...")
    try:
        from PIL import Image

        raw = await client.download_media(reply, file=bytes)
        img = Image.open(BytesIO(raw)).convert("RGBA")
        w, h = img.size
        if w >= h:
            new_w, new_h = 512, max(1, round(h * 512 / w))
        else:
            new_h, new_w = 512, max(1, round(w * 512 / h))
        img = img.resize((new_w, new_h), Image.LANCZOS)

        webp_bio = BytesIO()
        img.save(webp_bio, "WEBP")
        webp_bio.seek(0)

        # فایل رو اول به Saved Messages می‌فرستیم تا یه Document واقعی با
        # id/access_hash/file_reference بگیریم - ورودیِ لازم برای ساختِ استیکر
        uploaded = await client.upload_file(webp_bio.getvalue(), file_name="sticker.webp")
        sent = await client.send_message("me", file=uploaded, force_document=True)
        doc = sent.document
        input_doc = types.InputDocument(
            id=doc.id, access_hash=doc.access_hash, file_reference=doc.file_reference,
        )
        await sent.delete()

        item = types.InputStickerSetItem(document=input_doc, emoji=emoji)
        stickerset_ref = types.InputStickerSetShortName(short_name=short_name)

        try:
            await client(functions.messages.GetStickerSetRequest(stickerset=stickerset_ref, hash=0))
            pack_exists = True
        except Exception:
            pack_exists = False

        if pack_exists:
            await client(functions.stickers.AddStickerToSetRequest(stickerset=stickerset_ref, sticker=item))
            await msg.edit(f"✅ استیکر به پکِ «{short_name}» اضافه شد\nhttps://t.me/addstickers/{short_name}")
        else:
            me = await client.get_me()
            await client(functions.stickers.CreateStickerSetRequest(
                user_id=me, title=title, short_name=short_name, stickers=[item],
            ))
            await msg.edit(f"✅ پکِ جدیدِ «{short_name}» ساخته شد\nhttps://t.me/addstickers/{short_name}")

    except Exception as e:
        err = str(e)
        if "SHORTNAME_OCCUPIED" in err or "occupied" in err.lower():
            await msg.edit("❌ این نامِ پک قبلاً توسط یه اکانتِ دیگه گرفته شده؛ یه اسمِ دیگه امتحان کن")
        elif "SHORT_NAME_INVALID" in err:
            await msg.edit("❌ نامِ پک نامعتبره (فقط حروف/عدد/آندرلاین، شروع با حرف)")
        else:
            await msg.edit(f"❌ خطا در ساخت استیکر: {e}")
