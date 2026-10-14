import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

# Bot Token နဲ့ Sightengine API Credentials
TOKEN = "8836515568:AAEXvKfeOQA5pgogl1cRyvhdofGKemgHQSU"
CHANNEL_ID = "@yadanabonfreedom"

# Sightengine API Key များ
SIGHTENGINE_API_USER = "1243376243"
SIGHTENGINE_API_SECRET = "44FbxJmUhnUP8a5sCD3yfQUeZm6CQrSa"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ပို့စ်များကို သိမ်းဆည်းရန် Dictionary (User တစ်ဦးချင်းစီရဲ့ ပို့စ်များဖျက်ရန်)
user_posts = {}

# Sightengine ဖြင့် ပုံကို စစ်ဆေးမယ့် Function
async def check_image_safety(file_url: str) -> bool:
    url = "https://api.sightengine.com/1.0/check.json"
    params = {
        'url': file_url,
        'models': 'nudity-2.0,wad,gore',  # ညစ်ညမ်းမှု၊ လက်နက်၊ အကြမ်းဖက်/သွေးထွက်သံယိုမှု စစ်ဆေးရန်
        'api_user': SIGHTENGINE_API_USER,
        'api_secret': SIGHTENGINE_API_SECRET,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                
                # Nudity (ညစ်ညမ်းမှု) စစ်ဆေးခြင်း
                nudity = data.get('nudity', {})
                if nudity.get('sexual_activity', 0) > 0.5 or nudity.get('sexual_display', 0) > 0.5 or nudity.get('erotica', 0) > 0.6:
                    return False # မသင့်လျော်ပါ
                
                # Gore / Violence (အကြမ်းဖက်မှု/သွေးထွက်သံယိုမှု) စစ်ဆေးခြင်း
                gore = data.get('gore', {})
                if gore.get('prob', 0) > 0.5:
                    return False # မသင့်လျော်ပါ
                    
                return True # သန့်ရှင်းသည် (Safe ဖြစ်သည်)
            
    return True # API အလုပ်မလုပ်ရင် ပုံမှန်အတိုင်း လွှတ်ပေးမည်

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("မင်္ဂလာပါ ကိုကို့ရဲ့ Submission Bot မှ ကြိုဆိုပါတယ်။ ပုံ၊ ဗီဒီယို သို့မဟုတ် စာသားများ ပို့နိုင်ပါပြီ။")

# ပုံ သို့မဟုတ် ဗီဒီယို လက်ခံစစ်ဆေးခြင်း
@dp.message(F.photo | F.video)
async def media_handler(message: types.Message):
    await message.answer("🔍 ပုံ/ဗီဒီယိုကို စစ်ဆေးနေပါပြီ...")
    
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id

    # Telegram ကနေ ဖိုင်လင့်ခ် ရယူခြင်း
    file = await bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"
    
    # ပုံဖြစ်ပါက Sightengine ဖြင့် စစ်ဆေးမည်
    if message.photo:
        is_safe = await check_image_safety(file_url)
        if not is_safe:
            await message.answer("❌ တောင်းပန်ပါတယ်၊ ဤပုံတွင် မသင့်လျော်သော ညစ်ညမ်းမှု သို့မဟုတ် အကြမ်းဖက်မှုများ ပါဝင်နေသဖြင့် Channel တင်ခွင့်မပြုပါ။")
            return

    # စစ်ဆေးပြီး လုံခြုံပါက Channel သို့ ပို့မည်
    if message.photo:
        sent_msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=file_id, caption=message.caption or "")
    elif message.video:
        sent_msg = await bot.send_video(chat_id=CHANNEL_ID, video=file_id, caption=message.caption or "")

    user_id = message.from_user.id
    if user_id not in user_posts:
        user_posts[user_id] = []
    user_posts[user_id].append(sent_msg.message_id)

    # ဖျက်ရန် ခလုတ်ပါသော အသိပေးချက်
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🗑️ ဤပို့စ်ကို ဖျက်မည်", callback_data=f"del_{sent_msg.message_id}")]
    ])
    await message.answer("✅ ပို့စ်ကို Channel သို့ အောင်မြင်စွာ တင်ပြီးပါပြီ။", reply_markup=keyboard)

# ပို့စ်ဖျက်ရန် Callback Handler
@dp.callback_query(F.data.startswith("del_"))
async def delete_post_handler(callback: types.CallbackQuery):
    msg_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    if user_id in user_posts and msg_id in user_posts[user_id]:
        try:
            await bot.delete_message(chat_id=CHANNEL_ID, message_id=msg_id)
            user_posts[user_id].remove(msg_id)
            await callback.message.edit_text("🗑️ သင့်ပို့စ်ကို အောင်မြင်စွာ ဖျက်ပြီးပါပြီ။")
        except Exception as e:
            await callback.answer("ဖျက်၍မရပါ သို့မဟုတ် ပို့စ်ဟောင်းသွားပါပြီ။", show_alert=True)
    else:
        await callback.answer("ဤပို့စ်ကို ဖျက်ရန် ခွင့်ပြုချက်မရှိပါ။", show_alert=True)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
