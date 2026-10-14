import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8836515568:AAFrcGRN_r3Es_FCv1b4At7hgACarRpMN4U"
bot = Bot(token=TOKEN)
dp = Dispatcher()

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

# Aiogram v3 ပုံစံ Message Handler
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 ဖျက်မည်", callback_data="delete_post")]
    ])
    CHANNEL_ID = "@yadanabonfreedom"
    await bot.send_photo(chat_id=CHANNEL_ID, photo=message.photo[-1].file_id, caption=message.caption, reply_markup=keyboard)
    await message.reply("✅ ပို့စ်တင်ပြီးပါပြီ။", reply_markup=keyboard)

@dp.message(F.text)
async def handle_text(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 ဖျက်မည်", callback_data="delete_post")]
    ])
    CHANNEL_ID = "@yadanabonfreedom"
    await bot.send_message(chat_id=CHANNEL_ID, text=message.text, reply_markup=keyboard)
    await message.reply("✅ ပို့စ်တင်ပြီးပါပြီ။", reply_markup=keyboard)

@dp.callback_query(F.data == "delete_post")
async def process_delete(callback_query: types.CallbackQuery):
    try:
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        await callback_query.answer("🗑 ဖျက်ပြီးပါပြီ။", show_alert=True)
    except:
        await callback_query.answer("⚠️ ဖျက်၍ မရပါ။", show_alert=True)

async def main():
    # Render အတွက် Web Server ကို အရင်စတင်မယ်
    await start_web_server()
    
    # ရှေ့က Webhook ကပ်နေတာကို အလိုအလျောက် ရှင်းထုတ်မည်
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Telegram Bot ကို စတင်မယ်
    await dp.start_polling(bot)
if __name__ == "__main__":
    asyncio.run(main())
