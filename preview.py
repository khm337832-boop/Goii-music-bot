"""🎨 Design preview — see the bot's new icons/messages in your browser.

This is a *dev tool only*: it renders the exact templates from ``icons.py`` as
Telegram-like chat bubbles. It never connects to Telegram or downloads music.

    pip install -r requirements.txt
    python preview.py            # http://localhost:8080
"""
from __future__ import annotations

import html
import os

from flask import Flask

from icons import (
    ai_answer_text,
    brain_status_text,
    caption_text,
    download_text,
    error_text,
    help_text,
    no_results_text,
    prompt_text,
    recommend_text,
    results_text,
    safe_trim,
    thinking_text,
    track_label,
    welcome_text,
)

app = Flask("Goii Preview")

STYLE = """
*{box-sizing:border-box}
body{margin:0;padding:36px 16px 80px;background:radial-gradient(circle at 15% 0%,#2a1c4d,#0c0a18 55%);
 color:#f4f2ff;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;min-height:100vh}
.wrap{max-width:520px;margin:0 auto}
.head{text-align:center;margin-bottom:28px}
.head h1{margin:0 0 6px;font-size:26px}
.head p{margin:0;opacity:.6;font-size:13px;line-height:1.6}
.section{display:flex;align-items:center;gap:10px;margin:30px 0 14px;font-size:12px;
 letter-spacing:.12em;text-transform:uppercase;opacity:.55}
.section::after{content:"";flex:1;height:1px;background:rgba(255,255,255,.14)}
.bubble{background:#1e2130;border:1px solid rgba(255,255,255,.09);border-radius:18px 18px 18px 5px;
 padding:14px 16px;margin-bottom:12px;box-shadow:0 10px 30px rgba(0,0,0,.25);
 font-size:14px;line-height:1.75;word-break:break-word}
.bubble.me{background:#243447;border-radius:18px 18px 5px 18px;margin-left:52px}
.bubble code{background:rgba(255,255,255,.09);padding:2px 6px;border-radius:6px;font-size:12px}
.kb{display:flex;flex-wrap:wrap;gap:7px;margin:-4px 0 12px}
.kb span{padding:8px 12px;border-radius:10px;background:#2b3350;border:1px solid rgba(255,255,255,.10);
 color:#cdd6ff;font-size:12px;cursor:default;flex:1 1 auto;text-align:center}
.kb span:hover{background:#3a4570}
.note{font-size:11px;opacity:.4;margin:-8px 0 16px;text-align:right}
"""


def card(content: str, buttons: list[str] | None = None, me: bool = False, note: str = "") -> str:
    css = "bubble me" if me else "bubble"
    chips = ""
    if buttons:
        chips = '<div class="kb">' + "".join(f"<span>{html.escape(b)}</span>" for b in buttons) + "</div>"
    return f'<div class="{css}">{content}</div>{chips}<div class="note">{html.escape(note)}</div>'


def page() -> str:
    parts: list[str] = ['<!doctype html><html lang="my"><head><meta charset="utf-8">',
                        '<meta name="viewport" content="width=device-width,initial-scale=1">',
                        "<title>Goii Music Bot · Icon preview</title>",
                        f"<style>{STYLE}</style></head><body><div class='wrap'>"]
    parts.append(
        '<div class="head"><h1>🎧 Goii Music Bot ✨</h1>'
        "<p>Icon &amp; message preview · rendered live from <code>icons.py</code><br>"
        "Edit <code>class I</code> there to restyle everything at once.</p></div>"
    )

    parts.append('<div class="section">👋 Start menu</div>')
    parts.append(card(
        welcome_text(),
        ["🔎 သီချင်းရှာမယ်", "🤖 AI ကို မေးမယ်", "ℹ️ အကူအညီ", "🧠 AI အခြေအနေ", "🔗 Bot link ပေးပါ"],
        note="/start",
    ))

    parts.append('<div class="section">🔎 Search flow</div>')
    parts.append(card("Coldplay yellow ဖွင့်ပေးပါဗျ 🎵", me=True, note="user message"))
    parts.append(card(thinking_text(), note="AI thinking"))
    parts.append(card(prompt_text("search"), note="menu prompt"))
    parts.append(card(
        results_text("Coldplay yellow", 5, "gemini"),
        [track_label(i, title, duration) for i, (title, duration) in enumerate([
            ("Yellow - Coldplay", 268), ("Viva La Vida", 242), ("Fix You", 295),
            ("Something Just Like This", 247), ("A Sky Full of Stars", 288),
        ])] + ["🔄 နောက်ထပ် ရလဒ်များ", "🤖 ဒီအကြောင်း မေးမယ်"],
        note="results · numbered icon rows",
    ))
    parts.append(card(no_results_text("unknown xyz song", "local"), ["🔙 မီနူး ပြန်သွားမယ်"], note="no results"))

    parts.append('<div class="section">📥 Download & audio card</div>')
    for stage in range(3):
        parts.append(card(download_text(stage), note=f"stage {stage + 1}"))
    parts.append(card(
        caption_text("Yellow", "Coldplay", 268),
        ["▶️ Play"], note="audio caption",
    ))
    parts.append(card(error_text("download"), note="friendly error"))

    parts.append('<div class="section">🧠 AI brain</div>')
    parts.append(card(
        recommend_text("ဝမ်းနည်းနေရင် နားထောင်လို့ကောင်းတဲ့ သီချင်းလေးတွေ ရွေးပေးထားပါတယ် ❤️",
                       ["sad acoustic songs playlist", "slow heartbreak songs", "soft piano sad music"], "local"),
        [f"{n} ▶️ {safe_trim(s, 28)}" for n, s in zip(
            ("1️⃣", "2️⃣", "3️⃣"),
            ("sad acoustic songs playlist", "slow heartbreak songs", "soft piano sad music"))],
        note="recommendation",
    ))
    parts.append(card(
        ai_answer_text("Coldplay ဆိုတာ ဗြိတိန်ရဲ့ နာမည်ကြီး rock တီးခတ်တဲ့ အဖွဲ့တစ်ခုပါ။ "
                       "Chris Martin က အဆိုတော်ဖြစ်ပြီး Yellow က ၂၀၀၀ ခုနှစ်က သီချင်းပါ 🎸", "gemini"),
        ["🔎 Coldplay ကို ရှာမယ်", "🔙 မီနူး ပြန်သွားမယ်"], note="AI answer",
    ))
    parts.append(card(brain_status_text("gemini", True, "gemini-2.5-flash"), note="/brain · cloud AI on"))
    parts.append(card(brain_status_text("local", False, ""), note="/brain · offline fallback"))
    parts.append(card(help_text("gemini"), note="/help"))

    parts.append("</div></body></html>")
    return "".join(parts)


@app.get("/")
def index() -> str:
    return page()


if __name__ == "__main__":
    port = int(os.environ.get("PREVIEW_PORT", "8080"))
    print(f"🎨 Icon preview running on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
