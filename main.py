import os
import logging
import yt_dlp
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- ၁။ Render ပေါ်မှာ ၂၄ နာရီ နိုးနေစေဖို့ Web Server ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    # Render အတွက် Port 8080 ကို အသုံးပြုထားပါတယ်
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- ၂။ CONFIGURATION ---
# Token ကို အမှန်ပြင်ပေးထားပါတယ် (နောက်ဆုံးက 'U' ကို ဖြုတ်ထားပါတယ်)
TOKEN = '8750923349:AAHsRNgP_f-o1p5-fXnTjkY0s2w8-6wh41'

# သင့် Channel အချက်အလက်များ
CHANNEL_URL = "https://t.me/music002234"
CHANNEL_ID = "@music002234" 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ၃။ START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Join Channel 📢", url=CHANNEL_URL)],
        [InlineKeyboardButton("Join ပြီးပါပြီ ✅", callback_data='check_join')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "မင်္ဂလာပါ! သီချင်းနားထောင်ဖို့ အောက်က Channel ကို အရင် Join ပေးပါနော်။ ❤️",
        reply_markup=reply_markup
    )

# --- ၄။ BUTTON HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    await query.answer()

    if query.data == 'check_join':
        await query.edit_message_text("ကျေးဇူးတင်ပါတယ်။ အခု သီချင်းအမည် ဒါမှမဟုတ် အဆိုတော်အမည်ကို ရိုက်ထည့်ပြီး ရှာဖွေနိုင်ပါပြီ။ 🎶")

    elif query.data.startswith('dl_'):
        video_id = query.data.split('_')[1]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        status_msg = await query.message.reply_text("သီချင်းကို Audio အဖြစ်ပြောင်းလဲနေပါတယ်။ ခဏလေးစောင့်ပေးပါ... 🎧")

        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'downloads/{video_id}.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                title = info.get('title', 'Unknown Title')
                file_path = f"downloads/{video_id}.mp3"

                # အသုံးပြုသူထံ Audio ပို့ခြင်း
                with open(file_path, 'rb') as audio:
                    await context.bot.send_audio(
                        chat_id=update.effective_chat.id,
                        audio=audio,
                        title=title,
                        caption=f"🎵 {title}\n🔥 Downloaded via Music Bot"
                    )
                
                # Channel သို့ စာပို့ခြင်း (Admin ခန့်ထားမှ အလုပ်လုပ်ပါမည်)
                try:
                    await context.bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=f"👤 {user.first_name} က အခု '{title}' ကို နားထောင်နေပါတယ်။ 🎧"
                    )
                except:
                    pass

                if os.path.exists(file_path):
                    os.remove(file_path)
                await status_msg.delete()

        except Exception as e:
            await query.message.reply_text("သီချင်းပြောင်းလဲရာမှာ အဆင်မပြေဖြစ်သွားပါတယ်။ နောက်တစ်ခေါက် ပြန်စမ်းကြည့်ပါ။")

# --- ၅။ SONG SEARCH (သီချင်း ၅ ပုဒ် ရှာပေးခြင်း) ---
async def search_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text
    ydl_opts = {'quiet': True, 'noplaylist': True}
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            results = ydl.extract_info(f"ytsearch5:{user_query}", download=False)['entries']
            if not results:
                await update.message.reply_text("သီချင်းရှာမတွေ့ပါဘူး။ အမည်မှန်ရဲ့လား ပြန်စစ်ပေးပါ။")
                return

            keyboard = []
            response_text = "🔎 သင်ရှာဖွေထားတဲ့ သီချင်း ၅ ပုဒ် တွေ့ရှိပါတယ် - \n\n"
            
            for i, video in enumerate(results):
                title = video.get('title')
                vid = video.get('id')
                response_text += f"{i+1}. {title}\n"
                keyboard.append([InlineKeyboardButton(f"{i+1}. {title[:30]}...", callback_data=f"dl_{vid}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(response_text, reply_markup=reply_markup)
            
        except Exception:
            await update.message.reply_text("ရှာဖွေမှု အဆင်မပြေပါ။ ခဏနေမှ ပြန်ကြိုးစားပါ။")

# --- ၆။ MAIN RUNNER ---
def main():
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    # Flask server စတင်နှိုးခြင်း (Keep Alive)
    keep_alive()

    app_bot = Application.builder().token(TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_song))

    print("Bot is starting...")
    app_bot.run_polling()

if __name__ == '__main__':
    main()
