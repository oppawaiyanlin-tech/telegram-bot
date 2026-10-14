import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ကိုကို့ရဲ့ Bot Token
TOKEN = "8836515568:AAFrcGRN_r3Es_FCv1b4At7hgACarRpMN4U"
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

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
# 2. Bot ရဲ့ အဓိက လုပ်ဆောင်ချက်များ (Submission, Page ပုံစံပြောင်းခြင်း နှင့် Delete Button)
# ==========================================
@dp.message_handler(content_types=['photo', 'video', 'text'])
async def handle_submission(message: types.Message):
    # Bot ကို Private မှာ ပို့လာတာကို Channel ဆီ Page ပုံစံနဲ့ တင်ပေးမယ့် logic
    # User ကိုယ်တိုင် ဖျက်လို့ရမယ့် Delete Button ထည့်သွင်းခြင်း
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🗑 ဖျက်မည် (Delete)", callback_data="delete_post"))

    # Channel ID (ကိုကို့ရဲ့ channel username သို့မဟုတ် id ထည့်ရန်)
    CHANNEL_ID = "@yadanabonfreedom"

    if message.photo:
        caption = f"ส่งมาจาก: User\n{message.caption or ''}"
        sent_msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=message.photo[-1].file_id, caption=caption, reply_markup=keyboard)
        await message.reply("✅ ပို့စ်ကို Channel တင်ပြီးပါပြီ။ ဖျက်ချင်ရင် အောက်ပါခလုတ်ကို သုံးပါ။", reply_markup=keyboard)
    elif message.text:
        text_content = f"ส่งมาจาก: User\n\n{message.text}"
        sent_msg = await bot.send_message(chat_id=CHANNEL_ID, text=text_content, reply_markup=keyboard)
        await message.reply("✅ ပို့စ်ကို Channel တင်ပြီးပါပြီ။", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'delete_post')
async def process_delete(callback_query: types.CallbackQuery):
    try:
        # Channel ထဲက ပို့စ်ကို ဖျက်ရန်
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        await callback_query.answer("🗑 ပို့စ်ကို အောင်မြင်စွာ ဖျက်လိုက်ပါပြီ။", show_alert=True)
    except Exception as e:
        await callback_query.answer("⚠️ ပို့စ်ဖျက်၍ မရပါ (သို့မဟုတ် ဖျက်ပြီးသား ဖြစ်နေပါသည်)။", show_alert=True)

# ==========================================
# 3. Main Function (Web Server နဲ့ Bot ကို တပြိုင်နက် Run ရန်)
# ==========================================
async def main():
    # Render အတွက် Web Server ကို အရင်စတင်မယ်
    await start_web_server()
    
    # Telegram Bot ကို စတင်မယ်
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
