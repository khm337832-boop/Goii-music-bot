import os
import logging
import yt_dlp
import asyncio
from flask import Flask
from threading import Thread
from static_ffmpeg import add_paths
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# FFmpeg ကို Code ထဲကနေ တိုက်ရိုက် လမ်းကြောင်းဖွင့်ပေးခြင်း
add_paths()

# --- Web Server (Keeping Bot Alive) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online and Ready!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- Config ---
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_URL = "https://t.me/music002234"

# --- Button & Download Handler ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'check_join':
        await query.edit_message_text("ကျေးဇူးတင်ပါတယ်။ အခု သီချင်းအမည်ကို ရိုက်ထည့်ပြီး ရှာဖွေနိုင်ပါပြီ။ 🎶")
    
    elif query.data.startswith('dl_'):
        vid = query.data.split('_')[1]
        url = f"https://www.youtube.com/watch?v={vid}"
        status_msg = await query.message.reply_text("⏳ သီချင်းကို Audio ပြောင်းပြီး ပို့ပေးနေပါတယ်... ခဏစောင့်ပါနော်။ 🎧")
        
        try:
            path = f"downloads/{vid}.mp3"
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'downloads/{vid}.%(ext)s',
                'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
                'quiet': True,
                'no_warnings': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, url, download=True)
                title = info.get('title', 'Song Title')
                
                with open(path, 'rb') as audio:
                    await context.bot.send_audio(
                        chat_id=update.effective_chat.id, 
                        audio=audio, 
                        title=title,
                        caption=f"🎵 {title}\n📥 Downloaded via Goli Bot"
                    )
                
                if os.path.exists(path): os.remove(path)
                await status_msg.delete()

        except Exception as e:
            logging.error(f"Error: {e}")
            await status_msg.edit_text("❌ သီချင်းပို့ရတာ အဆင်မပြေပါ။ Token သို့မဟုတ် Internet ပြဿနာ ဖြစ်နိုင်ပါတယ်။")

# --- Search Handler ---
async def search_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text
    search_msg = await update.message.reply_text("🔎 ရှာဖွေနေပါတယ်...")
    
    try:
        with yt_dlp.YoutubeDL({'format': 'bestaudio/best', 'quiet': True, 'extract_flat': True}) as ydl:
            results = await asyncio.to_thread(ydl.extract_info, f"ytsearch5:{user_query}", download=False)
            entries = results.get('entries', [])
            
            if not entries:
                await search_msg.edit_text("⚠️ သီချင်းရှာမတွေ့ပါ။ အမည်မှန်အောင် ပြန်ရိုက်ကြည့်ပါ။")
                return

            keyboard = []
            text = "🔎 ရလဒ် ၅ ခု တွေ့ရှိပါတယ် - \n\n"
            for i, entry in enumerate(entries):
                title = entry.get('title')
                vid = entry.get('id')
                text += f"{i+1}. {title}\n"
                keyboard.append([InlineKeyboardButton(f"{i+1}. {title[:35]}...", callback
