import os
import asyncio
import aiohttp
from typing import List, Dict
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

# Render ရဲ့ Environment Variables ကနေ လုံခြုံစွာ ယူသုံးခြင်း
TOKEN = os.environ.get("BOT_TOKEN")
SIGHTENGINE_API_USER = os.environ.get("SIGHTENGINE_API_USER")
SIGHTENGINE_API_SECRET = os.environ.get("SIGHTENGINE_API_SECRET")

# Network ချိတ်ဆက်မှု Timeout နဲ့ Error များကို ကြံ့ခိုင်စေရန် Session တည်ဆောက်ခြင်း
session = AiohttpSession(timeout=60)
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()

# Album/MediaGroup များကို စုဆောင်းရန် Cache Storage
album_cache: Dict[str, List[types.Message]] = {}
album_locks: Dict[str, asyncio.Lock] = {}

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

async def check_nsfw_file(file_bytes: bytes) -> bool:
    if not SIGHTENGINE_API_USER or not SIGHTENGINE_API_SECRET:
        return False
        
    try:
        url = 'https://api.sightengine.com/1.0/check.json'
        data = aiohttp.FormData()
        data.add_field('media', file_bytes, filename='photo.jpg', content_type='image/jpeg')
        data.add_field('models', 'nudity-2.1,wad')
        data.add_field('api_user', SIGHTENGINE_API_USER)
        data.add_field('api_secret', SIGHTENGINE_API_SECRET)

        async with aiohttp.ClientSession() as session_api:
            async with session_api.post(url, data=data) as response:
                res_data = await response.json()
                
                if res_data.get('status') == 'success':
                    nudity = res_data.get('nudity', {})
                    safe_score = nudity.get('safe', 1.0)
                    raw_score = nudity.get('raw', 0.0)
                    partial_score = nudity.get('partial', 0.0)
                    
                    if safe_score < 0.4 or raw_score > 0.5 or partial_score > 0.6:
                        return True
                else:
                    return False
    except Exception as e:
        print(f"NSFW File Check Exception: {e}")
        return False
        
    return False

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

# ပုံတစ်ပုံချင်းစီ သို့မဟုတ် Album များကို စနစ်တကျ စုစည်းပြီး တင်ပေးမယ့် Handler
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    # အကယ်၍ Album (Media Group) ဖြစ်နေလျှင်
    if message.media_group_id:
        media_group_id = message.media_group_id
        
        if media_group_id not in album_cache:
            album_cache[media_group_id] = []
            album_locks[media_group_id] = asyncio.Lock()
            
        async with album_locks[media_group_id]:
            album_cache[media_group_id].append(message)
            
        # Album ရဲ့ ပထမဆုံး Message ကိုပဲ စုဆောင်းချိန် ခေတ္တစောင့်ဆိုင်းစေခြင်း
        if len(album_cache[media_group_id]) == 1:
            await asyncio.sleep(1.5)  # ပုံအားလုံး ဝင်လာစေရန် ၁.၅ စက္ကန့် စောင့်ခြင်း
            
            async with album_locks[media_group_id]:
                messages = album_cache.pop(media_group_id)
                del album_locks[media_group_id]
                
            # ၁။ မိုက်ရိုင်းစာသား စစ်ဆေးခြင်း
            caption_text = next((m.caption for m in messages if m.caption), "")
            matched_word = find_bad_word(caption_text)
            if matched_word:
                await messages[0].reply(f"⚠️ စာထဲတွင် မိုက်ရိုင်းသော စာသား ဥပမာ ''{matched_word}'' ပါဝင်နေသဖြင့် တင်၍မရပါ။")
                return

            # ၂။ Album ထဲမှ ပုံများကို NSFW စစ်ဆေးခြင်း
            media_list = []
            for idx, msg in enumerate(messages):
                photo = msg.photo[-1]
                file = await bot.get_file(photo.file_id)
                file_io = await bot.download_file(file.file_path)
                file_bytes = file_io.read()
                
                is_nsfw = await check_nsfw_file(file_bytes)
                if is_nsfw:
                    await msg.reply("⚠️ တင်ပြလာသော ပုံများတွင် မသင့်လျော်သော အကြောင်းအရာ (NSFW) ပါဝင်နေသဖြင့် တင်၍မရပါ။")
                    return
                
                # ပထမဆုံးပုံမှာပဲ Caption ထည့်ပေးရန်
                cap = msg.caption if idx == 0 else None
                media_list.append(InputMediaPhoto(media=photo.file_id, caption=cap))

            CHANNEL_ID = "@ydbumailbox"
            try:
                sent_msgs = await bot.send_media_group(chat_id=CHANNEL_ID, media=media_list)
                
                # ပို့စ်ဖျက်ရန် Button အတွက် Msg ID များကို စုစည်းခြင်း
                msg_ids = ",".join([str(m.message_id) for m in sent_msgs])
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🗑 ဤ Album ကို ဖျက်မည်", callback_data=f"deletegroup_{msg_ids}")]
                ])
                await messages[0].reply("✅ ပို့စ်များကို Album အဖြစ် Channel သို့ တင်ပြီးပါပြီ။", reply_markup=keyboard)
            except Exception as e:
                print(f"MediaGroup handle error: {e}")
                await messages[0].reply("⚠️ ချိတ်ဆက်မှု ခဏတာ အားနည်းသွားပါသဖြင့် ကျေးဇူးပြု၍ တစ်ချက်လောက် ထပ်ပို့ပေးပါရှင့်။")
        return

    # ပုံတစ်ပုံတည်း သီးသန့် ပို့ထားလျှင်
    caption_text = message.caption or ""
    matched_word = find_bad_word(caption_text)
    if matched_word:
        await message.reply(f"⚠️ စာထဲတွင် မိုက်ရိုင်းသော စာသား ဥပမာ ''{matched_word}'' ပါဝင်နေသဖြင့် တင်၍မရပါ။")
        return

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_io = await bot.download_file(file.file_path)
        file_bytes = file_io.read()
        
        is_nsfw = await check_nsfw_file(file_bytes)
        if is_nsfw:
            await message.reply("⚠️ တင်ပြလာသော ပုံသည် မသင့်လျော်သော အကြောင်းအရာ (NSFW) ပါဝင်နေသဖြင့် Channel သို့ တင်၍မရပါ။")
            return

        CHANNEL_ID = "@ydbumailbox"
        sent_msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photo.file_id, caption=message.caption)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 ဤပို့စ်ကို ဖျက်မည်", callback_data=f"delete_{sent_msg.message_id}")]
        ])
        await message.reply("✅ ပို့စ်ကို Channel တင်ပြီးပါပြီ။", reply_markup=keyboard)
    except Exception as e:
        print(f"Single Photo handle error: {e}")
        await message.reply("⚠️ ချိတ်ဆက်မှု ခဏတာ အားနည်းသွားပါသဖြင့် ကျေးဇူးပြု၍ တစ်ချက်လောက် ထပ်ပို့ပေးပါရှင့်။")

@dp.message(F.text)
async def handle_text(message: types.Message):
    if message.text.startswith("/"):
        return

    matched_word = find_bad_word(message.text)
    if matched_word:
        await message.reply(f"⚠️ စာထဲတွင် မိုက်ရိုင်းသော စာသား ဥပမာ ''{matched_word}'' ပါဝင်နေသဖြင့် တင်၍မရပါ။")
        return

    try:
        CHANNEL_ID = "@ydbumailbox"
        sent_msg = await bot.send_message(chat_id=CHANNEL_ID, text=message.text)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 ဤပို့စ်ကို ဖျက်မည်", callback_data=f"delete_{sent_msg.message_id}")]
        ])
        await message.reply("✅ ပို့စ်ကို Channel တင်ပြီးပါပြီ။", reply_markup=keyboard)
    except Exception as e:
        print(f"Text handle error: {e}")
        await message.reply("⚠️ ချိတ်ဆက်မှု ခဏတာ အားနည်းသွားပါသဖြင့် ကျေးဇူးပြု၍ တစ်ချက်လောက် ထပ်ပို့ပေးပါရှင့်။")

# ပုံတစ်ပုံတည်း ဖျက်ခြင်း Callback
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

# Album တစ်ခုလုံးကို ဖျက်ခြင်း Callback
@dp.callback_query(F.data.startswith("deletegroup_"))
async def process_delete_group(callback_query: types.CallbackQuery):
    try:
        msg_ids_str = callback_query.data.split("_")[1]
        msg_ids = [int(i) for i in msg_ids_str.split(",")]
        CHANNEL_ID = "@ydbumailbox"
        
        for m_id in msg_ids:
            try:
                await bot.delete_message(chat_id=CHANNEL_ID, message_id=m_id)
            except Exception:
                pass
                
        await callback_query.message.delete()
        await callback_query.answer("🗑 Album ပို့စ်တစ်ခုလုံးကို အောင်မြင်စွာ ဖျက်လိုက်ပါပြီ။", show_alert=True)
    except Exception as e:
        await callback_query.answer("⚠️ ပို့စ်များ ဖျက်၍ မရပါ (သို့မဟုတ် ဖျက်ပြီးသား ဖြစ်နေပါသည်)။", show_alert=True)

async def main():
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
