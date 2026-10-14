import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ကိုကို့ရဲ့ Bot Token
TOKEN = "8836515568:AAFrcGRN_r3Es_FCv1b4At7hgACarRpMN4U"
bot = Bot(token=TOKEN)
dp = Dispatcher()  # aiogram ဗားရှင်းအသစ်အတွက် ဤကဲ့သို့ ရေးရပါသည်

# ==========================================
# 1. Render အတွက် Port ဖွင့်ပေးမယ့် Dummy Web Server (Port Error ရှင်းရန်)
# ==========================================
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

# ==========================================
# 2. Bot ရဲ့ လုပ်ဆောင်ချက်များ
# ==========================================
@dp.message_handler(content_types=['photo', 'video', 'text'])
async def handle_submission(message: types.Message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🗑 ဖျက်မည် (Delete)", callback_data="delete_post"))

    CHANNEL_ID = "@yadanabonfreedom"

    if message.photo:
        caption = f"ส่งมาจาก: User\n{message.caption or ''}"
        await bot.send_photo(chat_id=CHANNEL_ID, photo=message.photo[-1].file_id, caption=caption, reply_markup=keyboard)
        await message.reply("✅ ပို့စ်ကို Channel တင်ပြီးပါပြီ။", reply_markup=keyboard)
    elif message.text:
        text_content = f"ส่งมาจาก: User\n\n{message.text}"
        await bot.send_message(chat_id=CHANNEL_ID, text=text_content, reply_markup=keyboard)
        await message.reply("✅ ပို့စ်ကို Channel တင်ပြီးပါပြီ။", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'delete_post')
async def process_delete(callback_query: types.CallbackQuery):
    try:
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        await callback_query.answer("🗑 ပို့စ်ကို အောင်မြင်စွာ ဖျက်လိုက်ပါပြီ။", show_alert=True)
    except Exception as e:
        await callback_query.answer("⚠️ ပို့စ်ဖျက်၍ မရပါ။", show_alert=True)

# ==========================================
# 3. Main Function
# ==========================================
async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
