import os
import logging
import yt_dlp
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_URL = "https://t.me/music002234"
CHANNEL_ID = "@music002234" 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Join Channel 📢", url=CHANNEL_URL)],
                [InlineKeyboardButton("Join ပြီးပါပြီ ✅", callback_data='check_join')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("မင်္ဂလာပါ! သီချင်းနားထောင်ဖို့ Channel အရင် Join ပေးပါနော်။", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'check_join':
        await query.edit_message_text("ကျေးဇူးတင်ပါတယ်။ သီချင်းအမည်ရိုက်ထည့်ပြီး ရှာဖွေနိုင်ပါပြီ။ 🎶")
    elif query.data.startswith('dl_'):
        video_id = query.data.split('_')[1]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        status_msg = await query.message.reply_text("Audio အဖြစ်ပြောင်းနေပါတယ်။ ခဏစောင့်ပါ... 🎧")
        try:
            ydl_opts = {'format': 'bestaudio/best', 'outtmpl': f'downloads/{video_id}.%(ext)s',
                        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                title = info.get('title', 'Unknown Title')
                file_path = f"downloads/{video_id}.mp3"
                with open(file_path, 'rb') as audio:
                    await context.bot.send_audio(chat_id=update.effective_chat.id, audio=audio, title=title)
                if os.path.exists(file_path): os.remove(file_path)
                await status_msg.delete()
        except:
            await query.message.reply_text("အဆင်မပြေဖြစ်သွားပါတယ်။ ပြန်စမ်းကြည့်ပါ။")

async def search_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text
    with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
        try:
            results = ydl.extract_info(f"ytsearch5:{user_query}", download=False)['entries']
            if not results: return await update.message.reply_text("ရှာမတွေ့ပါ။")
            keyboard = []
            response_text = "🔎 ရှာတွေ့သော သီချင်းများ - \n\n"
            for i, video in enumerate(results):
                title, vid = video.get('title'), video.get('id')
                response_text += f"{i+1}. {title}\n"
                keyboard.append([InlineKeyboardButton(f"{i+1}. {title[:30]}...", callback_data=f"dl_{vid}")])
            await update.message.reply_text(response_text, reply_markup=InlineKeyboardMarkup(keyboard))
        except: await update.message.reply_text("Error ဖြစ်သွားပါတယ်။")

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
