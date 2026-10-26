"""Button catalogue for Goii Music Bot — every tappable label lives here.

This module is deliberately *dependency-free* (no Telegram imports) so the
button layout can be unit-tested without a bot token or network.  ``main.py``
turns this data into real Telegram keyboards:

* :data:`REPLY_ROWS`      -> the persistent bottom keyboard (⌨️ အောက်ခလုတ်တွေ)
* :data:`CATEGORIES`      -> inline menus: mood / genre / artists / browse /
                             popular — one tap starts a search
* :data:`BOT_COMMANDS`    -> the "/" command-menu button next to the input box

To restyle or extend the buttons, edit the tuples below — nothing else needs
to change.  Keep ``key`` values short ASCII: they become Telegram callback
data (max 64 bytes).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class QuickSearch:
    """One inline category button: tapping it searches ``query`` at once."""

    key: str    # short ASCII id, unique inside its category
    label: str  # text shown on the button
    query: str  # YouTube search query used when tapped


# ---------------------------------------------------------------------------
# 🌈 Mood buttons
# ---------------------------------------------------------------------------

MOODS: tuple[QuickSearch, ...] = (
    QuickSearch("happy", "😊 ပျော်ရွှင် Happy", "feel good happy songs"),
    QuickSearch("sad", "😢 အလွမ်း Sad", "sad heartbreak songs"),
    QuickSearch("love", "❤️ အချစ် Love", "romantic love songs"),
    QuickSearch("chill", "😌 အေးဆေး Chill", "chill lofi songs"),
    QuickSearch("party", "🎉 Party", "party dance songs hits"),
    QuickSearch("workout", "💪 Workout", "workout motivation songs"),
    QuickSearch("rain", "🌧️ မိုးသီချင်း", "မြန်မာ မိုးသီချင်းများ"),
    QuickSearch("sleep", "🌙 အိပ်ယာဝင် Sleep", "soft acoustic sleep songs"),
)

# ---------------------------------------------------------------------------
# 🎸 Genre buttons
# ---------------------------------------------------------------------------

GENRES: tuple[QuickSearch, ...] = (
    QuickSearch("pop", "🎤 Pop", "top pop songs"),
    QuickSearch("rock", "🎸 Rock", "best rock songs"),
    QuickSearch("hiphop", "🎙️ Hip-Hop", "hip hop rap songs"),
    QuickSearch("lofi", "🌃 Lo-fi", "lofi songs"),
    QuickSearch("edm", "⚡ EDM", "EDM dance songs"),
    QuickSearch("acoustic", "🪕 Acoustic", "acoustic songs covers"),
    QuickSearch("rnb", "💜 R&B", "R&B soul songs"),
    QuickSearch("kpop", "🇰🇷 K-Pop", "K-pop hits songs"),
)

# ---------------------------------------------------------------------------
# 🎤 Artist buttons
# ---------------------------------------------------------------------------

ARTISTS_MM: tuple[QuickSearch, ...] = (
    QuickSearch("sai_htee_saing", "စိုင်းထီးဆိုင်", "စိုင်းထီးဆိုင်"),
    QuickSearch("htoo_eain_thin", "ထူးအိမ်သင်", "ထူးအိမ်သင်"),
    QuickSearch("lay_phyu", "လေးဖြူ", "လေးဖြူ"),
    QuickSearch("myo_gyi", "မျိုးကြီး", "မျိုးကြီး"),
    QuickSearch("sai_sai", "စိုင်းစိုင်းခမ်းလှိုင်", "စိုင်းစိုင်းခမ်းလှိုင်"),
    QuickSearch("zaw_win_htut", "ဇော်ဝင်းထွဋ်", "ဇော်ဝင်းထွဋ်"),
    QuickSearch("ni_ni_khin_zaw", "နီနီခင်ဇော်", "နီနီခင်ဇော်"),
    QuickSearch("wai_la", "ဝေလ", "ဝေလ သီချင်း"),
)

ARTISTS_INT: tuple[QuickSearch, ...] = (
    QuickSearch("taylor_swift", "Taylor Swift", "Taylor Swift"),
    QuickSearch("ed_sheeran", "Ed Sheeran", "Ed Sheeran"),
    QuickSearch("coldplay", "Coldplay", "Coldplay"),
    QuickSearch("billie_eilish", "Billie Eilish", "Billie Eilish"),
    QuickSearch("eminem", "Eminem", "Eminem"),
    QuickSearch("adele", "Adele", "Adele"),
    QuickSearch("bts", "BTS", "BTS"),
    QuickSearch("blackpink", "BLACKPINK", "BLACKPINK"),
)

# ---------------------------------------------------------------------------
# 🌍 Browse by language / kind
# ---------------------------------------------------------------------------

BROWSE: tuple[QuickSearch, ...] = (
    QuickSearch("mm", "🇲🇲 မြန်မာသီချင်း", "မြန်မာသီချင်းများ"),
    QuickSearch("mm_new", "🆕 မြန်မာ အသစ်", "မြန်မာ သီချင်းအသစ်များ"),
    QuickSearch("mm_oldies", "📼 မြန်မာ သီချင်းဟောင်း", "မြန်မာ သီချင်းဟောင်းများ"),
    QuickSearch("en", "🇬🇧 English", "english songs hits"),
    QuickSearch("thai", "🇹🇭 ထိုင်းသီချင်း", "thai songs hits"),
    QuickSearch("hindi", "🇮🇳 Bollywood", "bollywood hindi songs"),
    QuickSearch("oldies", "📻 Oldies", "classic oldies songs"),
    QuickSearch("cover", "🎤 Cover Songs", "best acoustic cover songs"),
)

# ---------------------------------------------------------------------------
# 🔥 Popular / trending
# ---------------------------------------------------------------------------

POPULAR: tuple[QuickSearch, ...] = (
    QuickSearch("trending", "🔥 Trending", "trending songs hits"),
    QuickSearch("top", "📈 Top Hits", "top hits songs"),
    QuickSearch("viral", "📱 TikTok Viral", "viral tiktok songs"),
    QuickSearch("new", "🆕 New Songs", "new release songs hits"),
    QuickSearch("mm_hot", "🇲🇲 မြန်မာ ပေါက်သီချင်း", "မြန်မာ ပေါက်သီချင်းများ"),
    QuickSearch("alltime", "⭐ All-Time Best", "best songs of all time"),
)

#: Every inline category menu, keyed by its short name.  The ``artists`` menu
#: itself is a hub (🇲🇲 / 🌍) so it is built separately in ``main.py``.
CATEGORIES: dict[str, tuple[QuickSearch, ...]] = {
    "mood": MOODS,
    "genre": GENRES,
    "artists_mm": ARTISTS_MM,
    "artists_int": ARTISTS_INT,
    "browse": BROWSE,
    "popular": POPULAR,
}

# ---------------------------------------------------------------------------
# Callback-data helpers (Telegram allows at most 64 bytes)
# ---------------------------------------------------------------------------

_CALLBACK_PREFIX = "qs_"


def quick_search_callback(category: str, key: str) -> str:
    """Build callback data for one quick-search button, e.g. ``qs_mood:sad``."""
    return f"{_CALLBACK_PREFIX}{category}:{key}"


def lookup_quick_search(callback_data: str) -> QuickSearch | None:
    """Resolve callback data back to its :class:`QuickSearch` (or ``None``)."""
    if not callback_data or not callback_data.startswith(_CALLBACK_PREFIX):
        return None
    category, _, key = callback_data[len(_CALLBACK_PREFIX):].partition(":")
    for item in CATEGORIES.get(category, ()):
        if item.key == key:
            return item
    return None


def iter_quick_searches() -> list[tuple[str, QuickSearch]]:
    """All ``(category, button)`` pairs — handy for tests and the preview."""
    return [(category, item) for category, items in CATEGORIES.items() for item in items]


# ---------------------------------------------------------------------------
# ⌨️ Bottom reply keyboard (always visible under the chat input)
#
# Telegram sends the button's exact label as a normal message when tapped, so
# ``main.py`` matches incoming text with :func:`reply_action` before the AI
# brain ever sees it.
# ---------------------------------------------------------------------------

class R:
    """Reply-keyboard labels. Change a label here and routing follows."""

    SEARCH = "🔎 သီချင်းရှာမယ်"
    POPULAR = "🔥 ပေါ်ပြူလာ"
    MOOD = "🌈 Mood ရွေးမယ်"
    ARTISTS = "🎤 အဆိုတော်များ"
    GENRE = "🎸 Genre ရွေးမယ်"
    BROWSE = "🌍 ဘာသာစကား ရွေးမယ်"
    AI = "🤖 AI ကို မေးမယ်"
    HELP = "ℹ️ အကူအညီ"
    MENU = "🏠 မူလမီနူး"


#: Row layout of the persistent bottom keyboard.
REPLY_ROWS: tuple[tuple[str, ...], ...] = (
    (R.SEARCH, R.POPULAR),
    (R.MOOD, R.ARTISTS),
    (R.GENRE, R.BROWSE),
    (R.AI, R.HELP),
    (R.MENU,),
)

#: Label -> action name understood by ``main.handle_reply_action``.
REPLY_ACTIONS: dict[str, str] = {
    R.SEARCH: "search",
    R.POPULAR: "popular",
    R.MOOD: "mood",
    R.ARTISTS: "artists",
    R.GENRE: "genre",
    R.BROWSE: "browse",
    R.AI: "ai",
    R.HELP: "help",
    R.MENU: "menu",
}


def _normalise_label(text: str) -> str:
    """Make label matching tolerant of spacing / emoji variation selectors.

    Some keyboards drop the U+FE0F variation selector (``ℹ️`` -> ``ℹ``), which
    would otherwise make an exact-match lookup silently fail.
    """
    value = unicodedata.normalize("NFC", text or "").replace("\ufe0f", "")
    return re.sub(r"\s+", " ", value).strip()


_NORMALISED_ACTIONS: dict[str, str] = {
    _normalise_label(label): action for label, action in REPLY_ACTIONS.items()
}


def reply_action(text: str) -> str | None:
    """Return the action for a bottom-keyboard tap, or ``None`` for free text."""
    return _NORMALISED_ACTIONS.get(_normalise_label(text))


# ---------------------------------------------------------------------------
# 📋 Bot command menu (the "/" button beside the message input)
# ---------------------------------------------------------------------------

#: (command, short description) pairs registered with ``set_my_commands``.
BOT_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "🏠 မူလမီနူး ဖွင့်မယ် · Main menu"),
    ("search", "🔎 သီချင်းရှာမယ် · Search a song"),
    ("ai", "🤖 AI ကို မေးမယ် · Ask the AI"),
    ("popular", "🔥 ပေါ်ပြူလာ သီချင်းများ · Trending"),
    ("mood", "🌈 Mood အလိုက် ရွေးမယ် · By mood"),
    ("artists", "🎤 အဆိုတော်အလိုက် ရှာမယ် · By artist"),
    ("genre", "🎸 Genre ရွေးမယ် · By genre"),
    ("browse", "🌍 ဘာသာစကား ရွေးမယ် · By language"),
    ("keyboard", "⌨️ အောက်ခလုတ်တွေ ပြန်ဖွင့်မယ် · Buttons"),
    ("brain", "🧠 AI အခြေအနေ · AI status"),
    ("link", "🔗 Bot link ရယူမယ် · Bot link"),
    ("help", "ℹ️ အကူအညီ · Help"),
    ("menu", "🏠 မီနူး · Menu"),
)
