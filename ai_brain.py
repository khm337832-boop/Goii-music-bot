"""Goii AI brain — understands songs / artists beyond a fixed dataset.

Two layers
----------
1. **Cloud LLM** (Gemini, Groq, OpenAI, OpenRouter or any OpenAI-compatible
   endpoint): real reasoning about artists, songs, moods and free-form
   questions. Optional — enable it with one API key.
2. **Local reasoning engine** (no key, no network): cleans Burmese/English
   requests, detects moods & questions, fixes common artist misspellings and
   always produces a useful, structured answer.

Every LLM error (missing key, timeout, 404 model, quota, bad JSON...) falls
back to the local engine, so the bot never gets stuck. No extra pip packages
are needed — HTTP calls use the standard library inside a worker thread.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import Any, Iterable

from config import Settings

LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are "Goii AI", the music brain of a Telegram music bot called Goii Music Bot.
Users write in Burmese (Myanmar), English, or romanized Burmese. They may use slang, typos,
very short hints ("that sad song", "Sai Htee Saing ရဲ့ မိုးသီချင်း"), or describe a mood
instead of naming a song. Your job is to THINK about what they really want, using your own
general knowledge about music and artists — you are NOT limited to a fixed database.

Reply with EXACTLY ONE JSON object, no markdown, no code fences, no extra text:
{
  "intent": "search" | "recommend" | "info" | "chat",
  "search_query": "best short YouTube search query, or empty string",
  "artist": "guessed artist name or empty string",
  "song": "guessed song title or empty string",
  "reply": "short friendly Burmese answer, max 3 sentences, max 1-2 emojis",
  "suggestions": ["up to 3 short playable search queries"]
}

Intent rules:
- "search": user gives a song/artist name, a lyric fragment, or clearly wants a specific track.
  Put a clean, highly searchable query in search_query. Prefer Latin transliteration for
  Myanmar artist/song names when you are confident, and keep the original script when not.
  Remove polite fillers ("ပေးပါ", "ဖွင့်ပေး", "please play") and fix obvious typos.
  For a specific song add "official audio" only if it helps; never invent a song title.
- "recommend": user describes a mood, a situation, a genre, or asks for suggestions.
  Give 3 DIFFERENT suggestions (genuine well-known songs/artists or clear search queries)
  and put the best one in search_query. Write a warm Burmese reply.
- "info": user asks a QUESTION about an artist, a song, lyrics meaning, genre, history, etc.
  Answer it in `reply` using your knowledge. Be honest when unsure; never fabricate facts.
  Set search_query to a relevant artist/song name so the bot can offer a play button.
- "chat": greetings, thanks, small talk. Just reply warmly and briefly.

Other rules:
- Plain text only inside `reply` (no markdown, no asterisks, no backticks).
- Keep `reply` under 400 characters. Keep every suggestion under 60 characters.
- If the message is ambiguous, prefer "search" and make the query as sensible as possible.
- Use the previous conversation (if given) to resolve follow-ups like "နောက်တစ်ပုဒ်",
  "ဒီအဆိုတော်က", "another one", "who is he".
- Never claim you played or downloaded a song; the bot does that separately.
"""

VALID_INTENTS = {"search", "recommend", "info", "chat"}
INTENT_ALIASES = {
    "play": "search", "find": "search", "song": "search", "download": "search",
    "search_song": "search", "music": "search",
    "recommendation": "recommend", "suggest": "recommend", "suggestions": "recommend",
    "mood": "recommend", "discover": "recommend",
    "question": "info", "knowledge": "info", "artist_info": "info", "explain": "info",
    "greeting": "chat", "smalltalk": "chat", "small_talk": "chat", "thanks": "chat",
}

# ---------------------------------------------------------------------------
# Provider endpoints / models (all overridable with env vars)
# ---------------------------------------------------------------------------

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CHAT_ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
}

# Model IDs change over time: try a chain, and users can pin one with AI_MODEL.
GEMINI_MODELS = ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite")
CHAT_MODELS = {
    "openai": ("gpt-4o-mini",),
    "groq": ("openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile"),
    "openrouter": ("meta-llama/llama-3.3-70b-instruct:free", "openai/gpt-oss-20b:free"),
    "custom": (),
}


class LLMHTTPError(Exception):
    """HTTP error from an LLM endpoint (status + short body)."""

    def __init__(self, status: int, body: str = ""):
        super().__init__(f"LLM HTTP {status}: {body[:200]}")
        self.status = status
        self.body = body


class LLMModelUnavailable(LLMHTTPError):
    """The requested model ID is not served (404/400) — try the next one."""


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict:
    """Blocking JSON POST using only the standard library."""
    import urllib.error
    import urllib.request

    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        if exc.code in (400, 404) and any(
            word in detail.lower() for word in ("model", "not found", "not supported", "unknown")
        ):
            raise LLMModelUnavailable(exc.code, detail) from exc
        raise LLMHTTPError(exc.code, detail) from exc


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class AIResult:
    """Structured decision made by the brain."""

    intent: str = "search"
    search_query: str = ""
    reply: str = ""
    artist: str = ""
    song: str = ""
    suggestions: list[str] = field(default_factory=list)
    source: str = "local"
    note: str = ""

    @property
    def wants_search(self) -> bool:
        return self.intent == "search" and bool(self.search_query)

    @classmethod
    def from_llm(cls, data: dict, source: str, fallback_query: str) -> "AIResult":
        intent = str(data.get("intent") or "search").strip().lower().replace(" ", "_")
        intent = INTENT_ALIASES.get(intent, intent)
        if intent not in VALID_INTENTS:
            intent = "search"

        query = _clean(str(data.get("search_query") or ""), 120)
        if intent == "search" and not query:
            query = _clean(fallback_query, 120)

        suggestions = [
            _clean(str(item), 70)
            for item in (data.get("suggestions") or [])[:3]
            if str(item).strip()
        ]
        suggestions = [item for item in suggestions if item][:3]

        return cls(
            intent=intent,
            search_query=query,
            reply=_clean(str(data.get("reply") or ""), 600),
            artist=_clean(str(data.get("artist") or ""), 80),
            song=_clean(str(data.get("song") or ""), 100),
            suggestions=suggestions,
            source=source,
            note=source,
        )


def _clean(value: str, limit: int) -> str:
    """Normalise text and strip markdown leftovers from LLM output."""
    value = unicodedata.normalize("NFC", value or "")
    value = re.sub(r"[*`_#>]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]


def _parse_json_object(raw: str) -> dict:
    """Tolerate code fences and chatty preambles around the JSON object."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in LLM reply")
    parsed = json.loads(text[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM reply is not a JSON object")
    return parsed


def _text_from_response(data: dict, provider: str) -> str:
    if provider == "gemini":
        candidates = data.get("candidates") or []
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return "".join(str(p.get("text") or "") for p in parts)
    choices = data.get("choices") or []
    content = (choices[0].get("message") or {}).get("content") or ""
    if isinstance(content, list):  # some OpenAI-compatible APIs return parts
        return "".join(str(part.get("text") or "") for part in content if isinstance(part, dict))
    return str(content)


# ---------------------------------------------------------------------------
# Local reasoning engine (works with zero configuration)
# ---------------------------------------------------------------------------

RECOMMEND_WORDS = (
    "ညွှန်း", "အကြံပြု", "recommend", "suggest", "playlist",
    "သီချင်းကောင်း", "ဘာနားထောင်", "ဘာဖွင့်", "တစ်ပုဒ်လောက်", "နားထောင်စရာ",
    "what should i listen", "give me some", "နားထောင်ချင်တယ်",
)
QUESTION_WORDS = (
    "ဘယ်သူ", "ဘာလဲ", "ဘာတွေ", "ဘယ်လို", "ဘယ်နှ", "ဘယ်က", "ဘာကြောင့်", "သိချင်",
    "ပြောပြ", "ရှင်းပြ", "အကြောင်း", "အဓိပ္ပာယ်", "ဟုတ်လား", "ဆိုတာ", "မေးချင်",
    "who ", "what ", "when ", "where ", "why ", "how ", "which ", "tell me",
    "explain", "do you know", "meaning of", "info about", "about ", "who's", "whos",
)
MOOD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sad": ("ဝမ်းနည်း", "စိတ်ပျက်", "ငို", "အားငယ်", "အထီးကျန်", "sad", "heartbreak", "breakup", "lonely", "cry", "depress"),
    "happy": ("ပျော်", "စိတ်လန်း", "happy", "cheer", "party", "dance", "fun", "မင်္ဂလာ"),
    "chill": ("အနားယူ", "စိတ်လျှော့", "တည်ငြိမ်", "အိပ်", "chill", "relax", "calm", "lofi", "lo-fi", "study", "sleep"),
    "romantic": ("ချစ်", "အချစ်", "ရည်းစား", "romantic", "love", "crush", "valentine"),
    "energy": ("လေ့ကျင့်", "အားကစား", "workout", "gym", "energy", "hype", "motivat", "energetic"),
}
MOOD_QUERIES: dict[str, tuple[str, ...]] = {
    "sad": ("sad acoustic songs playlist", "slow heartbreak songs", "soft piano music for a broken heart"),
    "happy": ("feel good upbeat songs playlist", "happy pop songs", "morning feel good music"),
    "chill": ("chill lofi songs playlist", "relaxing acoustic songs", "calm evening instrumental music"),
    "romantic": ("romantic love songs playlist", "soft acoustic love songs", "beautiful romantic bollywood songs"),
    "energy": ("workout motivation songs", "high energy hype playlist", "gym hip hop songs"),
    "default": ("trending songs playlist official audio", "top acoustic chill songs", "popular songs this week"),
}
MOOD_REPLIES = {
    "sad": "ဝမ်းနည်းနေရင် နားထောင်လို့ကောင်းတဲ့ သီချင်းလေးတွေ ရွေးပေးထားပါတယ်။ တစ်ပုဒ်လေး နှိပ်ကြည့်ပါနော် ❤️",
    "happy": "ပျော်စရာကောင်းတဲ့ သီချင်းလေးတွေ ရှာပေးထားပါတယ်။ စိတ်လန်းသွားမယ်နော် ✨",
    "chill": "အနားယူရင်း နားထောင်လို့ကောင်းမယ့် သီချင်းလေးတွေ ရွေးပေးထားပါတယ် 🌙",
    "romantic": "ချစ်စရာ သီချင်းလေးတွေ ရွေးပေးထားပါတယ်။ သဘောကျမယ်နော် 💗",
    "energy": "အားတက်စရာ သီချင်းတွေ ရွေးပေးထားပါတယ်။ လှုပ်ရှားကြမယ် 🔥",
    "default": "ဒီလိုလေးတွေ နားထောင်ကြည့်ပါနော်။ ကြိုက်တာလေး ရှိမယ်ထင်ပါတယ် 🎶",
}

# Latin request words, removed as whole words only (never inside a name).
LATIN_FILLERS = (
    "search for", "give me", "i would like", "i'd like", "can you", "could you",
    "i want", "i need", "the song", "official audio", "please", "pls", "plz",
    "play", "search", "find", "download", "songs", "song", "music", "mp3",
    "audio", "official", "want", "need", "me", "some", "by",
)

# Burmese request phrases are often glued to each other without spaces. They
# are stripped only from the START of a whitespace token, so song titles like
# "မိုးသီချင်း" stay intact while "သီချင်းလေး" (a generic word for "song") goes.
BURMESE_FILLER_PREFIXES = (
    "ကျေးဇူးပြုပြီး", "ကျွန်တော်", "ကျွန်မ", "နားထောင်ချင်တယ်", "နားထောင်ချင်",
    "သိချင်တယ်", "လိုချင်တယ်", "ဖွင့်ပေးပါဗျ", "ဖွင့်ပေးပါ", "ဖွင့်ပေး",
    "ရှာပေးပါ", "ရှာပေး", "ပို့ပေးပါ", "ပို့ပေး", "ပေးပါဗျ", "ပေးပါရှင့်",
    "ပေးပါ", "ပေးဗျာ", "ပေးနော်", "ပါဗျ", "ပါရှင့်", "ပါတယ်", "ပါတော့",
    "သီချင်းတစ်ပုဒ်", "သီချင်းလေး", "သီချင်းတွေ", "သီချင်း", "တစ်ပုဒ်",
    "လိုချင်", "ဗျာ", "နော်", "ဗျ", "လေး", "တယ်", "ပါ", "လောက်",
)
BURMESE_DROP_TOKENS = {
    "ရဲ့", "ကို", "က", "နဲ့", "တော့", "လည်း", "ထဲ", "အပေါ်", "အတွက်",
    "သီချင်း", "သီချင်းလေး", "တစ်ပုဒ်", "လေး", "ဗျ", "ဗျာ", "နော်",
    "ပါ", "တယ်", "လောက်", "ဖွင့်ပေးပါဗျ", "ပေးပါ",
}

# Well-known artists used ONLY for gentle typo correction (not as a database).
KNOWN_ARTISTS = (
    "Sai Htee Saing", "Sai Sai Maw", "Zaw Win Htut", "Ni Ni Khin Zaw", "Myo Gyi",
    "Wai La", "Mi Mi Khe", "Khin Yu May", "Myint Myint Khin", "Lay Phyu",
    "Taylor Swift", "The Weeknd", "Ed Sheeran", "Adele", "Billie Eilish", "Coldplay",
    "Ariana Grande", "Justin Bieber", "Eminem", "Linkin Park", "Queen",
    "Michael Jackson", "Drake", "Rihanna", "Bruno Mars", "Dua Lipa", "BTS",
    "BLACKPINK", "IU", "Arijit Singh", "Shreya Ghoshal", "Sonu Nigam",
    "Atif Aslam", "Nusrat Fateh Ali Khan", "Diljit Dosanjh", "Karan Aujla",
    "Sidhu Moose Wala", "Burna Boy", "Wizkid", "Davido", "Rema", "Tems",
    "Imagine Dragons", "Maroon 5", "OneRepublic", "Sia", "Sam Smith",
)


def _strip_latin_fillers(text: str) -> str:
    """Remove English request words as whole words (keeps "Coldplay" intact)."""
    alternatives = "|".join(re.escape(word) for word in sorted(LATIN_FILLERS, key=len, reverse=True))
    return re.sub(rf"\b(?:{alternatives})\b", " ", text, flags=re.IGNORECASE)


def _clean_burmese_token(token: str) -> str:
    """Strip leading Burmese request phrases from a single token.

    A glued song title is untouched because it does not START with a filler,
    while generic words for "song" or "please play" are reduced to nothing.
    """
    if not any("\u1000" <= char <= "\u109f" for char in token):
        return token
    value = token.strip("။၊.,!?;:\"'` ")
    while value:
        for phrase in BURMESE_FILLER_PREFIXES:
            if value.startswith(phrase) and len(value) >= len(phrase):
                value = value[len(phrase):]
                break
        else:
            break
    if not value or value in BURMESE_DROP_TOKENS:
        return ""
    return value


def _is_mostly_myanmar(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    burmese = sum(1 for c in letters if "\u1000" <= c <= "\u109f")
    return burmese / len(letters) > 0.4


def clean_query(text: str) -> str:
    """Turn a natural request into a compact, searchable query.

    Filler words are removed as whole tokens only, so glued Burmese song
    titles such as ``မိုးသီချင်း`` are left intact.
    """
    value = unicodedata.normalize("NFC", text or "").strip()
    value = re.sub(r"[\"'`“”‘’]+", " ", value)
    value = re.sub(r"[!?။၊,;:]+", " ", value)
    # Drop emoji / decorative symbols but keep Burmese & Latin letters.
    value = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", " ", value)

    # Fix artist typos FIRST: "cold play" -> "Coldplay" before the word "play"
    # could be removed as a filler.
    value = _correct_artist(value)
    value = _strip_latin_fillers(value)

    tokens = [cleaned for tok in value.split() if (cleaned := _clean_burmese_token(tok))]
    value = " ".join(tokens)
    value = _correct_artist(value)  # second chance after cleaning
    value = re.sub(r"\s+", " ", value).strip(" -–—·|")
    return value[:120]


def _correct_artist(text: str) -> str:
    """Fix near-miss Latin artist names ("cold play" -> "Coldplay")."""
    tokens = text.split()
    if not tokens or not re.search(r"[A-Za-z]", text):
        return text
    canonical = {name.lower(): name for name in KNOWN_ARTISTS}
    alias = {"coldplay": "Coldplay"}  # allow single-token misspellings
    canonical.update(alias)
    keys = list(canonical)

    for size in (3, 2, 1):
        for start in range(len(tokens) - size + 1):
            chunk = " ".join(tokens[start:start + size])
            if len(chunk) < 6 or not re.search(r"[A-Za-z]", chunk):
                continue
            cutoff = 0.9 if size == 1 else 0.85
            match = get_close_matches(chunk.lower(), keys, n=1, cutoff=cutoff)
            if not match:
                continue
            # A close prefix is not enough: "Billie Eilish bad" must NOT be
            # collapsed to "Billie Eilish" and swallow the song title.
            if match[0] != chunk.lower() and abs(len(chunk) - len(match[0])) > 2:
                continue
            fixed = canonical[match[0]]
            if fixed == chunk:
                continue
            tokens[start:start + size] = [fixed]
            return " ".join(tokens)
    return text


def _has_any(text: str, words: Iterable[str]) -> bool:
    return any(word in text for word in words)


def _detect_mood(text: str) -> str:
    for mood, keywords in MOOD_KEYWORDS.items():
        if _has_any(text, keywords):
            return mood
    return ""


def _is_greeting(text: str) -> bool:
    stripped = text.strip().lower().strip("!., ")
    return stripped in {"hi", "hello", "hey", "yo", "မင်္ဂလာပါ", "ဟိုင်း", "ဟဲလိုး"} or _has_any(
        stripped, ("ကျေးဇူးတင်ပါတယ်", "thank you", "thanks", "good morning", "good night")
    )


def _looks_like_question(text: str) -> bool:
    if text.rstrip().endswith(("?", "？", "လား", "လဲ")):
        return True
    return _has_any(text, QUESTION_WORDS)


def local_think(text: str, force_chat: bool = False) -> AIResult:
    """Reason about a message without any network / API key."""
    raw = unicodedata.normalize("NFC", (text or "").strip())
    low = raw.lower()

    if _is_greeting(low):
        reply = (
            "မင်္ဂလာပါနော် 👋 ကျွန်တော်က Goii ရဲ့ ဂီတ AI ပါ။ "
            "သီချင်းအမည်၊ အဆိုတော်အမည်၊ ဒါမှမဟုတ် စိတ်ခံစားချက်လေး ပြောပေးရင် "
            "ရှာပေးပါ့မယ် 🎶"
        )
        if _has_any(low, ("ကျေးဇူး", "thank")):
            reply = "ရပါတယ်နော် ❤️ နောက်တစ်ပုဒ် ရှာပေးရမလား? 🎧"
        return AIResult(intent="chat", reply=reply, source="local", note="local")

    if force_chat:
        query = clean_query(raw)
        return AIResult(
            intent="info",
            search_query=query,
            reply=_LOCAL_INFO_REPLY.format(name=query or raw),
            suggestions=[query] if query else [],
            source="local",
            note="local",
        )

    mood = _detect_mood(low)
    if mood or _has_any(low, RECOMMEND_WORDS):
        suggestions = list(MOOD_QUERIES.get(mood or "default", MOOD_QUERIES["default"]))
        return AIResult(
            intent="recommend",
            search_query=suggestions[0],
            reply=MOOD_REPLIES.get(mood or "default", MOOD_REPLIES["default"]),
            suggestions=suggestions,
            source="local",
            note="local",
        )

    if _looks_like_question(low):
        query = clean_query(raw)
        return AIResult(
            intent="info",
            search_query=query,
            reply=_LOCAL_INFO_REPLY.format(name=query or raw),
            suggestions=[query] if query else [],
            source="local",
            note="local",
        )

    query = clean_query(raw) or raw
    return AIResult(
        intent="search",
        search_query=query,
        reply=f"🔎 {query} ကို နားလည်ပြီး ရှာပေးနေပါတယ်နော် 🎧",
        source="local",
        note="local",
    )


_LOCAL_INFO_REPLY = (
    "🧠 «{name}» အကြောင်းကို Cloud AI နဲ့ဆိုရင် အသေးစိတ် စဉ်းစားပြီး ဖြေပေးနိုင်ပါတယ်။ "
    "အခုတော့ AI_API_KEY မသတ်မှတ်ထားသေးလို့ အောက်က နာမည်လေးကို "
    "ရှာပေးလိုက်ပါတယ်နော်။ Key ထည့်ပေးရင် အဆိုတော်၊ သီချင်း၊ စာသားအဓိပ္ပာယ် "
    "အကုန်လုံးကို ပြောပြနိုင်ပါလိမ့်မယ် ✨"
)


# ---------------------------------------------------------------------------
# The brain
# ---------------------------------------------------------------------------

class MusicAI:
    """Provider-agnostic music brain with automatic local fallback."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        self.provider = self.settings.resolved_provider()

    @property
    def has_key(self) -> bool:
        return bool(self.settings.ai_api_key)

    def status_model(self) -> str:
        if self.provider == "local":
            return ""
        models = self._models()
        return self.settings.ai_model or (models[0] if models else "default")

    def _models(self) -> tuple[str, ...]:
        if self.settings.ai_model:
            return (self.settings.ai_model,)
        if self.provider == "gemini":
            return GEMINI_MODELS
        return CHAT_MODELS.get(self.provider, ())

    async def think(
        self,
        text: str,
        history: list[dict[str, str]] | None = None,
        force_chat: bool = False,
    ) -> AIResult:
        """Understand a user message. Never raises — always returns a result."""
        message = unicodedata.normalize("NFC", (text or "").strip())
        if not message:
            return AIResult(intent="chat", reply="ဘာမှ မရိုက်ထားပါဘူးနော် 🙈", source="local")

        if self.provider != "local":
            try:
                result = await asyncio.wait_for(
                    self._think_llm(message, history or [], force_chat),
                    timeout=self.settings.ai_timeout + 3,
                )
                if result.reply or result.search_query:
                    if result.intent == "recommend" and not result.suggestions:
                        result.suggestions = list(MOOD_QUERIES["default"])
                        result.search_query = result.search_query or result.suggestions[0]
                    return result
            except Exception as exc:  # network, quota, bad JSON, ...
                LOG.warning("AI provider '%s' failed (%s) — using local brain", self.provider, exc)

        return local_think(message, force_chat=force_chat)

    # -- cloud -------------------------------------------------------------

    async def _think_llm(
        self, text: str, history: list[dict[str, str]], force_chat: bool
    ) -> AIResult:
        prompt = self._build_prompt(text, history, force_chat)
        raw = await asyncio.to_thread(self._request_llm, prompt)
        data = _parse_json_object(_text_from_response(raw, self.provider))
        return AIResult.from_llm(data, self.provider, text)

    def _build_prompt(
        self, text: str, history: list[dict[str, str]], force_chat: bool
    ) -> str:
        parts: list[str] = []
        if history:
            parts.append("Previous conversation (oldest first):")
            for item in history[-8:]:
                role = "User" if item.get("role") == "user" else "Bot"
                parts.append(f"{role}: {str(item.get('text', ''))[:300]}")
            parts.append("")
        if force_chat:
            parts.append("NOTE: The user used the /ai command, so they want an ANSWER, not a search.")
        parts.append(f"Current user message: {text}")
        return "\n".join(parts)

    def _request_llm(self, prompt: str) -> dict:
        if self.provider == "gemini":
            return self._request_gemini(prompt)
        return self._request_chat(prompt)

    def _request_gemini(self, prompt: str) -> dict:
        last_error: Exception | None = None
        for model in self._models():
            url = GEMINI_ENDPOINT.format(model=model)
            url += f"?key={self.settings.ai_api_key}"
            def build_payload(disable_thinking: bool) -> dict:
                generation = {
                    "temperature": 0.75,
                    "maxOutputTokens": 1000,
                    "responseMimeType": "application/json",
                }
                # 2.5 Flash "thinks" by default and can burn the whole token
                # budget without emitting JSON. Gemini 3 uses a different
                # parameter, so a 400 mentioning thinking is retried without it.
                if disable_thinking:
                    generation["thinkingConfig"] = {"thinkingBudget": 0}
                return {
                    "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": generation,
                }

            try:
                try:
                    data = _post_json(url, {}, build_payload(True), self.settings.ai_timeout)
                except LLMHTTPError as exc:
                    if exc.status == 400 and "thinking" in exc.body.lower():
                        data = _post_json(url, {}, build_payload(False), self.settings.ai_timeout)
                    else:
                        raise
                if not _text_from_response(data, "gemini"):
                    raise ValueError("empty Gemini response")
                return data
            except (LLMModelUnavailable, ValueError) as exc:
                LOG.info("Gemini model %s gave no usable answer, trying next: %s", model, exc)
                last_error = exc
                continue
            except LLMHTTPError as exc:
                # Key/quota problems won't be fixed by another model.
                if exc.status in (400, 401, 403, 429):
                    raise
                last_error = exc
        raise last_error or RuntimeError("no Gemini model available")

    def _request_chat(self, prompt: str) -> dict:
        endpoint = self.settings.ai_base_url or CHAT_ENDPOINTS.get(self.provider, "")
        if not endpoint:
            raise ValueError("AI_BASE_URL is required for this provider")
        if not endpoint.rstrip("/").endswith("chat/completions"):
            endpoint = endpoint.rstrip("/") + "/chat/completions"
        models = self._models() or ("gpt-4o-mini",)
        headers = {"Authorization": f"Bearer {self.settings.ai_api_key}"}
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/khm337832-boop/Goii-music-bot"

        last_error: Exception | None = None
        for model in models:
            payload: dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.75,
                "max_tokens": 900,
                "response_format": {"type": "json_object"},
            }
            try:
                return self._post_chat_once(endpoint, headers, payload)
            except LLMModelUnavailable as exc:
                LOG.info("Chat model %s unavailable, trying next: %s", model, exc)
                last_error = exc
            except LLMHTTPError as exc:
                if exc.status in (400, 401, 403, 429):
                    raise
                last_error = exc
        raise last_error or RuntimeError("no chat model available")

    def _post_chat_once(self, endpoint: str, headers: dict, payload: dict) -> dict:
        """Retry once without ``response_format`` for pickier providers."""
        try:
            return _post_json(endpoint, headers, payload, self.settings.ai_timeout)
        except LLMHTTPError as exc:
            if exc.status != 400:
                raise
            payload = dict(payload)
            payload.pop("response_format", None)
            return _post_json(endpoint, headers, payload, self.settings.ai_timeout)


# ---------------------------------------------------------------------------
# Query helpers used by the bot
# ---------------------------------------------------------------------------

SEARCH_SUFFIXES = ("official audio", "audio", "lyrics", "official music video")


def build_youtube_query(query: str, page: int = 0) -> str:
    """Add a light hint for Latin queries; leave Burmese queries untouched."""
    base = (query or "").strip()
    if not base or _is_mostly_myanmar(base):
        return base
    low = base.lower()
    if any(word in low for word in ("official", "lyrics", "audio", "cover", "remix", "live", "video", "playlist")):
        return base
    suffix = SEARCH_SUFFIXES[page % len(SEARCH_SUFFIXES)]
    return f"{base} {suffix}"
