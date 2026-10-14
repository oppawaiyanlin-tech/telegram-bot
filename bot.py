import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = '8836515568:AAEXvKfeOQA5pgogl1cRyvhdofGKemgHQSU'
CHANNEL_ID = '@yadanabonfreedom'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# User တစ်ဦးချင်းစီရဲ့ ပို့စ်များကို မှတ်ထားရန် (User ID -> List of posts)
user_posts = {}

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply(
        "မင်္ဂလာပါရှင်။ Page မှာ တင်ချင်တဲ့ စာ သို့မဟုတ် ပုံများကို ဤ Bot ထဲသို့ ပို့ပေးပါ။\n\n"
        "သင်တင်ထားသော ပို့စ်များကို ပြန်ကြည့်ရန်နှင့် ဖျက်ရန် **/myposts** ဟု ရိုက်နှိပ်ပါ။"
    )

# ကိုယ်တင်ထားတဲ့ ပို့စ်များကို ကြည့်ရန်နှင့် ဖျက်ရန် Command
@dp.message(Command("myposts"))
async def show_my_posts(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_posts or not user_posts[user_id]:
        await message.reply("ယခုလောလောဆယ်တွင် သင်တင်ထားသော ပို့စ်များ မရှိသေးပါ။")
        return

    builder = InlineKeyboardBuilder()
    for post in user_posts[user_id]:
        # ပို့စ်တစ်ခုချင်းစီအတွက် ဖျက်ရန် ခလုတ်များ ဖန်တီးခြင်း
        preview_text = post['text'][:20] if post['text'] else "ဓာတ်ပုံပို့စ်"
        builder.button(text=f"🗑 ဖျက်ရန်: {preview_text}", callback_data=f"del_user_post_{post['channel_msg_id']}")
    
    builder.adjust(1) # တစ်ကြောင်းချင်းစီ ပေါ်ရန်
    await message.reply("အောက်ပါတို့သည် သင်တင်ထားသော ပို့စ်များ ဖြစ်ပါသည်။ ဖျက်လိုသည့် ပို့စ်ကို နှိပ်ပါ -", reply_markup=builder.as_markup())

# ပို့စ်များကို လက်ခံ၍ Channel သို့ ပို့ပေးခြင်း (Channel တွင် ဖျက်ခလုတ် မပါတော့ပါ)
@dp.message(F.text | F.photo)
async def handle_user_submission(message: types.Message):
    try:
        user_id = message.from_user.id
        sent_message = None
        
        if message.photo:
            photo_file_id = message.photo[-1].file_id
            caption_text = message.caption or ""
            sent_message = await bot.send_photo(
                chat_id=CHANNEL_ID, 
                photo=photo_file_id, 
                caption=caption_text
            )
        elif message.text:
            sent_message = await bot.send_message(
                chat_id=CHANNEL_ID, 
                text=message.text
            )
            
        # User ရဲ့ ဇယားထဲသို့ ပို့စ် အချက်အလက် သိမ်းဆည်းခြင်း
        if user_id not in user_posts:
            user_posts[user_id] = []
            
        user_posts[user_id].append({
            'channel_msg_id': sent_message.message_id,
            'text': message.text or message.caption or ""
        })
            
        await message.reply("ကျေးဇူးတင်ပါတယ်ရှင့်။ သင့်ပို့စ်ကို Page ထဲသို့ အောင်မြင်စွာ တင်ပြီးပါပြီ။ ပြန်ဖျက်လိုပါက **/myposts** ဟု ရိုက်ပါ။")
    except Exception as e:
        print(f"Error: {e}")
        await message.reply("ပို့စ်တင်ရာတွင် အမှားအယွင်း ရှိသွားပါသည်။ Bot သည် Channel တွင် Admin ဖြစ်မဖြစ် စစ်ဆေးပါ။")

# User ရဲ့ Chatbox မှနေ၍ ရွေးချယ်ဖျက်လိုက်သောအခါ
@dp.callback_query(F.data.startswith("del_user_post_"))
async def delete_user_specific_post(callback: types.CallbackQuery):
    try:
        channel_msg_id = int(callback.data.split("_")[3])
        user_id = callback.from_user.id
        
        # Channel ထဲမှ ပို့စ်ကို ဖျက်ပစ်ခြင်း
        await bot.delete_message(chat_id=CHANNEL_ID, message_id=channel_msg_id)
        
        # မှတ်တမ်းထဲမှ ဖယ်ရှားခြင်း
        if user_id in user_posts:
            user_posts[user_id] = [p for p in user_posts[user_id] if p['channel_msg_id'] != channel_msg_id]
            
        await callback.message.edit_text("✅ ရွေးချယ်ထားသော ပို့စ်ကို Channel ထဲမှ အောင်မြင်စွာ ဖျက်လိုက်ပါပြီရှင်။")
    except Exception as e:
        print(f"Error: {e}")
        await callback.answer("ဒီပို့စ်ကို ဖျက်၍ မရတော့ပါ (သို့မဟုတ် ဖျက်ပြီးသား ဖြစ်နေပါသည်)။", show_alert=True)

async def main():
    print("Bot စတင်ပွင့်နေပါပြီ...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())