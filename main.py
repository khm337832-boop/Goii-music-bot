"""Goii Music Bot — Telegram music bot with an AI brain and pretty icons.

Flow:
    user message ──> MusicAI.think() ──> search / recommend / info / chat
                                   └──> YouTube results ──> MP3 download

Set BOT_TOKEN to run. Optionally set AI_API_KEY (+ AI_PROVIDER) to give the
bot a real LLM brain; without it the built-in local reasoning engine still
understands Burmese/English requests, moods and typos.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import uuid
from threading import Thread
from urllib.parse import quote

from flask import Flask, jsonify
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ai_brain import MusicAI, build_youtube_query, clean_query
from buttons import (
    BOT_COMMANDS,
    CATEGORIES,
    REPLY_ROWS,
    lookup_quick_search,
    quick_search_callback,
    reply_action,
)
from config import Settings
from icons import (
    I,
    ai_answer_text,
    brain_status_text,
    caption_text,
    download_text,
    error_text,
    esc,
    help_text,
    keyboard_text,
    menu_text,
    no_results_text,
    prompt_text,
    recommend_text,
    results_text,
    safe_trim,
    searching_text,
    thinking_text,
    track_label,
    welcome_text,
)
from music import cleanup_download, download_track, search_tracks

logging.basicConfig(
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("werkzeug").setLevel(logging.WARNING)
LOG = logging.getLogger("goii")

# FFmpeg binary (downloaded once by static-ffmpeg). Failure is not fatal:
# the system ffmpeg from the Render buildpack can still be used.
try:
    from static_ffmpeg import add_paths

    add_paths()
except Exception as exc:  # pragma: no cover - environment dependent
    LOG.warning("static-ffmpeg init skipped: %s", exc)

SETTINGS = Settings.from_env()
brain = MusicAI(SETTINGS)
DOWNLOAD_SEM = asyncio.Semaphore(2)  # protect the free-tier RAM

# ---------------------------------------------------------------------------
# Tiny keep-alive web app (Render free web service needs an open port)
# ---------------------------------------------------------------------------

web = Flask("Goii")

HOME_HTML = """<!doctype html>
<html lang="my"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Goii Music Bot</title>
<style>
  *{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;
  background:radial-gradient(circle at 20% 20%,#2b1b4d,#0d0b1a 60%);color:#f5f3ff;
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
  .card{width:min(420px,90vw);padding:32px;border-radius:24px;text-align:center;
  background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);
  box-shadow:0 20px 60px rgba(0,0,0,.35);backdrop-filter:blur(12px)}
  .logo{font-size:56px;line-height:1}h1{margin:12px 0 6px;font-size:26px}
  p{opacity:.75;line-height:1.7;margin:8px 0 20px}
  .chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center}
  .chip{padding:8px 14px;border-radius:999px;background:rgba(255,255,255,.09);
  border:1px solid rgba(255,255,255,.12);font-size:13px;color:inherit;text-decoration:none}
  a.chip{background:rgba(120,180,255,.18);border-color:rgba(120,180,255,.35)}
  .status{margin-top:22px;font-size:13px;opacity:.65}
</style></head><body><div class="card">
  <div class="logo">🎧</div><h1>Goii Music Bot ✨</h1>
  <p>သီချင်းရှာပေးတဲ့အပြင် စဉ်းစားတတ်တဲ့ AI လည်း ပါပါတယ် 🧠</p>
  <div class="chips"><span class="chip">🎵 Songs</span><span class="chip">🎤 Artists</span>
  <span class="chip">🌈 Moods</span><span class="chip">🤖 AI chat</span>
  __BOT_LINK__</div>
  <div class="status">Bot is alive · AI engine: __ENGINE__</div>
</div></body></html>"""


@web.get("/")
def home() -> str:
    link = SETTINGS.bot_link
    chip = (
        f'<a class="chip" href="{esc(link)}">🔗 Bot link</a>' if link
        else '<span class="chip">🔗 set BOT_USERNAME</span>'
    )
    return HOME_HTML.replace("__ENGINE__", brain.provider).replace("__BOT_LINK__", chip)


@web.get("/health")
def health():
    return jsonify(
        status="ok",
        bot="Goii Music Bot",
        ai_engine=brain.provider,
        cloud_ai=brain.provider != "local",
        bot_link=SETTINGS.bot_link or None,
        bot_id=SETTINGS.bot_id or None,
    )


def keep_alive() -> None:
    def run() -> None:
        web.run(
            host="0.0.0.0",
            port=SETTINGS.port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )

    Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------------------
# Small helpers: conversation memory + short callback tokens
# ---------------------------------------------------------------------------

def get_history(context: ContextTypes.DEFAULT_TYPE) -> list[dict[str, str]]:
    return context.chat_data.setdefault("ai_history", [])


def remember(context: ContextTypes.DEFAULT_TYPE, user_text: str, reply: str) -> None:
    history = get_history(context)
    history.append({"role": "user", "text": user_text[:400]})
    history.append({"role": "assistant", "text": reply[:400]})
    del history[:-8]  # keep the last 4 turns


def put_query(context: ContextTypes.DEFAULT_TYPE, value: str) -> str:
    """Store a long query behind an 8-char callback token (Telegram: 64 bytes)."""
    store = context.bot_data.setdefault("qstore", {})
    now = time.time()
    for token in [k for k, item in store.items() if now - item["ts"] > 3600]:
        store.pop(token, None)
    if len(store) > 150:
        for token in sorted(store, key=lambda k: store[k]["ts"])[:50]:
            store.pop(token, None)
    token = uuid.uuid4().hex[:8]
    store[token] = {"q": value, "ts": now}
    return token


def get_query(context: ContextTypes.DEFAULT_TYPE, token: str) -> str | None:
    item = context.bot_data.get("qstore", {}).get(token)
    return item["q"] if item else None


async def safe_edit(message, text: str, **kwargs) -> None:
    """Edit a message, tolerating 'not modified' and other minor failures."""
    try:
        await message.edit_text(text, **kwargs)
    except Exception as exc:
        if "not modified" in str(exc).lower():
            return
        LOG.warning("edit_text failed (%s), sending a new message", exc)
        try:
            await message.reply_text(text, **kwargs)
        except Exception:
            LOG.exception("reply_text failed too")


# ---------------------------------------------------------------------------
# Keyboards (all icons live in icons.py)
# ---------------------------------------------------------------------------

def main_menu() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(f"{I.SEARCH} သီချင်းရှာမယ်", callback_data="act_search"),
            InlineKeyboardButton(f"{I.FIRE} ပေါ်ပြူလာ", callback_data="act_popular"),
        ],
        [
            InlineKeyboardButton(f"{I.RAINBOW} Mood ရွေးမယ်", callback_data="act_mood"),
            InlineKeyboardButton(f"{I.MIC} အဆိုတော်များ", callback_data="act_artists"),
        ],
        [
            InlineKeyboardButton(f"{I.GUITAR} Genre", callback_data="act_genre"),
            InlineKeyboardButton(f"{I.GLOBE} ဘာသာစကား", callback_data="act_browse"),
        ],
        [
            InlineKeyboardButton(f"{I.ROBOT} AI ကို မေးမယ်", callback_data="act_ai"),
            InlineKeyboardButton(f"{I.INFO} အကူအညီ", callback_data="act_help"),
        ],
        [
            InlineKeyboardButton(f"{I.BRAIN} AI အခြေအနေ", callback_data="act_brain"),
            InlineKeyboardButton(f"{I.LINK} Bot link ပေးပါ", callback_data="act_link"),
        ],
        [InlineKeyboardButton(f"{I.KEYBOARD} အောက်ခလုတ် ဖွင့်မယ်", callback_data="act_keyboard")],
    ]
    link = SETTINGS.bot_link
    if link:  # let users forward the bot to friends with one tap
        share = (
            "https://t.me/share/url?url=" + quote(link, safe="")
            + "&text=" + quote("🎧 Goii Music Bot — သီချင်းရှာပြီး MP3 ပို့ပေးတဲ့ Bot လေး စမ်းကြည့်ပါ 🎵")
        )
        rows.append([InlineKeyboardButton(f"{I.SHARE} သူငယ်ချင်းတွေကို မျှဝေမယ်", url=share)])
    return InlineKeyboardMarkup(rows)


def reply_keyboard() -> ReplyKeyboardMarkup:
    """Persistent bottom keyboard (⌨️) — labels come from ``buttons.py``.

    Telegram sends the tapped label as a normal message, which
    :func:`handle_text` routes via :func:`buttons.reply_action`.
    """
    return ReplyKeyboardMarkup(
        [[KeyboardButton(label) for label in row] for row in REPLY_ROWS],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="သီချင်းအမည် ရိုက်ပါ (သို့) ခလုတ်နှိပ်ပါ 🎵",
    )


#: Inline-menu callback -> category name in ``buttons.CATEGORIES``.
CATEGORY_CALLBACKS = {
    "act_popular": "popular",
    "act_mood": "mood",
    "act_genre": "genre",
    "act_browse": "browse",
    "act_artists": "artists",
    "act_artists_mm": "artists_mm",
    "act_artists_int": "artists_int",
}


def category_keyboard(category: str) -> InlineKeyboardMarkup:
    """Two-column grid of one-tap quick-search buttons for a category."""
    items = CATEGORIES.get(category, ())
    rows = [
        [
            InlineKeyboardButton(item.label, callback_data=quick_search_callback(category, item.key))
            for item in items[start:start + 2]
        ]
        for start in range(0, len(items), 2)
    ]
    if category in {"artists_mm", "artists_int"}:
        rows.append([
            InlineKeyboardButton(f"{I.BACK} အဆိုတော်မီနူး", callback_data="act_artists"),
            InlineKeyboardButton(f"{I.HOME} မီနူး", callback_data="act_menu"),
        ])
    else:
        rows.append([
            InlineKeyboardButton(f"{I.HOME} မီနူး ပြန်သွားမယ်", callback_data="act_menu"),
            InlineKeyboardButton(f"{I.SEARCH} ကိုယ်တိုင်ရှာမယ်", callback_data="act_search"),
        ])
    return InlineKeyboardMarkup(rows)


def artists_hub_keyboard() -> InlineKeyboardMarkup:
    """🇲🇲 / 🌍 chooser shown before the actual artist grids."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{I.FLAG_MM} မြန်မာ အဆိုတော်များ", callback_data="act_artists_mm")],
        [InlineKeyboardButton(f"{I.GLOBE} International Artists", callback_data="act_artists_int")],
        [InlineKeyboardButton(f"{I.BACK} မီနူး ပြန်သွားမယ်", callback_data="act_menu")],
    ])


def category_payload(category: str) -> tuple[str, InlineKeyboardMarkup]:
    """(heading text, keyboard) for a category menu."""
    if category == "artists":
        return menu_text("artists"), artists_hub_keyboard()
    return menu_text(category), category_keyboard(category)


def after_download_keyboard() -> InlineKeyboardMarkup:
    """Buttons attached under every delivered MP3."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{I.REFRESH} ဒီလို နောက်တစ်ပုဒ်", callback_data="act_more_like"),
            InlineKeyboardButton(f"{I.SEARCH} အသစ်ရှာမယ်", callback_data="act_search"),
        ],
        [
            InlineKeyboardButton(f"{I.FIRE} ပေါ်ပြူလာ", callback_data="act_popular"),
            InlineKeyboardButton(f"{I.RAINBOW} Mood", callback_data="act_mood"),
        ],
        [InlineKeyboardButton(f"{I.HOME} မီနူး ပြန်သွားမယ်", callback_data="act_menu")],
    ])


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"{I.BACK} မီနူး ပြန်သွားမယ်", callback_data="act_menu")
    ]])


def results_keyboard(context, tracks, query: str, page: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(track_label(i, t.title, t.duration), callback_data=f"dl_{t.id}")]
        for i, t in enumerate(tracks)
    ]
    token = put_query(context, query)
    rows.append([
        InlineKeyboardButton(f"{I.REFRESH} နောက်ထပ် ရလဒ်များ", callback_data=f"sq_{token}_{page + 1}"),
        InlineKeyboardButton(f"{I.ROBOT} ဒီအကြောင်း မေးမယ်", callback_data=f"ask_{token}"),
    ])
    rows.append([
        InlineKeyboardButton(f"{I.FIRE} ပေါ်ပြူလာ", callback_data="act_popular"),
        InlineKeyboardButton(f"{I.HOME} မီနူး", callback_data="act_menu"),
    ])
    return InlineKeyboardMarkup(rows)


def suggestion_keyboard(context, suggestions: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for i, suggestion in enumerate(suggestions[:3]):
        number = ("1️⃣", "2️⃣", "3️⃣")[i]
        token = put_query(context, suggestion)
        rows.append([InlineKeyboardButton(
            f"{number} {I.PLAY} {safe_trim(suggestion, 34)}", callback_data=f"sr_{token}"
        )])
    rows.append([InlineKeyboardButton(f"{I.BACK} မီနူး ပြန်သွားမယ်", callback_data="act_menu")])
    return InlineKeyboardMarkup(rows)


def answer_keyboard(context, result) -> InlineKeyboardMarkup:
    rows = []
    if result.search_query:
        token = put_query(context, result.search_query)
        rows.append([InlineKeyboardButton(
            f"{I.SEARCH} {safe_trim(result.search_query, 34)} ကို ရှာမယ်",
            callback_data=f"sr_{token}",
        )])
    rows.append([InlineKeyboardButton(f"{I.BACK} မီနူး ပြန်သွားမယ်", callback_data="act_menu")])
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

async def show_results(message, context, query: str, page: int = 0) -> None:
    """Search YouTube and replace `message` with a nicely formatted result list."""
    # Remembered so the "🔄 ဒီလို နောက်တစ်ပုဒ်" button under a downloaded
    # MP3 can fetch the next page of the same search.
    context.chat_data["last_query"] = query
    context.chat_data["last_page"] = page
    yt_query = build_youtube_query(query, page)
    await safe_edit(message, searching_text(query), parse_mode="HTML")

    tracks = []
    try:
        tracks = await search_tracks(yt_query, SETTINGS.max_results)
    except Exception as exc:
        LOG.warning("Search failed for %r: %s", yt_query, exc)

    # If the AI flavoured query is too specific, fall back to the plain one.
    if not tracks and yt_query != query:
        try:
            tracks = await search_tracks(query, SETTINGS.max_results)
        except Exception as exc:
            LOG.warning("Fallback search failed: %s", exc)

    if not tracks:
        await safe_edit(
            message,
            no_results_text(query, brain.provider),
            parse_mode="HTML",
            reply_markup=back_keyboard(),
            disable_web_page_preview=True,
        )
        return

    await safe_edit(
        message,
        results_text(query, len(tracks), brain.provider, page),
        parse_mode="HTML",
        reply_markup=results_keyboard(context, tracks, query, page),
        disable_web_page_preview=True,
    )


async def route_result(message, context, result, original: str) -> None:
    if result.wants_search:
        await show_results(message, context, result.search_query)
        remember(context, original, f"🔎 {result.search_query} အတွက် ရလဒ်တွေ ပြပေးလိုက်ပါတယ်။")
        return

    if result.intent == "recommend":
        text = recommend_text(result.reply or "ဒီလိုလေးတွေ နားထောင်ကြည့်ပါနော် 🎶", result.suggestions, result.source)
        keyboard = suggestion_keyboard(context, result.suggestions)
    else:
        text = ai_answer_text(result.reply or "နားလည်သွားပါပြီနော် ✨", result.source)
        keyboard = answer_keyboard(context, result)

    await safe_edit(message, text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
    remember(context, original, result.reply or "")


# ---------------------------------------------------------------------------
# Command / message handlers
# ---------------------------------------------------------------------------

async def send_welcome(message, *, with_keyboard: bool = False) -> None:
    """Welcome card + inline main menu; optionally (re)install the ⌨️ keyboard.

    A Telegram message can carry only one ``reply_markup``, so the persistent
    bottom keyboard arrives as its own short second message.
    """
    await message.reply_text(
        welcome_text(), parse_mode="HTML", reply_markup=main_menu(), disable_web_page_preview=True
    )
    if with_keyboard:
        await message.reply_text(
            keyboard_text(), parse_mode="HTML", reply_markup=reply_keyboard(),
            disable_web_page_preview=True,
        )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_welcome(update.message, with_keyboard=True)


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_welcome(update.message)


async def cmd_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the persistent bottom button keyboard again."""
    await update.message.reply_text(
        keyboard_text(), parse_mode="HTML", reply_markup=reply_keyboard(),
        disable_web_page_preview=True,
    )


async def send_category(message, category: str) -> None:
    """Send a category button menu as a new message."""
    text, keyboard = category_payload(category)
    await message.reply_text(
        text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True
    )


def category_command(category: str):
    """Build a /popular, /mood, ... handler that opens a category menu."""

    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await send_category(update.message, category)

    handler.__name__ = f"cmd_{category}"
    return handler


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        help_text(brain.provider), parse_mode="HTML", reply_markup=back_keyboard(),
        disable_web_page_preview=True,
    )


async def cmd_brain(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        brain_status_text(brain.provider, brain.has_key, brain.status_model()),
        parse_mode="HTML", reply_markup=back_keyboard(), disable_web_page_preview=True,
    )


def link_payload() -> tuple[str, InlineKeyboardMarkup]:
    """(text, keyboard) for the public t.me link card (/link and 🔗 button)."""
    link = SETTINGS.bot_link
    if link:
        text = (
            f"{I.LINK} <b>Goii Music Bot</b> {I.HEADPHONES}\n"
            f"{I.SOFT_DIVIDER}\n"
            f"🔗 <code>{esc(link)}</code>\n\n"
            f"မိတ်ဆွေတွေကို မျှဝေလို့ရပါတယ်နော် 💌"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"{I.BOT} Bot ကို ဖွင့်မယ်", url=link),
            InlineKeyboardButton(f"{I.BACK} မီနူး", callback_data="act_menu"),
        ]])
        return text, keyboard
    hint = f" <code>{SETTINGS.bot_id}</code>" if SETTINGS.bot_id else ""
    text = (
        f"{I.WARN} <b>Bot link မရသေးပါဘူး</b>\n"
        f"{I.SOFT_DIVIDER}\n"
        f"Bot link က <code>https://t.me/&lt;username&gt;</code> ပုံစံဖြစ်ပါတယ်။ "
        f"@BotFather → <code>/mybots</code> → ကိုယ့် bot → <b>Bot Settings → Username</b> "
        f"ထဲက username ကို <code>BOT_USERNAME</code> အနေနဲ့ ထည့်ပေးပါနော် 🔑\n"
        f"Bot ID:{hint}"
    )
    return text, back_keyboard()


async def cmd_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Share the public t.me link for this bot."""
    text, keyboard = link_payload()
    await update.message.reply_text(
        text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True
    )


async def cmd_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Force an AI answer instead of a search."""
    question = " ".join(context.args or []).strip()
    if not question:
        await update.message.reply_text(
            prompt_text("ai"), parse_mode="HTML", reply_markup=back_keyboard(),
            disable_web_page_preview=True,
        )
        return
    thinking = await update.message.reply_text(thinking_text(), parse_mode="HTML")
    result = await brain.think(question, get_history(context), force_chat=True)
    if result.intent == "search":  # /ai always answers, but keep the play button
        result.intent = "info"
        result.reply = result.reply or f"«{result.search_query}» အကြောင်း ရှာပေးလိုက်ပါတယ်နော် 🎧"
    await route_result(thinking, context, result, question)


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fast direct search (no LLM round-trip)."""
    query = " ".join(context.args or []).strip()
    if not query:
        await update.message.reply_text(
            prompt_text("search"), parse_mode="HTML", reply_markup=back_keyboard(),
            disable_web_page_preview=True,
        )
        return
    thinking = await update.message.reply_text(thinking_text(), parse_mode="HTML")
    await show_results(thinking, context, clean_query(query) or query)


async def handle_reply_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    """Route a ⌨️ bottom-keyboard tap (it arrives as the button's label text)."""
    message = update.message
    if action in CATEGORIES or action == "artists":
        await send_category(message, action)
    elif action == "search":
        await message.reply_text(
            prompt_text("search"), parse_mode="HTML", reply_markup=back_keyboard(),
            disable_web_page_preview=True,
        )
    elif action == "ai":
        await message.reply_text(
            prompt_text("ai"), parse_mode="HTML", reply_markup=back_keyboard(),
            disable_web_page_preview=True,
        )
    elif action == "help":
        await cmd_help(update, context)
    elif action == "menu":
        await send_welcome(message)
    else:  # pragma: no cover - REPLY_ACTIONS only yields the actions above
        await send_welcome(message)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bottom-keyboard taps are routed instantly; everything else hits the AI."""
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text(error_text("empty"), parse_mode="HTML")
        return
    action = reply_action(text)
    if action:
        await handle_reply_action(update, context, action)
        return
    thinking = await update.message.reply_text(thinking_text(), parse_mode="HTML")
    result = await brain.think(text, get_history(context))
    await route_result(thinking, context, result, text)


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    callback = update.callback_query
    data = callback.data or ""
    await callback.answer()
    message = callback.message

    if data.startswith("dl_"):
        await handle_download(callback, context)
        return

    if data.startswith("qs_"):  # one-tap category button (mood / artist / ...)
        item = lookup_quick_search(data)
        if not item:
            await safe_edit(message, error_text("generic", "ခလုတ်က သက်တမ်းကုန်သွားပါပြီ။"), parse_mode="HTML", reply_markup=back_keyboard())
            return
        await show_results(message, context, item.query)
        return

    if data in CATEGORY_CALLBACKS:  # open a category button menu
        text, keyboard = category_payload(CATEGORY_CALLBACKS[data])
        await safe_edit(message, text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
        return

    if data.startswith("sr_") or data.startswith("ask_"):
        stored = get_query(context, data.split("_", 1)[1])
        if not stored:
            await safe_edit(message, error_text("generic", "ခလုတ်က သက်တမ်းကုန်သွားပါပြီ။"), parse_mode="HTML", reply_markup=back_keyboard())
            return
        if data.startswith("sr_"):
            await show_results(message, context, stored)
        else:
            await safe_edit(message, thinking_text(), parse_mode="HTML")
            result = await brain.think(
                f"«{stored}» အကြောင်း ပြောပြပါ။ အဆိုတော်၊ သီချင်းနဲ့ ဆိုင်တဲ့ ဗဟုသုသုတလေးတွေ ရှင်းပြပေးပါ။",
                get_history(context), force_chat=True,
            )
            if result.intent == "search":
                result.intent = "info"
            await safe_edit(
                message, ai_answer_text(result.reply or "ပြောပြစရာလေး ရှာမတွေ့သေးပါဘူးနော 🙈", result.source),
                parse_mode="HTML", reply_markup=answer_keyboard(context, result),
                disable_web_page_preview=True,
            )
            remember(context, stored, result.reply or "")
        return

    match = re.fullmatch(r"sq_([a-f0-9]{8})_(\d+)", data)
    if match:
        stored = get_query(context, match.group(1))
        page = int(match.group(2))
        if stored:
            await show_results(message, context, stored, page)
        else:
            await safe_edit(message, error_text("generic", "ခလုတ်က သက်တမ်းကုန်သွားပါပြီ။"), parse_mode="HTML", reply_markup=back_keyboard())
        return

    if data == "act_menu":
        await safe_edit(message, welcome_text(), parse_mode="HTML", reply_markup=main_menu(), disable_web_page_preview=True)
    elif data == "act_help":
        await safe_edit(message, help_text(brain.provider), parse_mode="HTML", reply_markup=back_keyboard(), disable_web_page_preview=True)
    elif data == "act_brain":
        await safe_edit(message, brain_status_text(brain.provider, brain.has_key, brain.status_model()), parse_mode="HTML", reply_markup=back_keyboard(), disable_web_page_preview=True)
    elif data == "act_search":
        await safe_edit(message, prompt_text("search"), parse_mode="HTML", reply_markup=back_keyboard(), disable_web_page_preview=True)
    elif data == "act_ai":
        await safe_edit(message, prompt_text("ai"), parse_mode="HTML", reply_markup=back_keyboard(), disable_web_page_preview=True)
    elif data == "act_link":
        text, kb = link_payload()
        await safe_edit(message, text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    elif data == "act_keyboard":
        # A reply keyboard cannot be attached by editing — send a new message.
        await message.reply_text(
            keyboard_text(), parse_mode="HTML", reply_markup=reply_keyboard(),
            disable_web_page_preview=True,
        )
    elif data == "act_more_like":
        # "🔄 ဒီလို နောက်တစ်ပုဒ်" under a downloaded MP3: next page of the
        # same search. A fresh status message is used because the button may
        # sit on an audio message, which cannot be edited into a result list.
        last_query = context.chat_data.get("last_query")
        if last_query:
            status = await message.reply_text(thinking_text(), parse_mode="HTML")
            await show_results(status, context, last_query, int(context.chat_data.get("last_page", 0)) + 1)
        else:
            text, kb = category_payload("popular")
            await safe_edit(message, text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)


async def handle_download(callback, context: ContextTypes.DEFAULT_TYPE) -> None:
    video_id = (callback.data or "")[3:]
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
        await safe_edit(callback.message, error_text("download"), parse_mode="HTML")
        return

    status = await callback.message.reply_text(download_text(0), parse_mode="HTML")
    try:
        async with DOWNLOAD_SEM:
            await safe_edit(status, download_text(1), parse_mode="HTML")
            path, meta = await download_track(video_id, SETTINGS)

            if os.path.getsize(path) > 49 * 1024 * 1024:
                raise RuntimeError("file too large for Telegram")

            await safe_edit(status, download_text(2), parse_mode="HTML")
            try:
                await context.bot.send_chat_action(callback.message.chat_id, ChatAction.UPLOAD_DOCUMENT)
            except Exception:
                pass

            kwargs = {
                "title": meta["title"][:64],
                "performer": meta["performer"][:64],
                "caption": caption_text(meta["title"], meta["performer"], meta["duration"]),
                "parse_mode": "HTML",
                "reply_to_message_id": callback.message.message_id,
                "reply_markup": after_download_keyboard(),
            }
            if meta["duration"] > 0:
                kwargs["duration"] = meta["duration"]
            with open(path, "rb") as audio:
                await context.bot.send_audio(chat_id=callback.message.chat_id, audio=audio, **kwargs)
        await status.delete()
    except Exception as exc:
        LOG.exception("Download failed for %s", video_id)
        await safe_edit(status, error_text("download", str(exc)), parse_mode="HTML")
    finally:
        cleanup_download(video_id, SETTINGS)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOG.error("Unhandled error: %s", context.error, exc_info=context.error)


# ---------------------------------------------------------------------------

async def post_init(application: Application) -> None:
    """Register the "/" command-menu button next to the message input."""
    try:
        await application.bot.set_my_commands(
            [BotCommand(command, description) for command, description in BOT_COMMANDS]
        )
        LOG.info("📋 Bot command menu registered (%d commands)", len(BOT_COMMANDS))
    except Exception as exc:  # the bot still works without the menu button
        LOG.warning("set_my_commands failed: %s", exc)


def main() -> None:
    if not SETTINGS.bot_token:
        raise SystemExit(
            "❌ BOT_TOKEN မသတ်မှတ်ထားပါဘူး။ "
            "Render dashboard (သို့) .env ထဲမှာ BOT_TOKEN ထည့်ပေးပါနော်."
        )
    os.makedirs(SETTINGS.download_dir, exist_ok=True)
    keep_alive()

    application = (
        Application.builder()
        .token(SETTINGS.bot_token)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(60)
        .post_init(post_init)
        .build()
    )
    application.add_handler(CommandHandler(["start", "home"], cmd_start))
    application.add_handler(CommandHandler("menu", cmd_menu))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("ai", cmd_ai))
    application.add_handler(CommandHandler("search", cmd_search))
    application.add_handler(CommandHandler("brain", cmd_brain))
    application.add_handler(CommandHandler("link", cmd_link))
    application.add_handler(CommandHandler("keyboard", cmd_keyboard))
    application.add_handler(CommandHandler("popular", category_command("popular")))
    application.add_handler(CommandHandler(["mood", "moods"], category_command("mood")))
    application.add_handler(CommandHandler(["genre", "genres"], category_command("genre")))
    application.add_handler(CommandHandler("artists", category_command("artists")))
    application.add_handler(CommandHandler("browse", category_command("browse")))
    application.add_handler(CallbackQueryHandler(on_button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_error_handler(on_error)

    LOG.info("🎧 Goii Music Bot starting | AI engine: %s", brain.provider)
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
