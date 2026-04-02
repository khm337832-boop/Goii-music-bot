import os
import logging
import yt_dlp
import asyncio
from flask import Flask
from threading import Thread
from static_ffmpeg import add_paths
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# FFmpeg setup
add_paths()

app = Flask('')
@app.route('/')
def home(): return "Goli Music Bot - Power Mode 🚀"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# Config
TOKEN = "8750923349:AAHsRNgP_f-o1p5-fXnTjkY0s2w8-6wh41U"

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith('dl_'):
        vid = query.data.split('_')[1]
        url = f"https://www.youtube.com/watch?v={vid}"
        status_msg = await query.message.reply_text("🚀 RAM ချွေတာရေးစနစ်ဖြင့် အမြန်ဆုံး ပို့ပေးနေပါတယ်... 🎧")
        
        try:
            # RAM စားသက်သာအောင် 96kbps quality ကို သုံးပြီး temporary ဒေါင်းပါမယ်
            path = f"downloads/{vid}.mp3"
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'downloads/{vid}.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '96', # 128 ထက် ပိုနည်းအောင်လုပ်ပြီး RAM ကို ကာကွယ်တာပါ
                }],
                'quiet': True,
                'no_warnings': True,
                'max_filesize': 10 * 1024 * 1024 # 10MB ထက်ကြီးရင် မဒေါင်းခိုင်းပါနဲ့ (RAM crash လို့ပါ)
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, url, download=True)
                title = info.get('title', 'Song Title')
                
                with open(path, 'rb') as audio:
                    await context.bot.send_audio(
                        chat_id=update.effective_chat.id, 
                        audio=audio, 
                        title=title,
                        performer="Goli Bot 🔥",
                        caption=f"🎵 **{title}**\n\n✅ Done! (RAM Optimized Mode)"
                    )
                
                if os.path.exists(path): os.remove(path)
                await status_msg.delete()

        except Exception as e:
            # Error တက်ရင် logs မှာ ကြည့်လို့ရအောင် ထုတ်ပြတာပါ
            logging.error(f"Error: {e}")
            await status_msg.edit_text("❌ Render RAM ပြည့်သွားပါပြီ။ သီချင်းအရှည်ကြီးတွေဆိုရင် ပို့မရနိုင်ပါဘူး။ ခဏနေမှ ပြန်စမ်းကြည့်ပါဗျာ။")

async def search_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text
    search_msg = await update.message.reply_text("🔎 နာမည်ကြီး Official Audio များကို ရှာဖွေနေပါတယ်...")
    
    try:
        ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Official Audio တွေကို ဦးစားပေးရှာမယ်
            results = await asyncio.to_thread(ydl.extract_info, f"ytsearch5:{user_query} official audio", download=False)
            entries = results.get('entries', [])
            
            if not entries:
                await search_msg.edit_text("⚠️ ရှာမတွေ့ပါ။ အမည်မှန်အောင် ပြန်ရိုက်ကြည့်ပါ။")
                return

            keyboard = []
            for entry in entries:
                title = entry.get('title')
                vid = entry.get('id')
                keyboard.append([InlineKeyboardButton(f"🎵 {title[:35]}...", callback_data=f"dl_{vid}")])
            
            await search_msg.delete()
            await update.message.reply_text("🔥 လူကြိုက်အများဆုံး ရလဒ်များ -", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        await search_msg.edit_text("❌ ရှာဖွေမှု အဆင်မပြေပါ။")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Goli Music Bot မှ ကြိုဆိုပါတယ်။\n\nသီချင်းအမည်ရိုက်ပြီး ရှာဖွေနိုင်ပါပြီ။ အမြန်ဆုံးစနစ်နဲ့ ပို့ပေးပါ့မယ်! ❤️")

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
