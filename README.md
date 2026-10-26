# 🎧 Goii Music Bot ✨

Telegram music bot that **thinks** about what you type — songs, artists, moods or
questions — then finds and sends the MP3. Burmese 🇲🇲 and English both work.

> **TL;DR** — set `BOT_TOKEN`, run `python main.py`. It already works.
> Add one free `AI_API_KEY` and it becomes a real AI that can reason about
> artists and songs way beyond a fixed list.

---

## 🆕 What's new

| Before | Now |
| --- | --- |
| Text was pasted straight into `ytsearch5:` | An **AI brain** (`ai_brain.py`) understands the request first |
| Only exact / literal strings worked | Handles typos, Burmese, romanized Burmese, moods, lyric fragments, "that song by…", follow-up messages |
| Could not answer questions about artists | `info` / `chat` intent answers with real knowledge (cloud AI), or an honest local reply |
| Plain `🎵 title...` buttons, raw `**` markdown | A consistent **icon system** (`icons.py`), numbered result buttons, HTML formatting, menus, status cards |
| Bot token hard-coded in `main.py` | Token read from `BOT_TOKEN` env var / `.env` |
| Temp files leaked on errors | Always cleaned up, concurrency limited to protect free-tier RAM |

### 🧠 The AI brain has two layers

```
user message
     │
     ▼
MusicAI.think()  ──►  cloud LLM (Gemini / Groq / OpenAI / OpenRouter / custom)
     │                     │  JSON decision: intent, search_query, reply, suggestions
     │                     └─ any error / timeout / no key ─┐
     ▼                                                      ▼
local reasoning engine  ◄────────────────────────────────────┘
     │  Burmese+English filler removal, mood detection,
     │  question detection, fuzzy artist typo correction
     ▼
search ─► YouTube (yt-dlp) ─► MP3 ─► Telegram
recommend / info / chat ─► AI answer + inline buttons
```

**It never gets stuck**: missing key, expired model, rate limit, bad JSON or
offline network all fall back to the local engine automatically.

---

## 🚀 Quick start (local)

```bash
git clone https://github.com/khm337832-boop/Goii-music-bot.git
cd Goii-music-bot
pip install -r requirements.txt

cp .env.example .env      # put your BOT_TOKEN in it
python main.py
```

Open `http://localhost:8080/health` to check the bot is alive.

`static-ffmpeg` downloads FFmpeg on first run; the `render.yaml` buildpack also
provides a system FFmpeg, so either one works.

---

## 🤖 Giving the bot a real AI (optional but recommended)

Get a **free** Gemini API key at <https://aistudio.google.com/app/apikey>, then:

```bash
export AI_PROVIDER=gemini
export AI_API_KEY="AIza...your-key..."
python main.py
```

Or add those two values in the Render dashboard → Environment.

| Provider | `AI_PROVIDER` | Key variable | Notes |
| --- | --- | --- | --- |
| Google Gemini (free) | `gemini` | `AI_API_KEY` or `GEMINI_API_KEY` | Default. Tries current Flash models automatically |
| Groq | `groq` | `GROQ_API_KEY` | Very fast, OpenAI-compatible |
| OpenAI | `openai` | `OPENAI_API_KEY` | Default model `gpt-4o-mini` |
| OpenRouter | `openrouter` | `AI_API_KEY` | Free models available |
| Any OpenAI-compatible API | `custom` | `AI_API_KEY` **+ `AI_BASE_URL`** | e.g. your own vLLM / LM Studio server |
| Offline only | `local` | — | No network, no key |

`AI_PROVIDER=auto` (default) picks the provider from whichever key env var it
finds. Pin a model with `AI_MODEL` (e.g. `AI_MODEL=gemini-3.5-flash`) — model
IDs change over time, so the built-in list is tried in order and a `404` on a
retired model automatically falls through to the next one.

### Example things the AI now understands

- `Sai Htee Saing ရဲ့ မိုးသီချင်းလေး ဖွင့်ပေးပါ` → clean search query
- `စိတ်ပျက်နေတယ် သီချင်းလေးညွှန်းပေးပါ` → mood recommendations
- `ဒီသီချင်းကို ဘယ်သူဆိုတာလဲ?` → AI answer about the artist + play button
- `cold play ရဲ့ သီချင်း` → typo corrected to **Coldplay**
- `နောက်တစ်ပုဒ်` / `another one` → remembers the previous turn

---

## 🎛 Commands & buttons

| Command | What it does |
| --- | --- |
| `/start` | Welcome card + main menu |
| plain text | AI decides: search, recommend, info or chat |
| `/ai <question>` | Force an AI answer (great for artist questions) |
| `/search <name>` | Fast direct search, no LLM round-trip |
| `/brain` | Shows which AI engine is active |
| `/link` | Shows the public `https://t.me/...` bot link |
| `/help` | Command list |

Inline menus: 🔎 search, 🤖 ask AI, 🧠 AI status, ℹ️ help, 🔄 more results,
🔙 back. Result rows are numbered `1️⃣…5️⃣` with a duration badge.

---

## ⚙️ Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `BOT_TOKEN` | — | **Required.** Telegram token from [@BotFather](https://t.me/BotFather) |
| `BOT_USERNAME` | — | Bot's `@username` (no `@`). Enables `/link` and the link chip on the web page |
| `AI_PROVIDER` | `auto` | `auto / gemini / groq / openai / openrouter / custom / local` |
| `AI_API_KEY` | — | Generic key, used with any provider |
| `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY` | — | Provider-specific alternatives |
| `AI_MODEL` | auto | Pin a model ID |
| `AI_BASE_URL` | — | Base URL for `custom` OpenAI-compatible endpoints |
| `AI_TIMEOUT` | `12` | Seconds before falling back to the local brain |
| `MAX_SEARCH_RESULTS` | `5` | Result rows (1–8) |
| `AUDIO_QUALITY` | `96` | MP3 kbps — kept low to protect free-tier RAM |
| `MAX_FILE_MB` | `12` | Skip oversized downloads |
| `DOWNLOAD_DIR` | `downloads` | Temporary folder (auto-cleaned) |
| `PORT` | `8080` | Keep-alive web server port |

---

## 🔗 Bot link

A Telegram bot link is always `https://t.me/<username>` — the **username** is
chosen in [@BotFather](https://t.me/BotFather) → `/mybots` → your bot →
**Bot Settings → Username**. The repo cannot guess it, so set it once:

```bash
export BOT_USERNAME="GoiiMusicBot"    # no @ needed
```

Then the public link is **https://t.me/GoiiMusicBot** and the bot itself will
show it via `/link`, the `/start` menu (`🔗 Bot link ပေးပါ`), the health endpoint
(`/health` → `bot_link`) and the web page chip. Without a username, Telegram
does not offer a shareable `t.me/...` URL — `/link` explains how to get one.
`/health` also reports `bot_id` (the numeric part of the token).

## ☁️ Deploy on Render

1. Push this branch and create a **Web Service** from the repo (or use the
   included `render.yaml` as a Blueprint).
2. Add `BOT_TOKEN` and `BOT_USERNAME` in **Environment** (`sync: false` in the
   YAML means Render will ask you for the values). The web URL shown in the
   Render dashboard is the keep-alive site, **not** the Telegram bot link.
3. Optionally add `AI_PROVIDER=gemini` and `AI_API_KEY=...`.
4. Deploy. `/health` returns `{"status":"ok", ...}` so the free service stays up.

> ⚠️ **Security:** an earlier version of `main.py` contained a bot token in
> plain text. That token is public in Git history — **revoke it with
> [@BotFather](https://t.me/BotFather) (`/revoke`)** and put the new one in
> `BOT_TOKEN` only. Never commit `.env`.

---

## 🎨 Changing the icons

All emoji and message layouts live in **`icons.py`** (`class I`). Edit `I.BOT`,
`I.SEARCH`, `I.DIVIDER`, `NUMBER_ICONS`, `TRACK_ICONS` … and the whole bot
changes look at once. Dynamic values are HTML-escaped there, so it is safe to
keep `parse_mode="HTML"`.

Want to see the design before deploying? Run the visual preview (no Telegram
token or network needed):

```bash
python preview.py      # http://localhost:8080
```

It renders the real message templates as Telegram-like chat bubbles — welcome
menu, thinking state, numbered result buttons, download stages, audio caption,
recommendations, AI answers and error cards.

Files:

```
main.py        Telegram handlers, menus, routing, download flow
ai_brain.py    LLM client + local reasoning engine
music.py       yt-dlp search / MP3 download / cleanup
icons.py       icon palette + all message templates
config.py      env (.env) settings
preview.py     browser preview of the new message designs
tests/         dependency-free unittest suite
```

---

## ✅ Tests

```bash
python -m unittest discover -s tests -v
```

No API key or network needed — tests cover intent detection, query cleaning,
typo correction, JSON parsing, provider resolution and message rendering.

---

Made with ❤️ for Burmese music lovers. 🎶
