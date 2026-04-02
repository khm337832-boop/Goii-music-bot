import os
import logging
import yt_dlp
import asyncio
from flask import Flask
from threading import Thread
from static_ffmpeg import add_paths
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# FFmpeg လမ်းကြောင်းကို အလိုအလျောက် သတ်မှတ်ပေးခြင်း
add_paths()

# --- Web Server (Render မှာ Bot မသေအောင် ထိန်းပေးရန်) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online! ❤️"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- သင်ပေးထားတဲ့ Bot Token ကို ဒီမှာ အသေထည့်ထားပါတယ် ---
TOKEN = "8750923349:AAHsRNgP_f-o1p5-fXnTjkY0s2w8-6wh41U"
CHANNEL_URL = "https://t.me/music002234"

# --- သီချင်းဒေါင်းလုဒ်ဆွဲပြီး Audio ပြောင်းပေးမည့်စနစ် ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'check_join':
        await query.edit_message_text("ကျေးဇူးတင်ပါတယ်။ အခု သီချင်းအမည်ကို ရိုက်ထည့်ပြီး ရှာဖွေနိုင်ပါပြီ။ 🎶")
    
    elif query.data.startswith('dl_'):
        vid = query.data.split('_')[1]
        url = f"https://www.youtube.com/watch?v={vid}"
        status_msg = await query.message.reply_text("⏳ သီချင်းကို Audio (MP3) ပြောင်းပြီး ပို့ပေးနေပါတယ်... ခဏစောင့်ပါနော်။ 🎧")
        
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
            await status_msg.edit_text("❌ သီချင်းပို့ရတာ အဆင်မပြေပါ။ ခဏကြာမှ ပြန်ကြိုးစားကြည့်ပါ။")

# --- သီချင်းရှာဖွေပေးမည့်စနစ် ---
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
                keyboard.append([InlineKeyboardButton(f"{i+1}. {title[:35]}...", callback_data=f"dl_{vid}")])
            
            await search_msg.delete()
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        await search_msg.edit_text("❌ ရှာဖွေမှု အဆင်မပြေပါ။")

# --- Bot ကို စတင်ခိုင်းသည့် Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Join Channel 📢", url=CHANNEL_URL)],
                [InlineKeyboardButton("Join ပြီးပါပြီ ✅", callback_data='check_join')]]
    await update.message.reply_text("မင်္ဂလာပါ! သီချင်းနားထောင်ဖို့ အောက်က Channel ကို အရင် Join ပေးပါနော်။ ❤️", 
                                  reply_markup=InlineKeyboardMarkup(keyboard))

def main():
    if not os.path.exists('downloads'): os.makedirs('downloads')
    keep_alive()
    
    app_bot = Application.builder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_song))
    
    print("Bot is starting with hardcoded token...")
    app_bot.run_polling()

if __name__ == '__main__':
    main()
