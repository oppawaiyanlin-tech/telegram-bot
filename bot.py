
import os
import io
import uuid
import asyncio
import aiohttp

from typing import List, Dict, Optional
from aiohttp import web

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
)


# =========================================================
# 1. ENVIRONMENT VARIABLES
# =========================================================

TOKEN = os.environ.get("BOT_TOKEN")
SIGHTENGINE_API_USER = os.environ.get("SIGHTENGINE_API_USER")
SIGHTENGINE_API_SECRET = os.environ.get("SIGHTENGINE_API_SECRET")
SIGHTENGINE_WORKFLOW_ID = os.environ.get("SIGHTENGINE_WORKFLOW_ID")

CHANNEL_ID = "@ydbumailbox"

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is missing!")

if not all([
    SIGHTENGINE_API_USER,
    SIGHTENGINE_API_SECRET,
    SIGHTENGINE_WORKFLOW_ID,
]):
    raise RuntimeError(
        "Sightengine API User, API Secret or Workflow ID is missing!"
    )


# =========================================================
# 2. BOT AND DISPATCHER
# =========================================================

session = AiohttpSession(timeout=60)
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()


# =========================================================
# 3. ALBUM AND DELETE STORAGE
# =========================================================

album_cache: Dict[str, List[types.Message]] = {}
album_locks: Dict[str, asyncio.Lock] = {}
album_tasks: Dict[str, asyncio.Task] = {}

# Callback data must remain within Telegram's 64-byte limit.
# Store message IDs on the server instead of placing all IDs
# directly inside callback_data.
delete_groups: Dict[str, List[int]] = {}


# =========================================================
# 4. BAD WORD FILTER
# =========================================================

BAD_WORDS = [
    "လီး", "စက်ပက်", "စောက်ဖုတ်", "စောက်ဖုတ်ပြဲမ", "မသာမ",
    "ဖာသည်မ", "မအေလိုး", "ခွေးမသား", "လီးပဲ", "ကိုယ်မေကိုလိုး",
    "နှမလိုး", "ငါလိုးမသား", "မင်းညီမငါလိုး", "မင်းအမေငါလိုး",
    "တစ်ဆွေလုံးတစ်မျိုးလုံးငါလိုး", "kmkl", "mal", "lee", "leee",
    "leeee", "စပ", "ခွေးတတောင်းစားမ", "လီးစုပ်", "မှုတ်ပေး",
    "စမူ", "စောက်ပက်", "ခွေးလိုးမသား", "လိုးမလား", "လိုးမယ်",
    "လိုးချင်တယ်", "ကုန်းပေးမယ်", "ဖင်ချ", "ဖင်ခံ", "ဖင်လိုး",
    "စောက်စိ", "စောက်ချီး", "ချီးပဲ", "လပြွတ်ပဲ", "လဥပဲ",
    "လီးတောင်နေတယ်", "လချီး", "ဂွေးဥ", "ဂွေးစိ",
    "နို့စို့ချင်တယ်", "နို့ကိုင်ချင်တယ်", "fuck", "shit",
    "bitch", "asshole",
]


def find_bad_word(text: Optional[str]) -> Optional[str]:
    if not text:
        return None

    text_lower = text.lower()

    for word in BAD_WORDS:
        if word.lower() in text_lower:
            return word

    return None


# =========================================================
# 5. RENDER WEB SERVER
# =========================================================

async def handle(request):
    return web.Response(text="Bot is running!")


app = web.Application()
app.add_routes([web.get("/", handle)])


async def start_web_server():
    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)

    await site.start()
    print(f"Web server started on port {port}")


# =========================================================
# 6. SIGHTENGINE WORKFLOW MODERATION
# =========================================================

async def check_nsfw_file(file_bytes: bytes) -> bool:
    """
    True  = Block the image.
    False = Workflow explicitly accepted the image.

    Uses Sightengine Workflow only.
    API errors, unknown actions and workflow mismatches
    are blocked by default.
    """

    url = "https://api.sightengine.com/1.0/check-workflow.json"

    data = aiohttp.FormData()
    data.add_field(
        "media",
        file_bytes,
        filename="photo.jpg",
        content_type="image/jpeg",
    )
    data.add_field("workflow", SIGHTENGINE_WORKFLOW_ID)
    data.add_field("api_user", SIGHTENGINE_API_USER)
    data.add_field("api_secret", SIGHTENGINE_API_SECRET)

    timeout = aiohttp.ClientTimeout(total=60)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as api_session:
            async with api_session.post(url, data=data) as response:

                response_text = await response.text()

                print("Sightengine HTTP status:", response.status)

                if response.status != 200:
                    print(
                        "Sightengine HTTP error:",
                        response_text[:1500],
                    )
                    return True

                try:
                    result = await response.json(
                        content_type=None
                    )
                except (ValueError, aiohttp.ContentTypeError):
                    print("Sightengine returned invalid JSON.")
                    return True

                if result.get("status") != "success":
                    # Do not print API credentials.
                    print(
                        "Sightengine API failure:",
                        result.get("error", "Unknown API error"),
                    )
                    return True

                workflow_info = result.get("workflow") or {}
                returned_workflow_id = workflow_info.get("id")

                # Verify that the configured Workflow was used.
                if returned_workflow_id != SIGHTENGINE_WORKFLOW_ID:
                    print("Sightengine Workflow ID mismatch.")
                    print(
                        "Returned workflow ID:",
                        returned_workflow_id,
                    )
                    return True

                summary = result.get("summary")

                if not isinstance(summary, dict):
                    print("Sightengine response has no valid summary.")
                    return True

                action = summary.get("action")

                print("Sightengine Workflow:", returned_workflow_id)
                print("Sightengine action:", action)
                print(
                    "Reject probability:",
                    summary.get("reject_prob"),
                )
                print(
                    "Reject reasons:",
                    summary.get("reject_reason"),
                )

                if action == "accept":
                    return False

                if action == "reject":
                    return True

                # Missing or unknown action: block by default.
                print("Unknown Workflow action; blocking image.")
                return True

    except asyncio.TimeoutError:
        print("Sightengine request timed out.")
        return True

    except aiohttp.ClientError as error:
        print("Sightengine network error:", repr(error))
        return True

    except Exception as error:
        print("Sightengine unexpected error:", repr(error))
        return True


# =========================================================
# 7. MODERATION HELPER
# =========================================================

async def moderate_photo(message: types.Message) -> bool:
    """
    Returns True only when the image is explicitly accepted.
    """

    if not message.photo:
        return False

    try:
        photo = message.photo[-1]
        file_io = io.BytesIO()

        await bot.download(photo, destination=file_io)
        file_bytes = file_io.getvalue()

        if not file_bytes:
            print("Downloaded photo is empty.")
            return False

        blocked = await check_nsfw_file(file_bytes)

        return not blocked

    except Exception as error:
        print("Photo moderation error:", repr(error))
        return False


# =========================================================
# 8. START COMMAND
# =========================================================

@dp.message(F.text == "/start")
async def handle_start(message: types.Message):
    await message.reply(
        "မင်္ဂလာပါရှင့်။\n"
        "ဤဘော့တ်မှတစ်ဆင့် Channel သို့ ပုံနှင့်စာများ "
        "ပေးပို့တင်နိုင်ပါသည်။\n"
        "ပုံများကို Sightengine Workflow ဖြင့် စစ်ဆေးပါသည်။"
    )


# =========================================================
# 9. OTHER COMMANDS
# =========================================================

@dp.message(F.text.startswith("/"))
async def handle_other_commands(message: types.Message):
    return


# =========================================================
# 10. ALBUM COLLECTION
# =========================================================

async def process_album_after_delay(media_group_id: str):
    """
    Wait briefly to collect album messages, then moderate
    every photo before publishing any of them.
    """

    try:
        await asyncio.sleep(2.0)

        lock = album_locks.get(media_group_id)

        if lock is None:
            return

        async with lock:
            messages = album_cache.pop(media_group_id, [])

        if not messages:
            return

        messages.sort(key=lambda item: item.message_id)

        caption_text = next(
            (item.caption for item in messages if item.caption),
            "",
        )

        matched_word = find_bad_word(caption_text)

        if matched_word:
            await messages[0].reply(
                f"⚠️ စာထဲတွင် မသင့်လျော်သော စာသား "
                f"ဥပမာ '{matched_word}' ပါဝင်နေသဖြင့် "
                f"တင်၍မရပါ။"
            )
            return

        # Check the whole album before publishing anything.
        for msg in messages:
            accepted = await moderate_photo(msg)

            if not accepted:
                await messages[0].reply(
                    "⚠️ Album ထဲမှ ပုံတစ်ပုံ သို့မဟုတ် "
                    "တစ်ပုံထက်ပိုသောပုံများကို Workflow က "
                    "လက်မခံပါ။ သို့မဟုတ် စစ်ဆေးမှု မအောင်မြင်ပါ။ "
                    "Album တစ်ခုလုံးကို Channel သို့ မတင်ပါ။"
                )
                return

        media_list = []

        for index, msg in enumerate(messages):
            caption = caption_text if index == 0 else None

            media_list.append(
                InputMediaPhoto(
                    media=msg.photo[-1].file_id,
                    caption=caption,
                )
            )

        sent_messages = await bot.send_media_group(
            chat_id=CHANNEL_ID,
            media=media_list,
        )

        group_key = uuid.uuid4().hex[:16]

        delete_groups[group_key] = [
            sent.message_id for sent in sent_messages
        ]

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🗑 ဤ Album ကို ဖျက်မည်",
                        callback_data=f"deletegroup_{group_key}",
                    )
                ]
            ]
        )

        await messages[0].reply(
            "✅ Workflow စစ်ဆေးမှု အောင်မြင်ပြီး "
            "Album ကို Channel သို့ တင်ပြီးပါပြီ။",
            reply_markup=keyboard,
        )

    except Exception as error:
        print("Album processing error:", repr(error))

    finally:
        album_cache.pop(media_group_id, None)
        album_locks.pop(media_group_id, None)
        album_tasks.pop(media_group_id, None)


@dp.message(F.photo)
async def handle_photo(message: types.Message):

    # -----------------------------------------------------
    # ALBUM
    # -----------------------------------------------------

    if message.media_group_id:
        group_id = message.media_group_id

        if group_id not in album_cache:
            album_cache[group_id] = []
            album_locks[group_id] = asyncio.Lock()

        lock = album_locks[group_id]

        async with lock:
            album_cache[group_id].append(message)

            # Start one collection task per album.
            if group_id not in album_tasks:
                album_tasks[group_id] = asyncio.create_task(
                    process_album_after_delay(group_id)
                )

        return

    # -----------------------------------------------------
    # SINGLE PHOTO
    # -----------------------------------------------------

    caption_text = message.caption or ""

    matched_word = find_bad_word(caption_text)

    if matched_word:
        await message.reply(
            f"⚠️ စာထဲတွင် မသင့်လျော်သော စာသား "
            f"ဥပမာ '{matched_word}' ပါဝင်နေသဖြင့် "
            f"တင်၍မရပါ။"
        )
        return

    accepted = await moderate_photo(message)

    if not accepted:
        await message.reply(
            "⚠️ ပုံကို Sightengine Workflow က Reject လုပ်ထားပါသည် "
            "သို့မဟုတ် စစ်ဆေးမှု မအောင်မြင်ပါ။ "
            "Channel သို့ မတင်ထားပါ။"
        )
        return

    try:
        sent_message = await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=message.photo[-1].file_id,
            caption=message.caption,
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🗑 ဤပို့စ်ကို ဖျက်မည်",
                        callback_data=f"delete_{sent_message.message_id}",
                    )
                ]
            ]
        )

        await message.reply(
            "✅ Workflow စစ်ဆေးမှု အောင်မြင်ပြီး "
            "ပို့စ်ကို Channel သို့ တင်ပြီးပါပြီ။",
            reply_markup=keyboard,
        )

    except Exception as error:
        print("Single photo publishing error:", repr(error))
        await message.reply(
            "⚠️ Channel သို့ တင်မရပါ။ "
            "Bot Admin Permission နှင့် Logs ကို စစ်ဆေးပါ။"
        )


# =========================================================
# 11. TEXT MESSAGES
# =========================================================

@dp.message(F.text)
async def handle_text(message: types.Message):

    if message.text.startswith("/"):
        return

    matched_word = find_bad_word(message.text)

    if matched_word:
        await message.reply(
            f"⚠️ စာထဲတွင် မသင့်လျော်သော စာသား "
            f"ဥပမာ '{matched_word}' ပါဝင်နေသဖြင့် "
            f"တင်၍မရပါ။"
        )
        return

    try:
        sent_message = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message.text,
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🗑 ဤပို့စ်ကို ဖျက်မည်",
                        callback_data=f"delete_{sent_message.message_id}",
                    )
                ]
            ]
        )

        await message.reply(
            "✅ ပို့စ်ကို Channel သို့ တင်ပြီးပါပြီ။",
            reply_markup=keyboard,
        )

    except Exception as error:
        print("Text publishing error:", repr(error))
        await message.reply(
            "⚠️ Channel သို့ တင်မရပါ။ "
            "Bot Admin Permission နှင့် Logs ကို စစ်ဆေးပါ။"
        )


# =========================================================
# 12. DELETE SINGLE CHANNEL POST
# =========================================================

@dp.callback_query(F.data.startswith("delete_"))
async def process_delete(callback: types.CallbackQuery):

    try:
        target_message_id = int(
            callback.data.removeprefix("delete_")
        )

        await bot.delete_message(
            chat_id=CHANNEL_ID,
            message_id=target_message_id,
        )

        await callback.message.delete()
        await callback.answer(
            "🗑 ပို့စ်ကို ဖျက်ပြီးပါပြီ။",
            show_alert=True,
        )

    except Exception as error:
        print("Delete post error:", repr(error))
        await callback.answer(
            "⚠️ ပို့စ်ဖျက်မရပါ။ "
            "ဖျက်ပြီးသားဖြစ်နိုင်သလို Permission လည်း စစ်ပါ။",
            show_alert=True,
        )


# =========================================================
# 13. DELETE WHOLE ALBUM
# =========================================================

@dp.callback_query(F.data.startswith("deletegroup_"))
async def process_delete_group(callback: types.CallbackQuery):

    group_key = callback.data.removeprefix("deletegroup_")
    message_ids = delete_groups.pop(group_key, None)

    if not message_ids:
        await callback.answer(
            "⚠️ Album ဖျက်ရန် အချက်အလက် မရှိတော့ပါ။",
            show_alert=True,
        )
        return

    failed = []

    for message_id in message_ids:
        try:
            await bot.delete_message(
                chat_id=CHANNEL_ID,
                message_id=message_id,
            )
        except Exception as error:
            print(
                "Delete album item error:",
                message_id,
                repr(error),
            )
            failed.append(message_id)

    try:
        await callback.message.delete()
    except Exception:
        pass

    if failed:
        await callback.answer(
            "⚠️ Album ထဲမှ ပို့စ်အချို့ကို ဖျက်မရပါ။",
            show_alert=True,
        )
    else:
        await callback.answer(
            "🗑 Album တစ်ခုလုံးကို ဖျက်ပြီးပါပြီ။",
            show_alert=True,
        )


# =========================================================
# 14. MAIN
# =========================================================

async def main():
    await start_web_server()

    try:
        await bot.delete_webhook(drop_pending_updates=True)

        print("Telegram bot starting...")
        print("Sightengine Workflow moderation enabled.")

        await dp.start_polling(bot)

    finally:
        # Close bot HTTP session when polling stops.
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
