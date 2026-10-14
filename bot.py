import os
import asyncio
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8993727666:AAGbcfOUdLJv_p8Uqm0WiZH6l78SeSC8axM"
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Sightengine API Credentials
SIGHTENGINE_API_USER = "1243376243"
SIGHTENGINE_API_SECRET = "44FbxJmUhnuP8a5sCD3yfQJeZm6CQrSa"

# ကိုကို ပေးထားသော မသင့်လျော်သော စကားလုံးများစာရင်း
BAD_WORDS = [
    "လီး", "စက်ပက်", "စောက်ဖုတ်", "စောက်ဖုတ်ပြဲမ", "မသာမ", "ဖာသည်မ", 
    "မအေလိုး", "ခွေးမသား", "လီးပဲ", "ကိုယ်မေကိုလိုး", "နှမလိုး", "ငါလိုးမသား", 
    "မင်းညီမငါလိုး", "မင်းအမေငါလိုး", "တစ်ဆွေလုံးတစ်မျိုးလုံးငါလိုး", "kmkl", 
    "mal", "lee", "leee", "leeee", "စပ", "ခွေးတတောင်းစားမ", "လီးစုပ်", 
    "မှုတ်ပေး", "စမူ", "စောက်ပက်", "ခွေးလိုးမသား", "လိုးမလား", "လိုးမယ်", 
    "လိုးချင်တယ်", "ကုန်းပေးမယ်", "ဖင်ချ", "ဖင်ခံ", "ဖင်လိုး", "စောက်စိ", 
    "စောက်ချီး", "ချီးပဲ", "လပြွတ်ပဲ", "လဥပဲ", "လီးတောင်နေတယ်", "လချီး", 
    "ဂွေးဥ", "ဂွေးစိ", "နို့စို့ချင်တယ်", "နို့ကိုင်ချင်တယ်", "fuck", "shit", "bitch", "asshole"
]

# Render Port ဖွင့်ရန်
async def handle(request):
    return web.Response(text="Bot is running!")

app = web.Application()
app.add_routes([web.get('/', handle)])

async def start_web_server():
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# Sightengine ဖြင့် ပုံစစ်ဆေးခြင်း
async def check_nsfw(file_url: str) -> bool:
    params = {
        'url': file_url,
        'models': 'nudity,wad',
        'api_user': SIGHTENGINE_API_USER,
        'api_secret': SIGHTENGINE_API_SECRET
    }
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.sightengine.com/1.0/check.json', params=params) as resp:
            data = await resp.json()
            if data.get('status') == 'success':
                nudity = data.get('nudity', {})
                if nudity.get('safe', 1.0) < 0.6:  
                    return True
    return False

# စာသားထဲတွင် မသင့်လျော်သော စကားလုံး ပါဝင်ခြင်း ရှိမရှိ စစ်ဆေးပြီး တွေ့ရှိသော စကားလုံးကို ပြန်ပေးခြင်း
def find_bad_word(text: str) -> str:
    if not text:
        return None
    text_lower = text.lower()
    for word in BAD_WORDS:
        if word in text_lower:
            return word
    return None

@dp.message(F.text.startswith("/"))
async def handle_commands(message: types.Message):
    if message.text == "/start":
        await message.reply("မင်္ဂလာပါရှင့်။ ဤဘော့တ်မှတဆင့် Channel သို့ ပုံနှင့် စာများကို တင်နိုင်ပါသည်။")
    return

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    caption_text = message.caption or ""
    matched_word = find_bad_word(caption_text)
    if matched_word:
        await message.reply(f"⚠️ သူစာထဲမှာ မိုက်ရိုင်းတဲ့စာသား ဥပမာ ''{matched_word}'' ပါဝင်နေသဖြင့်တင်လို့မရပါ။")
        return

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"
    
    is_nsfw = await check_nsfw(file_url)
    if is_nsfw:
        await message.reply("⚠️ တင်ပြလာသော ပုံသည် မသင့်လျော်သော အကြောင်းအရာ (NSFW) ပါဝင်နေသဖြင့် Channel သို့ တင်၍မရပါ။")
        return

    CHANNEL_ID = "@yadanabonfreedom"
    
    sent_msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photo.file_id, caption=message.caption)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 ဤပို့စ်ကို ဖျက်မည်", callback_data=f"delete_{sent_msg.message_id}")]
    ])
    await message.reply("✅ ပို့စ်ကို Channel တင်ပြီးပါပြီ။", reply_markup=keyboard)

@dp.message(F.text)
async def handle_text(message: types.Message):
    if message.text.startswith("/"):
        return

    matched_word = find_bad_word(message.text)
    if matched_word:
        await message.reply(f"⚠️ သူစာထဲမှာ မိုက်ရိုင်းတဲ့စာသား ဥပမာ ''{matched_word}'' ပါဝင်နေသဖြင့်တင်လို့မရပါ။")
        return

    CHANNEL_ID = "@yadanabonfreedom"
    
    sent_msg = await bot.send_message(chat_id=CHANNEL_ID, text=message.text)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 ဤပို့စ်ကို ဖျက်မည်", callback_data=f"delete_{sent_msg.message_id}")]
    ])
    await message.reply("✅ ပို့စ်ကို Channel တင်ပြီးပါပြီ။", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("delete_"))
async def process_delete(callback_query: types.CallbackQuery):
    try:
        target_msg_id = int(callback_query.data.split("_")[1])
        CHANNEL_ID = "@yadanabonfreedom"
        
        await bot.delete_message(chat_id=CHANNEL_ID, message_id=target_msg_id)
        await callback_query.message.delete()
        await callback_query.answer("🗑 ပို့စ်ကို အောင်မြင်စွာ ဖျက်လိုက်ပါပြီ။", show_alert=True)
    except Exception as e:
        await callback_query.answer("⚠️ ပို့စ်ဖျက်၍ မရပါ (သို့မဟုတ် ဖျက်ပြီးသား ဖြစ်နေပါသည်)။", show_alert=True)

async def main():
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
