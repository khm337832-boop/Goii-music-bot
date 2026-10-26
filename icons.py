"""Pretty, consistent icons and message styling for Goii Music Bot.

Everything user-facing is built here so the look & feel stays in one place.
All dynamic values are HTML-escaped -> safe to send with ``parse_mode=HTML``.
"""
from __future__ import annotations

import html
import re
import unicodedata
from typing import Iterable


class I:
    """Icon palette (emoji). Change these to restyle the whole bot at once."""

    BOT = "🎧"
    BRAIN = "🧠"
    ROBOT = "🤖"
    SPARKLES = "✨"
    SEARCH = "🔎"
    NOTES = "🎶"
    MUSIC = "🎵"
    HEADPHONES = "🎧"
    DISC = "💿"
    MIC = "🎤"
    FIRE = "🔥"
    HEART = "❤️"
    STAR = "⭐"
    CHECK = "✅"
    CROSS = "❌"
    WARN = "⚠️"
    CLOCK = "⏳"
    INBOX = "📥"
    UPLOAD = "📤"
    REFRESH = "🔄"
    INFO = "ℹ️"
    WAVE = "👋"
    BULB = "💡"
    LINK = "🔗"
    KEY = "🔑"
    CLOUD = "☁️"
    BOX = "📦"
    PENCIL = "✍️"
    BACK = "🔙"
    PLAY = "▶️"
    DOWN = "👇"
    RAINBOW = "🌈"
    DIVIDER = "━" * 18
    SOFT_DIVIDER = "─" * 14


NUMBER_ICONS = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣")
TRACK_ICONS = (I.MUSIC, I.NOTES, I.DISC, I.HEADPHONES, I.MIC)
PROVIDER_ICONS = {
    "gemini": "✨",
    "openai": "🟢",
    "groq": "⚡",
    "openrouter": "🟣",
    "custom": "🤖",
    "local": "📦",
}
PROVIDER_NAMES = {
    "gemini": "Gemini",
    "openai": "OpenAI",
    "groq": "Groq",
    "openrouter": "OpenRouter",
    "custom": "Custom AI",
    "local": "Local brain",
}


def esc(value: object) -> str:
    """HTML-escape any value coming from a user, YouTube or an LLM."""
    return html.escape(str(value if value is not None else ""), quote=False)


def safe_trim(text: object, limit: int = 40) -> str:
    """Shorten text for button labels without breaking Burmese combining marks."""
    value = unicodedata.normalize("NFC", str(text or ""))
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= limit:
        return value
    cut = value[: max(1, limit - 1)]
    while cut and (unicodedata.combining(cut[-1]) or unicodedata.category(cut[-1]) in {"Mn", "Mc"}):
        cut = cut[:-1]
    return cut.rstrip() + "…"


def fmt_duration(seconds: int) -> str:
    """Turn 215 into ``3:35``."""
    try:
        total = int(seconds or 0)
    except (TypeError, ValueError):
        return ""
    if total <= 0:
        return ""
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def provider_badge(provider: str) -> str:
    """Small, friendly label showing which brain answered."""
    icon = PROVIDER_ICONS.get(provider, I.ROBOT)
    name = PROVIDER_NAMES.get(provider, provider.title())
    return f"{icon} <i>Goii AI · {esc(name)}</i>"


def track_label(index: int, title: str, duration: int = 0) -> str:
    """Button label: ``1️⃣ 🎵 Song name · 3:35``."""
    number = NUMBER_ICONS[index] if index < len(NUMBER_ICONS) else f"{index + 1}."
    note = TRACK_ICONS[index % len(TRACK_ICONS)]
    length = fmt_duration(duration)
    tail = f" · {length}" if length else ""
    return f"{number} {note} {safe_trim(title, 34)}{tail}"


def welcome_text() -> str:
    return (
        f"{I.SPARKLES} <b>Goii Music Bot</b> {I.HEADPHONES}\n"
        f"{I.DIVIDER}\n"
        f"{I.WAVE} မင်္ဂလာပါနော်! သီချင်းရှာပေးတဲ့အပြင် "
        f"<b>စဉ်းစားတတ်တဲ့ AI</b> လည်း ပါပါတယ် {I.BRAIN}\n\n"
        f"{I.MUSIC} သီချင်းအမည် / အဆိုတော်အမည် ရိုက်ပေးပါ\n"
        f"{I.RAINBOW} စိတ်ခံစားချက်လေး ပြောရင်လည်း ညွှန်းပေးပါ့မယ်\n"
        f"{I.ROBOT} အဆိုတော်အကြောင်း မေးချင်ရင်လည်း မေးလို့ရပါတယ်\n"
        f"{I.SOFT_DIVIDER}\n"
        f"<i>ဥပမာ · “စိတ်ပျက်နေတယ် သီချင်းလေးညွှန်းပေးပါ”</i>"
    )


def help_text(provider: str) -> str:
    return (
        f"{I.INFO} <b>အကူအညီ / Commands</b>\n"
        f"{I.DIVIDER}\n"
        f"{I.PENCIL} စာရိုက်ရုံနဲ့ သီချင်းရှာပေးပါတယ်\n"
        f"{I.ROBOT} <code>/ai မေးခွန်း</code> · AI ကို တိုက်ရိုက်မေးမယ်\n"
        f"{I.SEARCH} <code>/search သီချင်းအမည်</code> · တိုက်ရိုက်ရှာမယ်\n"
        f"{I.BRAIN} <code>/brain</code> · AI အခြေအနေ ကြည့်မယ်\n"
        f"{I.LINK} <code>/link</code> · Bot ရဲ့ t.me link ရယူမယ်\n"
        f"{I.STAR} <code>/start</code> · မီနူး ပြန်ဖွင့်မယ်\n"
        f"{I.SOFT_DIVIDER}\n"
        f"{I.BULB} စာလုံးပေါင်းမှားရင်၊ အဆိုတော်ကို တိုက်ရိုက်မသိရင်လည်း "
        f"AI က နားလည်အောင် ကြိုးစားပေးပါလိမ့်မယ်။\n"
        f"{provider_badge(provider)}"
    )


def brain_status_text(provider: str, has_key: bool, model: str = "") -> str:
    cloud = provider != "local"
    state = f"{I.CLOUD} <b>Cloud AI</b> ချိတ်ဆက်ထားပါတယ်" if cloud else f"{I.BOX} <b>Local brain</b> နဲ့ အလုပ်လုပ်နေပါတယ်"
    key_state = f"{I.CHECK} ရှိပါတယ်" if has_key else f"{I.WARN} မရှိသေးပါ"
    model_line = f"\n{I.STAR} Model · <code>{esc(model)}</code>" if model else ""
    if cloud:
        detail = "သီချင်း၊ အဆိုတော်၊ စိတ်ခံစားချက်၊ မေးခွန်းအားလုံးကို နားလည်ပါတယ် 🧠"
    else:
        detail = (
            "မြန်မာလို/အင်္ဂလိပ်လို တောင်းဆိုချက်၊ စာလုံးပေါင်းမှားချက်၊ "
            "mood တွေကို နားလည်ပါတယ်။ အဆိုတော်အကြောင်း အသေးစိတ် ဖြေဖို့ "
            "<code>AI_API_KEY</code> ထည့်ပေးပါနော် 🔑"
        )
    return (
        f"{I.BRAIN} <b>Goii AI အခြေအနေ</b>\n"
        f"{I.DIVIDER}\n"
        f"{I.ROBOT} Engine · <code>{esc(provider)}</code>\n"
        f"{I.KEY} Key · {key_state}\n"
        f"{I.HEART} {state}{model_line}\n"
        f"{I.SOFT_DIVIDER}\n"
        f"{detail}\n"
        f"{provider_badge(provider)}"
    )


def thinking_text() -> str:
    return f"{I.BRAIN} <b>Goii AI</b> စဉ်းစားနေပါတယ်… {I.SPARKLES}"


def searching_text(query: str) -> str:
    return f"{I.SEARCH} <b>{esc(safe_trim(query, 70))}</b> ကို ရှာဖွေနေပါတယ်… {I.NOTES}"


def results_text(query: str, count: int, provider: str, page: int = 0) -> str:
    page_note = f" · အသစ်တစ်ခေါက် {I.REFRESH}" if page else ""
    return (
        f"{I.NOTES} <b>ရလဒ် {count} ပုဒ် တွေ့ပါတယ်</b> {I.SPARKLES}\n"
        f"{I.SOFT_DIVIDER}\n"
        f"{I.SEARCH} <code>{esc(safe_trim(query, 80))}</code>{page_note}\n"
        f"{I.DOWN} ကြိုက်တာလေးကို နှိပ်ပြီး MP3 ရယူလိုက်ပါနော် 🎧\n"
        f"{provider_badge(provider)}"
    )


def no_results_text(query: str, provider: str) -> str:
    hint = ""
    if provider == "local":
        hint = f"\n{I.BULB} Cloud AI key ထည့်ရင် ပိုပြီး နားလည်အောင် ရှာပေးနိုင်ပါတယ် 🔑"
    return (
        f"{I.WARN} <b>{esc(safe_trim(query, 70))}</b> အတွက် ရှာမတွေ့ပါဘူး။\n"
        f"{I.SOFT_DIVIDER}\n"
        f"{I.PENCIL} အမည်ကို နည်းနည်းပြောင်းပြီး ပြန်ရိုက်ကြည့်ပါနော်။{hint}\n"
        f"{provider_badge(provider)}"
    )


def ai_answer_text(reply: str, provider: str) -> str:
    return (
        f"{I.ROBOT} <b>Goii AI</b> {I.SPARKLES}\n"
        f"{I.SOFT_DIVIDER}\n"
        f"{esc(reply.strip())}\n"
        f"{I.SOFT_DIVIDER}\n"
        f"{provider_badge(provider)}"
    )


def recommend_text(reply: str, suggestions: Iterable[str], provider: str) -> str:
    lines = []
    for idx, item in enumerate(suggestions):
        number = NUMBER_ICONS[idx] if idx < len(NUMBER_ICONS) else I.PLAY
        lines.append(f"{number} <code>{esc(safe_trim(item, 70))}</code>")
    choices = "\n".join(lines)
    return (
        f"{I.RAINBOW} <b>Goii AI ရဲ့ အကြံပြုချက်</b> {I.HEADPHONES}\n"
        f"{I.SOFT_DIVIDER}\n"
        f"{esc(reply.strip())}\n"
        f"{I.SOFT_DIVIDER}\n"
        f"{choices}\n"
        f"{I.DOWN} ကြိုက်တာလေး နှိပ်ပြီး ရှာလိုက်ပါနော် 🎵\n"
        f"{provider_badge(provider)}"
    )


STAGE_MESSAGES = (
    f"{I.CLOCK} <b>စီစဉ်နေပါတယ်…</b>",
    f"{I.INBOX} <b>သီချင်းကို ဒေါင်းလုဒ်လုပ်နေပါတယ်…</b> {I.MUSIC}",
    f"{I.UPLOAD} <b>MP3 ပို့ပေးနေပါတယ်…</b> {I.HEADPHONES}",
)


def download_text(stage: int) -> str:
    return STAGE_MESSAGES[max(0, min(stage, len(STAGE_MESSAGES) - 1))]


def caption_text(title: str, performer: str, duration: int = 0) -> str:
    length = fmt_duration(duration)
    duration_line = f"\n{I.CLOCK} {esc(length)}" if length else ""
    return (
        f"{I.MUSIC} <b>{esc(safe_trim(title, 90))}</b>\n"
        f"{I.MIC} {esc(safe_trim(performer or 'Unknown artist', 70))}"
        f"{duration_line}\n"
        f"{I.SOFT_DIVIDER}\n"
        f"{I.CHECK} ရောက်ပါပြီနော် · <b>Goii Music Bot</b> {I.HEADPHONES}"
    )


def error_text(kind: str, detail: str = "") -> str:
    if kind == "search":
        body = "ရှာဖွေမှု အဆင်မပြေဖြစ်နေပါတယ်။ ခဏနေမှ ပြန်စမ်းကြည့်ပါနော်။"
    elif kind == "download":
        body = (
            "သီချင်းကို ပို့လို့ မရသေးပါဘူး။ အရမ်းရှည်တဲ့ သီချင်းဆိုရင် "
            "RAM ပြည့်တတ်ပါတယ်။ ခဏနေမှ ပြန်စမ်းကြည့်ပါနော်။"
        )
    elif kind == "empty":
        body = "ဘာမှ ရိုက်မထားပါဘူး။ သီချင်းအမည်လေး ပြောပေးပါနော် 🎵"
    else:
        body = "တစ်ခုခု မှားသွားပါတယ်။ ခဏနေမှ ပြန်စမ်းကြည့်ပါနော်။"
    debug = f"\n<i>{esc(safe_trim(detail, 110))}</i>" if detail else ""
    return (
        f"{I.CROSS} <b>တောင်းပန်ပါတယ်နော်</b> {I.WARN}\n"
        f"{I.SOFT_DIVIDER}\n"
        f"{body}{debug}"
    )


def prompt_text(kind: str) -> str:
    if kind == "search":
        return (
            f"{I.PENCIL} <b>သီချင်းရှာမယ်</b> {I.SEARCH}\n"
            f"{I.SOFT_DIVIDER}\n"
            f"သီချင်းအမည် (သို့) အဆိုတော်အမည်လေး ရိုက်ပေးပါနော် 🎵"
        )
    return (
        f"{I.ROBOT} <b>AI ကို မေးမယ်</b> {I.BRAIN}\n"
        f"{I.SOFT_DIVIDER}\n"
        f"အဆိုတော်အကြောင်း၊ သီချင်းအကြောင်း၊ ဒါမှမဟုတ် ကြိုက်တဲ့ mood လေး "
        f"ပြောပေးပါနော် ✨\n"
        f"<i>တိုက်ရိုက်မေးချင်ရင် /ai ကိုလည်း သုံးလို့ရပါတယ်။</i>"
    )
