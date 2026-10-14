import os
import asyncio
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Render ထဲက Environment Variable ကနေ Token များကို လုံခြုံစွာ ယူသုံးခြင်း
TOKEN = os.environ.get("BOT_TOKEN")
SIGHTENGINE_USER = os.environ.get("SIGHTENGINE_USER")
SIGHTENGINE_SECRET = os.environ.get("SIGHTENGINE_SECRET")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# မသင့်လျော်သော စကားလုံးများစာရင်း
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

def find_bad_word(text: str) -> str:
    if not text:
        return None
    text_lower = text.lower()
    for word in BAD_WORDS:
        if word in text_lower:
            return word
    return None

# Sightengine ဖြင့် ပုံကို အထူးတင်းကြပ်စွာ စစ်ဆေးခြင်း (Fail-safe ပါဝင်သည်)
async def check_nsfw_file(file_bytes: bytes) -> bool:
    if not SIGHTENGINE_USER or not SIGHTENGINE_SECRET:
        return False
        
    try:
        url = 'https://api.sightengine.com/1.0/check.json'
        data = aiohttp.FormData()
        data.add_field('media', file_bytes, filename='photo.jpg', content_type='image/jpeg')
        data.add_field('models', 'nudity-2.1')
        data.add_field('api_user', SIGHTENGINE_USER)
        data.add_field('api_secret', SIGHTENGINE_SECRET)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                res_data = await response.json()
                print(f"Sightengine Response: {res_data}")
                if res_data.get('status') == 'success':
                    nudity = res_data.get('nudity', {})
                    raw_score = nudity.get('raw', 0.0)
                    partial_score = nudity.get('partial', 0.0)
                    safe_score = nudity.get('safe', 1.0)
                    
                    # ညစ်ညမ်းမှု အနည်းငယ်ပါတာနဲ့ (သို့မဟုတ် safe score 0.9 ထက်နည်းရင်) တားမည်
                    if raw_score > 0.02 or partial_score > 0.05 or safe_score < 0.90:
                        return True
                else:
                    print(f"Sightengine API Error: {res_data}")
    except Exception as e:
        print(f"NSFW File Check Error: {e}")
    return False

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
        await message.reply(f"⚠️ ပို့စ်စာသားထဲမှာ မိုက်ရိုင်းတဲ့စာသား ဥပမာ ''{matched_word}'' ပါဝင်နေသဖြင့် တင်လို့မရပါ။")
        return

    # Telegram မှ ပုံဖိုင်ကို Bytes အဖြစ် ဒေါင်းလုပ်ဆွဲယူခြင်း
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    file_io = await bot.download_file(file.file_path)
    file_bytes = file_io.read()

    # NSFW စစ်ဆေးခြင်း
    is_nsfw = await check_nsfw_file(file_bytes)
    if is_nsfw:
        await message.reply("⚠️ ပုံထဲတွင် မသင့်လျော်သော (NSFW/Sex) ပါဝင်နေသဖြင့် Channel သို့ တင်ခွင့်မပြုပါ။")
        return

    CHANNEL_ID = "@ydbumailbox"
    sent_msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=file_id, caption=message.caption)

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

    CHANNEL_ID = "@ydbumailbox"
    
    sent_msg = await bot.send_message(chat_id=CHANNEL_ID, text=message.text)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 ဤပို့စ်ကို ဖျက်မည်", callback_data=f"delete_{sent_msg.message_id}")]
    ])
    await message.reply("✅ ပို့စ်ကို Channel တင်ပြီးပါပြီ။", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("delete_"))
async def process_delete(callback_query: types.CallbackQuery):
    try:
        target_msg_id = int(callback_query.data.split("_")[1])
        CHANNEL_ID = "@ydbumailbox"
        
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
