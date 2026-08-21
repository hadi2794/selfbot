"""فونت‌های پیام: انگلیسی (یونیکد ریاضی) / فارسی (تزئینی) / ترکیبی."""


def _build_latin_map(upper_start, lower_start, digit_start=None, exceptions=None):
    """
    یه نگاشت A-Z/a-z (و اختیاری ۰-۹) به یه بلاک یونیکد پیوسته می‌سازه.
    exceptions برای حروفی که یونیکد به‌جای بلاک اصلی از نمادهای قدیمی‌تر
    استفاده کرده (مثلاً اسکریپت یا فراکتور) به کار می‌ره.
    """
    exceptions = exceptions or {}
    mapping = {}
    for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        mapping[ch] = exceptions.get(ch, chr(upper_start + i))
    for i, ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
        mapping[ch] = exceptions.get(ch, chr(lower_start + i))
    if digit_start is not None:
        for i, ch in enumerate("0123456789"):
            mapping[ch] = chr(digit_start + i)
    return mapping


_BOLD_MAP = _build_latin_map(0x1D400, 0x1D41A, 0x1D7CE)
_ITALIC_MAP = _build_latin_map(0x1D434, 0x1D44E, exceptions={"h": "\u210E"})
_BOLD_ITALIC_MAP = _build_latin_map(0x1D468, 0x1D482)
_SCRIPT_MAP = _build_latin_map(0x1D49C, 0x1D4B6, exceptions={
    "B": "\u212C", "E": "\u2130", "F": "\u2131", "H": "\u210B", "I": "\u2110",
    "L": "\u2112", "M": "\u2133", "R": "\u211B",
    "e": "\u212F", "g": "\u210A", "o": "\u2134",
})
_FRAKTUR_MAP = _build_latin_map(0x1D504, 0x1D51E, exceptions={
    "C": "\u212D", "H": "\u210C", "I": "\u2111", "R": "\u211C", "Z": "\u2128",
})
_SANS_BOLD_MAP = _build_latin_map(0x1D5D4, 0x1D5EE, 0x1D7EC)
_MONO_MAP = _build_latin_map(0x1D670, 0x1D68A, 0x1D7F6)
_CIRCLED_MAP = _build_latin_map(0x24B6, 0x24D0)

_SMALLCAPS_MAP = {
    "a": "\u1D00", "b": "\u0299", "c": "\u1D04", "d": "\u1D05", "e": "\u1D07",
    "f": "\uA730", "g": "\u0262", "h": "\u029C", "i": "\u026A", "j": "\u1D0A",
    "k": "\u1D0B", "l": "\u029F", "m": "\u1D0D", "n": "\u0274", "o": "\u1D0F",
    "p": "\u1D18", "q": "q", "r": "\u0280", "s": "s", "t": "\u1D1B",
    "u": "\u1D1C", "v": "\u1D20", "w": "\u1D21", "x": "x", "y": "\u028F", "z": "\u1D22",
}
for _c in list(_SMALLCAPS_MAP.keys()):
    _SMALLCAPS_MAP[_c.upper()] = _SMALLCAPS_MAP[_c]

_FLIP_MAP = {
    "a": "ɐ", "b": "q", "c": "ɔ", "d": "p", "e": "ǝ", "f": "ɟ", "g": "ƃ",
    "h": "ɥ", "i": "ᴉ", "j": "ɾ", "k": "ʞ", "l": "l", "m": "ɯ", "n": "u",
    "o": "o", "p": "d", "q": "b", "r": "ɹ", "s": "s", "t": "ʇ", "u": "n",
    "v": "ʌ", "w": "ʍ", "x": "x", "y": "ʎ", "z": "z",
    "0": "0", "1": "Ɩ", "2": "ᄅ", "3": "Ɛ", "4": "ㄣ", "5": "ϛ", "6": "9",
    "7": "ㄥ", "8": "8", "9": "6", "?": "¿", "!": "¡",
}
for _c in list(_FLIP_MAP.keys()):
    if _c.isalpha():
        _FLIP_MAP[_c.upper()] = _FLIP_MAP[_c]


def _apply_map(text, mapping):
    return "".join(mapping.get(ch, ch) for ch in text)


def _flip_text(text):
    return "".join(_FLIP_MAP.get(ch, ch) for ch in text)[::-1]


def _persian_spaced(t):
    return " ".join(list(t))


# حروفی که فقط به حرفِ قبلی می‌چسبن، نه به حرفِ بعدی - نباید بعدشون تطویل بذاریم
_NON_FORWARD_JOIN = set("اآدذرزژو")


def _persian_kashida(t):
    """
    کشیدگی واقعی حروف با تطویل عربی (ـ) - همون تکنیکی که توی چاپ و خوشنویسی
    فارسی/عربی برای کشیده‌کردن کلمات استفاده می‌شه. برخلاف نمادهای تزئینی،
    این یه کاراکتر استاندارد و پشتیبانی‌شده روی همه‌ی گوشی‌هاست.
    """
    chars = list(t)
    out = []
    for i, ch in enumerate(chars):
        out.append(ch)
        is_persian = "\u0600" <= ch <= "\u06FF"
        next_is_persian = i < len(chars) - 1 and "\u0600" <= chars[i + 1] <= "\u06FF"
        if is_persian and ch not in _NON_FORWARD_JOIN and next_is_persian:
            out.append("\u0640")  # ـ تطویل
    return "".join(out)


def _combining_style(t, mark):
    return "".join(ch + mark if ch != " " else ch for ch in t)


def _persian_underline(t):
    return _combining_style(t, "\u0332")  # زیرخط واقعی روی هر حرف


def _persian_strike(t):
    return _combining_style(t, "\u0336")  # خط‌خوردگی واقعی روی هر حرف


ENGLISH_FONTS = {
    "bold": lambda t: _apply_map(t, _BOLD_MAP),
    "italic": lambda t: _apply_map(t, _ITALIC_MAP),
    "bold_italic": lambda t: _apply_map(t, _BOLD_ITALIC_MAP),
    "script": lambda t: _apply_map(t, _SCRIPT_MAP),
    "fraktur": lambda t: _apply_map(t, _FRAKTUR_MAP),
    "sans_bold": lambda t: _apply_map(t, _SANS_BOLD_MAP),
    "monospace": lambda t: _apply_map(t, _MONO_MAP),
    "smallcaps": lambda t: _apply_map(t, _SMALLCAPS_MAP),
    "circled": lambda t: _apply_map(t, _CIRCLED_MAP),
    "upside_down": _flip_text,
}

PERSIAN_FONTS = {
    "fa_kashida": _persian_kashida,   # کشیدگی واقعی با تطویل - رندر درست همه‌جا
    "fa_underline": _persian_underline,  # زیرخط واقعی روی تک‌تک حروف
    "fa_strike": _persian_strike,     # خط‌خوردگی واقعی روی تک‌تک حروف
    "fa_spaced": _persian_spaced,
    "fa_stars": lambda t: f"✦ {t} ✦",
    "fa_flowers": lambda t: f"⋆｡°✩ {t} ✩°｡⋆",
    "fa_brackets": lambda t: f"『{t}』",
    "fa_elegant": lambda t: f"⟪ {t} ⟫",
    "fa_ribbon": lambda t: f"⸙ {t} ⸙",
    "fa_diamond": lambda t: f"◈ {t} ◈",
    "fa_wave": lambda t: f"﹋﹋ {t} ﹋﹋",
    "fa_boxed": lambda t: f"【{t}】",
    "fa_hearts": lambda t: f"❀ {t} ❀",
}

COMBINED_FONTS = {
    "mix_bold": lambda t: f"✦ {_apply_map(t, _BOLD_MAP)} ✦",
    "mix_italic": lambda t: f"『{_apply_map(t, _ITALIC_MAP)}』",
    "mix_script": lambda t: f"⟪ {_apply_map(t, _SCRIPT_MAP)} ⟫",
    "mix_mono": lambda t: f"⌗ {_apply_map(t, _MONO_MAP)} ⌗",
}

FONT_STYLES = {**ENGLISH_FONTS, **PERSIAN_FONTS, **COMBINED_FONTS}
