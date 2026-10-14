
import os
import io
import uuid
import asyncio
import time

from typing import Dict, List, Optional

import aiohttp
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
    raise RuntimeError("Sightengine credentials or Workflow ID are missing!")


# =========================================================
# 2. BOT SETUP
# =========================================================

session = AiohttpSession(timeout=60)
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()


# =========================================================
# 3. STORAGE
# =========================================================

album_cache: Dict[str, List[types.Message]] = {}
album_locks: Dict[str, asyncio.Lock] = {}
album_tasks: Dict[str, asyncio.Task] = {}
album_last_seen: Dict[str, float] = {}

# Status messages shown while albums are being checked.
album_status_messages: Dict[str, types.Message] = {}

# Store Telegram channel message IDs for album deletion.
delete_groups: Dict[str, List[int]] = {}


# =========================================================
# 4. USER MESSAGES
# =========================================================

CHECKING_TEXT = (
    "⏳ ခဏစောင့်ပေးပါရှင့်။ သင့်ပို့စ်တွင် "
    "အများပြည်သူအတွက် မသင့်လျော်သော အကြောင်းအရာများ "
    "ပါဝင်ခြင်းရှိ၊ မရှိ စစ်ဆေးနေပါသည်။"
)

SUCCESS_TEXT = "✅ ပို့စ်ကို Channel သို့ တင်ပြီးပါပြီ။"

REJECT_TEXT = (
    "⚠️ Mailboxသည် မသင့်လျော်သောပုံများ လက်မခံပါ။ "
    "အခြားပုံတစ်ပုံကို ပေးပို့ပေးပါရှင့်။"
)

ERROR_TEXT = (
    "⚠️ ပုံကို စစ်ဆေးရာတွင် ယာယီအမှားဖြစ်နေပါသည်။ "
    "ကျေးဇူးပြု၍ ခဏအကြာတွင် ပြန်ပို့ပေးပါရှင့်။"
)


async def delete_status_message(message: Optional[types.Message]):
    """Delete a temporary checking message safely."""

    if message is None:
        return

    try:
        await message.delete()
    except Exception as error:
        print("Status message deletion error:", repr(error))


async def reply_final_result(
    original_message: types.Message,
    status_message: Optional[types.Message],
    text: str,
    keyboard: Optional[InlineKeyboardMarkup] = None,
):
    """Remove checking message, then send the final result."""

    await delete_status_message(status_message)

    try:
        await original_message.reply(
            text,
            reply_markup=keyboard,
        )
    except Exception as error:
        print("Final reply error:", repr(error))


# =========================================================
# 5. BAD WORD FILTER
# =========================================================

BAD_WORDS = [
    "လီး", "စက်ပက်", "စောက်ဖုတ်", "စောက်ဖုတ်ပြဲမ",
    "မသာမ", "ဖာသည်မ", "မအေလိုး", "ခွေးမသား",
    "လီးပဲ", "ကိုယ်မေကိုလိုး", "နှမလိုး", "ငါလိုးမသား",
    "မင်းညီမငါလိုး", "မင်းအမေငါလိုး",
    "တစ်ဆွေလုံးတစ်မျိုးလုံးငါလိုး", "kmkl", "mal",
    "lee", "leee", "leeee", "စပ", "ခွေးတတောင်းစားမ",
    "လီးစုပ်", "မှုတ်ပေး", "စမူ", "စောက်ပက်",
    "ခွေးလိုးမသား", "လိုးမလား", "လိုးမယ်",
    "လိုးချင်တယ်", "ကုန်းပေးမယ်", "ဖင်ချ", "ဖင်ခံ",
    "ဖင်လိုး", "စောက်စိ", "စောက်ချီး", "ချီးပဲ",
    "လပြွတ်ပဲ", "လဥပဲ", "လီးတောင်နေတယ်", "လချီး",
    "ဂွေးဥ", "ဂွေးစိ", "နို့စို့ချင်တယ်",
    "နို့ကိုင်ချင်တယ်", "fuck", "shit", "bitch", "asshole",
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
# 6. RENDER WEB SERVER
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
# 7. SIGHTENGINE WORKFLOW
# =========================================================

async def check_nsfw_file(file_bytes: bytes) -> bool:
    """
    True  = block the image
    False = Workflow explicitly accepted the image

    Uses Sightengine Workflow only.
    Errors and unknown actions fail closed.
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
                    print("Sightengine HTTP error:", response_text[:1000])
                    return True

                try:
                    result = await response.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError):
                    print("Sightengine returned invalid JSON.")
                    return True

                if result.get("status") != "success":
                    print(
                        "Sightengine API error:",
                        result.get("error", "Unknown error"),
                    )
                    return True

                summary = result.get("summary")

                if not isinstance(summary, dict):
                    print("Sightengine summary missing.")
                    return True

                action = summary.get("action")
                print("Sightengine Workflow action:", action)

                if action == "accept":
                    return False

                if action == "reject":
                    return True

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


async def moderate_photo(message: types.Message) -> bool:
    """Return True only when the Workflow accepts the photo."""

    try:
        if not message.photo:
            return False

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
        "မင်္ဂလာပါရှင့်။\n"
        "ဤဘော့တ်မှတစ်ဆင့် Channel သို့ ပုံနှင့်စာများ "
        "ပေးပို့တင်နိုင်ပါသည်။\n"
        "ပုံများကို Sightengine Workflow ဖြင့် စစ်ဆေးပါသည်။"
    )


@dp.message(F.text.startswith("/"))
async def handle_other_commands(message: types.Message):
    return


# =========================================================
# 9. PROCESS ALBUM
# =========================================================

async def process_album_after_delay(media_group_id: str):
    messages: List[types.Message] = []
    status_message: Optional[types.Message] = None

    try:
        loop = asyncio.get_running_loop()

        # Wait until no new album item arrives for 2 seconds.
        while True:
            await asyncio.sleep(0.5)

            last_seen = album_last_seen.get(media_group_id)

            if last_seen is None:
                return

            if loop.time() - last_seen >= 2.0:
                break

        lock = album_locks.get(media_group_id)

        if lock is None:
            return

        async with lock:
            messages = album_cache.pop(media_group_id, [])
            status_message = album_status_messages.pop(
                media_group_id, None
            )

        if not messages:
            await delete_status_message(status_message)
            return

        messages.sort(key=lambda item: item.message_id)

        # Find the caption, regardless of which album item contains it.
        caption_text = next(
            (item.caption for item in messages if item.caption),
            "",
        )

        matched_word = find_bad_word(caption_text)

        if matched_word:
            await reply_final_result(
                messages[0],
                status_message,
                f"⚠️ စာထဲတွင် မသင့်လျော်သော စာသား "
                f"'{matched_word}' ပါဝင်နေသဖြင့် ပို့စ်ကို မတင်ပါ။",
            )
            return

        if len(messages) < 2 or len(messages) > 10:
            await reply_final_result(
                messages[0],
                status_message,
                "⚠️ Album ပုံအရေအတွက် မမှန်ပါ။ "
                "ပုံ ၂ ပုံမှ ၁၀ ပုံအထိ Album အဖြစ် ပေးပို့ပါ။",
            )
            return

        # Check every image before publishing any image.
        for index, msg in enumerate(messages, start=1):
            print(
                f"Checking album {media_group_id}: "
                f"{index}/{len(messages)}"
            )

            accepted = await moderate_photo(msg)

            if not accepted:
                await reply_final_result(
                    messages[0],
                    status_message,
                    REJECT_TEXT,
                )
                return

        # Put caption on the first image only.
        media_list = []

        for index, msg in enumerate(messages):
            media_list.append(
                InputMediaPhoto(
                    media=msg.photo[-1].file_id,
                    caption=caption_text if index == 0 else None,
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

        await reply_final_result(
            messages[0],
            status_message,
            SUCCESS_TEXT,
            keyboard,
        )

    except asyncio.CancelledError:
        raise

    except Exception as error:
        print(
            f"Album processing error ({media_group_id}): {error!r}"
        )

        if not status_message:
            status_message = album_status_messages.get(media_group_id)

        if not messages:
            messages = album_cache.get(media_group_id, [])

        if messages:
            await reply_final_result(
                messages[0],
                status_message,
                ERROR_TEXT,
            )
        else:
            await delete_status_message(status_message)

    finally:
        album_cache.pop(media_group_id, None)
        album_last_seen.pop(media_group_id, None)
        album_locks.pop(media_group_id, None)
        album_tasks.pop(media_group_id, None)
        album_status_messages.pop(media_group_id, None)


# =========================================================
# 10. PHOTO HANDLER: ALBUM AND SINGLE PHOTO
# =========================================================

@dp.message(F.photo)
async def handle_photo(message: types.Message):

    # -----------------------------------------------------
    # ALBUM
    # -----------------------------------------------------

    if message.media_group_id:
        group_id = message.media_group_id
        loop = asyncio.get_running_loop()

        if group_id not in album_cache:
            album_cache[group_id] = []
            album_locks[group_id] = asyncio.Lock()

        async with album_locks[group_id]:
            album_cache[group_id].append(message)
            album_last_seen[group_id] = loop.time()

            # Show the checking message once per album.
            if group_id not in album_status_messages:
                try:
                    status = await message.reply(CHECKING_TEXT)
                    album_status_messages[group_id] = status
                except Exception as error:
                    print("Album status message error:", repr(error))

            # Start one collector task per album.
            # Do not cancel/restart it when another image arrives.
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
            f"'{matched_word}' ပါဝင်နေသဖြင့် ပို့စ်ကို မတင်ပါ။"
        )
        return

    status_message = None

    try:
        status_message = await message.reply(CHECKING_TEXT)

        accepted = await moderate_photo(message)

        if not accepted:
            await reply_final_result(
                message,
                status_message,
                REJECT_TEXT,
            )
            return

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

        await reply_final_result(
            message,
            status_message,
            SUCCESS_TEXT,
            keyboard,
        )

    except Exception as error:
        print("Single photo handler error:", repr(error))

        await reply_final_result(
            message,
            status_message,
            ERROR_TEXT,
        )


# =========================================================
# 11. TEXT MESSAGE HANDLER
# =========================================================

@dp.message(F.text)
async def handle_text(message: types.Message):

    if message.text.startswith("/"):
        return

    matched_word = find_bad_word(message.text)

    if matched_word:
        await message.reply(
            f"⚠️ စာထဲတွင် မသင့်လျော်သော စာသား "
            f"'{matched_word}' ပါဝင်နေသဖြင့် ပို့စ်ကို မတင်ပါ။"
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
            SUCCESS_TEXT,
            reply_markup=keyboard,
        )

    except Exception as error:
        print("Text publishing error:", repr(error))
        await message.reply(
            "⚠️ စာသားကို Channel သို့ တင်မရပါ။ "
            "Render Logs နှင့် Bot Admin Permission ကို စစ်ပါ။"
        )


# =========================================================
# 12. DELETE SINGLE POST
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
        print("Delete single post error:", repr(error))

        await callback.answer(
            "⚠️ ပို့စ်ကို ဖျက်မရပါ။ "
            "Permission နှင့် ပို့စ်အခြေအနေကို စစ်ဆေးပါ။",
            show_alert=True,
        )


# =========================================================
# 13. DELETE ALBUM
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
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
