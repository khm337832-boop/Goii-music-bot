import os
import logging
import yt_dlp
import asyncio
from flask import Flask
from threading import Thread
from static_ffmpeg import add_paths
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

add_paths()

app = Flask('')
@app.route('/')
def home(): return "Bot Online ❤️"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

TOKEN = "8750923349:AAHsRNgP_f-o1p5-fXnTjkY0s2w8-6wh41U"

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith('dl_'):
        vid = query.data.split('_')[1]
        url = f"https://www.youtube.com/watch?v={vid}"
        status_msg = await query.message.reply_text("⏳ လူကြိုက်အများဆုံး Quality နဲ့ ပြောင်းပေးနေပါတယ်... ခဏစောင့်ပါ ❤️")
        
        try:
            path = f"downloads/{vid}.mp3"
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'downloads/{vid}.%(ext)s',
                'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '128'}], # RAM ချွေတာဖို့ 128 ထားပါတယ်
                'quiet': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, url, download=True)
                title = info.get('title', 'Song')
                
                with open(path, 'rb') as audio:
                    await context.bot.send_audio(chat_id=update.effective_chat.id, audio=audio, title=title)
                
                if os.path.exists(path): os.remove(path)
                await status_msg.delete()

        except Exception as e:
            await status_msg.edit_text("❌ Render RAM မလုံလောက်ပါ (သို့မဟုတ်) FFmpeg Error တက်နေပါသည်။")

async def search_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text
    search_msg = await update.message.reply_text("🔎 နာမည်ကြီးသီချင်းများကို ဦးစားပေး ရှာဖွေနေပါတယ်...")
    
    try:
        # နာမည်ကြီးတာတွေ အရင်ပေါ်အောင် 'relevance' နဲ့ 'view_count' သုံးထားပါတယ်
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'extract_flat': True,
            'default_search': 'ytsearch5',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # search query မှာ view count အများဆုံးကို ရှေ့ကပြခိုင်းတာပါ
            results = await asyncio.to_thread(ydl.extract_info, f"ytsearch5:{user_query} official audio", download=False)
            entries = results.get('entries', [])
            
            keyboard = []
            for entry in entries:
                title = entry.get('title')
                vid = entry.get('id')
                keyboard.append([InlineKeyboardButton(f"🎵 {title[:35]}...", callback_data=f"dl_{vid}")])
            
            await search_msg.delete()
            await update.message.reply_text("🔥 လူကြိုက်အများဆုံး ရလဒ်များ -", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        await search_msg.edit_text("❌ ရှာမတွေ့ပါ။")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ! နာမည်ကြီး သီချင်းအမည်ရိုက်ပြီး ရှာဖွေနိုင်ပါပြီ။ ❤️")

def main():
    if not os.path.exists('downloads'): os.makedirs('downloads')
    keep_alive()
    app_bot = Application.builder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_song))
    app_bot.run_polling()

if __name__ == '__main__':
    main()

