import os
import logging
import yt_dlp
import asyncio
from flask import Flask
from threading import Thread
from static_ffmpeg import add_paths
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# FFmpeg ကို အလိုအလျောက် လမ်းကြောင်းပြပေးခြင်း
add_paths()

# Web Server
app = Flask('')
@app.route('/')
def home(): return "Bot is Online"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Join Channel 📢", url="https://t.me/music002234")],
                [InlineKeyboardButton("Join ပြီးပါပြီ ✅", callback_data='check_join')]]
    await update.message.reply_text("မင်္ဂလာပါ! သီချင်းရှာဖို့ အမည်ရိုက်ထည့်ပေးပါနော်။ ❤️", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'check_join':
        await query.edit_message_text("အခု သီချင်းအမည်ကို ရိုက်ထည့်ပြီး ရှာဖွေနိုင်ပါပြီ။ 🎶")
    elif query.data.startswith('dl_'):
        vid = query.data.split('_')[1]
        url = f"https://www.youtube.com/watch?v={vid}"
        status_msg = await query.message.reply_text("⏳ သီချင်းပို့ပေးနေပါတယ်... ခဏစောင့်ပေးပါနော်။ 🎧")
        try:
            path = f"downloads/{vid}.mp3"
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'downloads/{vid}.%(ext)s',
                'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
                'quiet': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await asyncio.to_thread(ydl.extract_info, url, download=True)
                with open(path, 'rb') as audio:
                    await context.bot.send_audio(chat_id=update.effective_chat.id, audio=audio)
                if os.path.exists(path): os.remove(path)
                await status_msg.delete()
        except Exception:
            await status_msg.edit_text("❌ သီချင်းပို့မရပါ။ Token ပြန်စစ်ပေးပါ။")

async def search_song(update: Update, context: Update):
    user_query = update.message.text
    search_msg = await update.message.reply_text("🔎 ရှာဖွေနေပါတယ်...")
    try:
        with yt_dlp.YoutubeDL({'format': 'bestaudio/best', 'quiet': True, 'extract_flat': True}) as ydl:
            results = await asyncio.to_thread(ydl.extract_info, f"ytsearch5:{user_query}", download=False)
            entries = results.get('entries', [])
            keyboard = []
            for entry in entries:
                keyboard.append([InlineKeyboardButton(f"🎵 {entry.get('title')[:30]}", callback_data=f"dl_{entry.get('id')}")])
            await search_msg.delete()
            await update.message.reply_text("ရလဒ်များ -", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        await search_msg.edit_text("❌ ရှာမတွေ့ပါ။")

def main():
    if not os.path.exists('downloads'): os.makedirs('downloads')
    keep_alive()
    if not TOKEN: return
    app_bot = Application.builder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_song))
    app_bot.run_polling()

if __name__ == '__main__':
    main()
