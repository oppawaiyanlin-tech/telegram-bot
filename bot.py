
import asyncio
import io
import os
import re
import uuid
import logging
from dataclasses import dataclass, field

import aiohttp
from aiohttp import web

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
    InputMediaPhoto,
)

# =========================================================
# CONFIGURATION
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "@ydbumailbox").strip()

SIGHTENGINE_API_USER = os.getenv(
    "SIGHTENGINE_API_USER", ""
).strip()

SIGHTENGINE_API_SECRET = os.getenv(
    "SIGHTENGINE_API_SECRET", ""
).strip()

SIGHTENGINE_WORKFLOW_ID = os.getenv(
    "SIGHTENGINE_WORKFLOW_ID", ""
).strip()

SIGHTENGINE_URL = (
    "https://api.sightengine.com/1.0/check-workflow.json"
)

PORT = int(os.getenv("PORT", "10000"))

# စောင့်ဆိုင်းချိန်၊ album စုဆောင်းချိန်
ALBUM_DEBOUNCE_SECONDS = 1.5
ALBUM_MAX_PHOTOS = 10
MAX_IMAGE_SIZE = 15 * 1024 * 1024  # 15 MB

CHECKING_TEXT = (
    "⏳ ခဏစောင့်ပေးပါရှင့်။ သင့်ပို့စ်တွင် "
    "အများပြည်သူအတွက် မသင့်လျော်သော အကြောင်းအရာများ "
    "ပါဝင်ခြင်းရှိ၊ မရှိ စစ်ဆေးနေပါသည်။"
)

REJECT_TEXT = (
    "⚠️ Mailboxသည် မသင့်လျော်သောပုံများ လက်မခံပါ။ "
    "အခြားပုံတစ်ပုံကို ပေးပို့ပေးပါရှင့်။"
)

SUCCESS_TEXT = "✅ ပို့စ်ကို Channel သို့ တင်ပြီးပါပြီ။"

BAD_WORDS = [
    "ငါလိုးမ",
    "လီး",
    "စက်ပက်",
    "စောက်ဖုတ်",
    "စောက်ဖုတ်ပြဲမ",
    "မသာမ",
    "ဖာသည်မ",
    "မအေလိုး",
    "ခွေးမသား",
    "လီးပဲ",
    "ကိုယ်မေကိုလိုး",
    "နှမလိုး",
    "ငါလိုးမသား",
    "မင်းညီမငါလိုး",
    "မင်းအမေငါလိုး",
    "တစ်ဆွေလုံးတစ်မျိုးလုံးငါလိုး",
    "kmkl",
    "mal",
    "lee",
    "leee",
    "leeee",
    "စပ",
    "ခွေးတတောင်းစားမ",
    "လီးစုပ်",
    "မှုတ်ပေး",
    "စမူ",
    "စောက်ပက်",
    "ခွေးလိုးမသား",
    "လိုးမလား",
    "လိုးမယ်",
    "လိုးချင်တယ်",
    "ကုန်းပေးမယ်",
    "ဖင်ချ",
    "ဖင်ခံ",
    "ဖင်လိုး",
    "စောက်စိ",
    "စောက်ချီး",
    "ချီးပဲ",
    "လပြွတ်ပဲ",
    "လဥပဲ",
    "လီးတောင်နေတယ်",
    "လချီး",
    "ဂွေးဥ",
    "ဂွေးစိ",
    "နို့စို့ချင်တယ်",
    "နို့ကိုင်ချင်တယ်",
    "fuck",
    "shit",
    "bitch",
    "asshole",
    "ချေးပါ",
    "နှာဘူး",
    "စမူဆာ",
    "အီးပါ",
    "ခွေးမ",
    "ခွေးသူတောင်းစား",
    "ဆပ္ပတ်",
    "ဖင်လျက်",
    "ဖာခေါင်း",
    "ဖာမ",
    "ဘောမ",
    "အမေလိုး",
    "မအလ",
    "အခြောက်",
    "ထဘီခြုံ",
    "ငါလိုး",
    "ခွေးလိုး",
    "ချီးထုတ်",
    "လီးစား",
    "လီးဘဲ",
    "လိုးမ",
    "မေလိုး",
    "မင်းမေစက်ပက်",
    "မင်းမေမင်းလိုး",
    "ဖေလိုးမ",
    "ဖေလိုး",
    "အဖေလိုး",
    "စောက်ပက်စား",
    "စောက်ကောင်",
    "စောက်ကောင်မ",
    "စောက်ချီးစား",
    "ချီးလိုပဲ",
    "သုတ်ကောင်",
    "တုတ်ကြောင်မ",
    "သေခြင်းဆိုး",
    "ကုလားနာ",
    "သေနာကောင်",
    "ဖွတ်ကျား",
    "စောက်ရူး",
    "သေဂျင်းဇိုးလေး",
    "စောက်မွှေး",
    "လီးပြဲ",
    "ဖာသည်",
    "ဒစ်စုပ်",
    "ငါ့ဒစ်စုပ်",
    "လီးစုပ့",
    "လီးစား",
    "လီးဘဲ",
    "လီးစုပ်",
    "လိုးမ",
    "မေလိုး",
    "ဖေလိုး",
    "အဖေလိုး",
    "စောက်ပက်စား",
    "ချီးလိုပဲ",
    "ထဘီခြုံ",
    "ငါလိုး",
    "ခွေးလိုး",
    "ချီးထုတ်",
    "လီးစား",
    "လီးဘဲ",
    "လီးစုပ်",
    "လီးစား",
    "လီးဘဲ",
    "လိုးမ",
    "မေလိုး",
    "မင်းမေစက်ပက်",
    "မင်းမေမင်းလိုး",
    "ဖေလိုးမ",
    "ဖေလိုး",
    "အဖေလိုး",
    "စောက်ပက်စား",
    "စောက်ကောင်",
    "စောက်ကောင်မ",
    "စောက်ချီးစား",
    "ချီးလိုပဲ",
    "သုတ်ကောင်",
    "တုတ်ကြောင်မ",
    "သေခြင်းဆိုး",
    "ကုလားနာ",
    "သေနာကောင်",
    "ဖွတ်ကျား",
    "စောက်ရူး",
    "သေဂျင်းဇိုးလေး",
    "စောက်မွှေး",
    "လီးပြဲ",
    "ဖာသည်",
    "ဒစ်စုပ်",
    "ငါ့ဒစ်စုပ်",
    "ငါလိုး",
    "ခွေးလိုး",
    "ချီးထုတ်",
    "လီးစား",
    "လီးဘဲ",
    "လိုးမ",
    "မေလိုး",
    "ဖေလိုး",
    "အဖေလိုး",
    "စောက်ပက်စား",
    "စောက်ကောင်",
    "စောက်ကောင်မ",
    "စောက်ချီးစား",
    "ချီးလိုပဲ",
    "သုတ်ကောင်",
    "တုတ်ကြောင်မ",
    "သေခြင်းဆိုး",
    "ကုလားနာ",
    "သေနာကောင်",
    "ဖွတ်ကျား",
    "စောက်ရူး",
    "သေဂျင်းဇိုးလေး",
    "စောက်မွှေး",
    "လီးပြဲ",
    "ဖာသည်",
    "ဒစ်စုပ်",
    "ငါ့ဒစ်စုပ်",
    "မင်းမေစက်ပက်",
    "မင်းမေမင်းလိုး",
    "ဖေလိုးမ",
    "ဖေလိုး",
    "အဖေလိုး",
    "စောက်ပက်စား",
    "စောက်ကောင်",
    "စောက်ကောင်မ",
    "စောက်ချီးစား",
    "ချီးလိုပဲ",
    "သုတ်ကောင်",
    "တုတ်ကြောင်မ",
    "သေခြင်းဆိုး",
    "ကုလားနာ",
    "သေနာကောင်",
    "ဖွတ်ကျား",
    "စောက်ရူး",
    "သေဂျင်းဇိုးလေး",
    "စောက်မွှေး",
    "လီးပြဲ",
    "ဖာသည်",
    "ဒစ်စုပ်",
    "ငါ့ဒစ်စုပ်",
    "လီးစား",
    "လီးဘဲ",
    "လီးစုပ်",
    "လိုးမ",
    "မေလိုး",
    "ဖေလိုး",
    "အဖေလိုး",
    "စောက်ပက်စား",
    "စောက်ကောင်",
    "စောက်ကောင်မ",
    "စောက်ချီးစား",
    "ချီးလိုပဲ",
    "သုတ်ကောင်",
    "တုတ်ကြောင်မ",
    "သေခြင်းဆိုး",
    "ကုလားနာ",
    "သေနာကောင်",
    "ဖွတ်ကျား",
    "စောက်ရူး",
    "သေဂျင်းဇိုးလေး",
    "စောက်မွှေး",
    "လီးပြဲ",
    "ဖာသည်",
    "ဒစ်စုပ်",
    "ငါ့ဒစ်စုပ်",
    "လီးစုပ်",
    "လိုးမ",
    "မေလိုး",
    "ဖေလိုး",
    "အဖေလိုး",
    "စောက်ပက်စား",
    "စောက်ကောင်",
    "စောက်ကောင်မ",
    "စောက်ချီးစား",
    "ချီးလိုပဲ",
    "သုတ်ကောင်",
    "တုတ်ကြောင်မ",
    "သေခြင်းဆိုး",
    "ကုလားနာ",
    "သေနာကောင်",
    "ဖွတ်ကျား",
    "စောက်ရူး",
    "သေဂျင်းဇိုးလေး",
    "စောက်မွှေး",
    "လီးပြဲ",
    "ဖာသည်",
    "ဒစ်စုပ်",
    "ငါ့ဒစ်စုပ်",
]

# ထပ်နေသော စကားလုံးများကို ဖယ်ရှားထားသည်။
BAD_WORDS = list(dict.fromkeys(BAD_WORDS))

# =========================================================
# LOGGING AND BOT
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN ကို Render Environment Variables မှာ ထည့်ပါ။")

if not CHANNEL_ID:
    raise RuntimeError("CHANNEL_ID ကို သတ်မှတ်ပေးပါ။")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Delete button အတွက် memory ထဲမှာ ခဏသိမ်းထားမည့် အချက်အလက်
post_registry = {}

# Album စုဆောင်းရန်
@dataclass
class AlbumState:
    messages: list = field(default_factory=list)
    status_message: Message | None = None
    task: asyncio.Task | None = None


album_states = {}
album_lock = asyncio.Lock()


# =========================================================
# TEXT MODERATION
# =========================================================

def contains_bad_word(text: str | None) -> bool:
    if not text:
        return False

    normalized_text = text.casefold()

    for word in BAD_WORDS:
        if word.casefold() in normalized_text:
            return True

    return False


# =========================================================
# SIGHTENGINE WORKFLOW MODERATION
# =========================================================

async def check_nsfw_file(
    image_bytes: bytes,
    filename: str = "image.jpg",
) -> bool:
    """
    True  = Workflow က လက်ခံသည်
    False = Reject ဖြစ်သည် သို့မဟုတ် စစ်ဆေးမှု မအောင်မြင်ပါ
    """

    if not (
        SIGHTENGINE_API_USER
        and SIGHTENGINE_API_SECRET
        and SIGHTENGINE_WORKFLOW_ID
    ):
        logger.error("Sightengine Environment Variables မပြည့်စုံပါ။")
        return False

    timeout = aiohttp.ClientTimeout(total=45)

    form = aiohttp.FormData()
    form.add_field("api_user", SIGHTENGINE_API_USER)
    form.add_field("api_secret", SIGHTENGINE_API_SECRET)
    form.add_field("workflow_id", SIGHTENGINE_WORKFLOW_ID)
    form.add_field(
        "media",
        image_bytes,
        filename=filename,
        content_type="image/jpeg",
    )

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                SIGHTENGINE_URL,
                data=form,
            ) as response:
                response_text = await response.text()

                if response.status != 200:
                    logger.error(
                        "Sightengine HTTP error %s: %s",
                        response.status,
                        response_text[:500],
                    )
                    return False

                try:
                    result = await response.json(
                        content_type=None
                    )
                except Exception:
                    logger.error(
                        "Sightengine JSON မဖတ်နိုင်ပါ: %s",
                        response_text[:500],
                    )
                    return False

        if result.get("status") != "success":
            logger.error(
                "Sightengine Workflow failed: %s",
                result,
            )
            return False

        summary = result.get("summary") or {}
        action = str(summary.get("action", "")).lower()

        if action == "accept":
            return True

        if action == "reject":
            return False

        # Unknown action ဖြစ်ရင် လုံခြုံရေးအတွက် ပိတ်မည်
        logger.warning(
            "Sightengine action မသိပါ: %s",
            action,
        )
        return False

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Sightengine စစ်ဆေးမှု အမှားဖြစ်နေပါသည်။")
        return False


async def check_photo_message(message: Message) -> bool:
    """
    Telegram photo ကို download လုပ်ပြီး Sightengine Workflow ဖြင့် စစ်သည်။
    """

    if not message.photo:
        return False

    photo = message.photo[-1]
    buffer = io.BytesIO()

    try:
        await bot.download(
            file=photo,
            destination=buffer,
        )

        image_bytes = buffer.getvalue()

        if not image_bytes:
            logger.error("ပုံဖိုင် အလွတ်ဖြစ်နေပါသည်။")
            return False

        if len(image_bytes) > MAX_IMAGE_SIZE:
            logger.warning("ပုံဖိုင် အရွယ်အစား ကန့်သတ်ချက် ကျော်နေပါသည်။")
            return False

        filename = f"telegram_{message.message_id}.jpg"

        return await check_nsfw_file(
            image_bytes=image_bytes,
            filename=filename,
        )

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Telegram ပုံကို download လုပ်မရပါ။")
        return False
    finally:
        buffer.close()


# =========================================================
# DELETE BUTTONS
# =========================================================

def make_delete_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑️ ပို့စ်ဖျက်ရန်",
                    callback_data=f"delete:{token}",
                )
            ]
        ]
    )


def register_post(
    owner_id: int,
    message_ids: list[int],
) -> str:
    token = uuid.uuid4().hex[:12]

    post_registry[token] = {
        "owner_id": owner_id,
        "message_ids": message_ids,
    }

    return token


@router.callback_query(F.data.startswith("delete:"))
async def delete_post_callback(callback: CallbackQuery):
    token = callback.data.split(":", 1)[1]
    record = post_registry.get(token)

    if not record:
        await callback.answer(
            "ဒီပို့စ်ကို ဖျက်ရန် အချက်အလက် မတွေ့ပါ။",
            show_alert=True,
        )
        return

    if callback.from_user.id != record["owner_id"]:
        await callback.answer(
            "ဒီပို့စ်ကို တင်ခဲ့သူသာ ဖျက်နိုင်ပါတယ်။",
            show_alert=True,
        )
        return

    failed = False

    for message_id in record["message_ids"]:
        try:
            await bot.delete_message(
                chat_id=CHANNEL_ID,
                message_id=message_id,
            )
        except Exception:
            failed = True
            logger.exception(
                "Channel post ဖျက်မရပါ: %s",
                message_id,
            )

    if not failed:
        post_registry.pop(token, None)
        await callback.answer("✅ ပို့စ်ကို ဖျက်ပြီးပါပြီ။")
    else:
        await callback.answer(
            "⚠️ ပို့စ်တချို့ကို ဖျက်မရပါ။ Bot ရဲ့ Channel Admin ခွင့်ပြုချက်ကို စစ်ပါ။",
            show_alert=True,
        )


# =========================================================
# MESSAGE HELPERS
# =========================================================

async def delete_status_message(status_message: Message | None):
    if not status_message:
        return

    try:
        await status_message.delete()
    except Exception:
        logger.debug("Status message ဖျက်မရပါ။", exc_info=True)


async def send_rejection(message: Message):
    await message.answer(REJECT_TEXT)


async def send_success(
    message: Message,
    owner_id: int,
    channel_message_ids: list[int],
):
    token = register_post(owner_id, channel_message_ids)

    await message.answer(
        SUCCESS_TEXT,
        reply_markup=make_delete_keyboard(token),
    )


# =========================================================
# START COMMAND
# =========================================================

@router.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "မင်္ဂလာပါရှင့်။ 📬\n\n"
        "Mailbox မှာ စာသား၊ ပုံနဲ့ Album ပုံတွေ ပေးပို့နိုင်ပါတယ်။\n"
        "မသင့်လျော်တဲ့ စကားလုံးနဲ့ ပုံတွေကို စစ်ဆေးပြီးမှ Channel ကို တင်ပေးပါမယ်။"
    )


# =========================================================
# TEXT POSTS
# =========================================================

@router.message(F.text)
async def text_handler(message: Message):
    text_content = message.text or ""

    if contains_bad_word(text_content):
        await message.answer(
            "⚠️ မသင့်လျော်သော စကားလုံးများ ပါဝင်နေသောကြောင့် "
            "ပို့စ်ကို Channel သို့ မတင်ထားပါ။"
        )
        return

    try:
        # Bot command များကို Channel သို့ မတင်ပါ
        if text_content.startswith("/"):
            return

        sent = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text_content,
        )

        await send_success(
            message=message,
            owner_id=message.from_user.id,
            channel_message_ids=[sent.message_id],
        )

    except Exception:
        logger.exception("Text post တင်ရာတွင် အမှားဖြစ်နေပါသည်။")
        await message.answer(
            "⚠️ ပို့စ်ကို Channel သို့ တင်မရပါ။ "
            "Bot ကို Channel Admin ပေးထားခြင်းရှိ၊ မရှိ စစ်ဆေးပေးပါ။"
        )


# =========================================================
# SINGLE PHOTO POSTS
# =========================================================

@router.message(F.photo, ~F.media_group_id)
async def single_photo_handler(message: Message):
    status_message = None

    try:
        # Caption ပါရင် စကားလုံးကိုလည်း အရင်စစ်ပါ
        if contains_bad_word(message.caption):
            await message.answer(
                "⚠️ မသင့်လျော်သော စကားလုံးများ ပါဝင်နေသောကြောင့် "
                "ပို့စ်ကို Channel သို့ မတင်ထားပါ။"
            )
            return

        status_message = await message.answer(CHECKING_TEXT)

        accepted = await check_photo_message(message)

        await delete_status_message(status_message)
        status_message = None

        if not accepted:
            await send_rejection(message)
            return

        buffer = io.BytesIO()
        await bot.download(
            file=message.photo[-1],
            destination=buffer,
        )

        image_bytes = buffer.getvalue()
        buffer.close()

        if not image_bytes:
            await send_rejection(message)
            return

        token = uuid.uuid4().hex[:12]
        markup = make_delete_keyboard(token)

        sent = await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=BufferedInputFile(
                image_bytes,
                filename=f"mailbox_{message.message_id}.jpg",
            ),
            caption=message.caption or None,
            reply_markup=markup,
        )

        post_registry[token] = {
            "owner_id": message.from_user.id,
            "message_ids": [sent.message_id],
        }

        await message.answer(
            SUCCESS_TEXT,
            reply_markup=make_delete_keyboard(token),
        )

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Single photo handler အမှား")

        await delete_status_message(status_message)

        try:
            await message.answer(
                "⚠️ ပုံကို စစ်ဆေးခြင်း သို့မဟုတ် Channel သို့ တင်ခြင်း "
                "မအောင်မြင်ပါ။ ထပ်မံကြိုးစားပေးပါ။"
            )
        except Exception:
            logger.exception("Error message ပို့မရပါ။")


# =========================================================
# ALBUM COLLECTION
# =========================================================

@router.message(F.photo, F.media_group_id)
async def album_photo_handler(message: Message):
    group_id = message.media_group_id
    key = (message.chat.id, group_id)

    async with album_lock:
        state = album_states.get(key)

        if state is None:
            state = AlbumState()
            album_states[key] = state

            try:
                state.status_message = await message.answer(
                    CHECKING_TEXT
                )
            except Exception:
                logger.exception(
                    "Album checking message ပို့မရပါ။"
                )

        state.messages.append(message)

        # Album ရဲ့ နောက်ဆုံးပုံရောက်ပြီးနောက် အချိန်တိုအတွင်း
        # ထပ်မံရောက်လာနိုင်သောပုံများကို စုဆောင်းရန်
        if state.task and not state.task.done():
            state.task.cancel()

        state.task = asyncio.create_task(
            process_album_after_delay(key)
        )


async def process_album_after_delay(key):
    try:
        await asyncio.sleep(ALBUM_DEBOUNCE_SECONDS)

        async with album_lock:
            state = album_states.get(key)

            if state is None:
                return

            messages = sorted(
                state.messages,
                key=lambda item: item.message_id,
            )
            status_message = state.status_message

            # Processing စတင်ချိန်မှာ state ကို ဖယ်ထားပါ
            album_states.pop(key, None)

        await process_album(
            messages=messages,
            status_message=status_message,
        )

    except asyncio.CancelledError:
        # နောက်ပုံတစ်ပုံ ထပ်ရောက်လာလျှင် timer ကို ပြန်စမည်
        raise
    except Exception:
        logger.exception("Album စုဆောင်းမှု အမှား")
        state = album_states.pop(key, None)

        if state:
            await delete_status_message(state.status_message)


async def process_album(
    messages: list[Message],
    status_message: Message | None,
):
    if not messages:
        await delete_status_message(status_message)
        return

    owner_message = messages[0]
    owner_id = owner_message.from_user.id

    try:
        if len(messages) > ALBUM_MAX_PHOTOS:
            await delete_status_message(status_message)
            await owner_message.answer(
                "⚠️ Album တစ်ခုတွင် ပုံ ၁၀ ပုံထက်ပို၍ "
                "လက်မခံပါ။"
            )
            return

        # Album အတွင်း Caption ပါသော message ကို ရှာပါ
        caption = ""

        for item in messages:
            if item.caption:
                caption = item.caption
                break

        if contains_bad_word(caption):
            await delete_status_message(status_message)
            await owner_message.answer(
                "⚠️ မသင့်လျော်သော စကားလုံးများ ပါဝင်နေသောကြောင့် "
                "ပို့စ်ကို Channel သို့ မတင်ထားပါ။"
            )
            return

        # ပုံအားလုံးကို စစ်ပြီးမှ Channel သို့ တင်မည်
        image_data = []

        for item in messages:
            accepted = await check_photo_message(item)

            if not accepted:
                await delete_status_message(status_message)
                await send_rejection(owner_message)
                return

            buffer = io.BytesIO()

            await bot.download(
                file=item.photo[-1],
                destination=buffer,
            )

            content = buffer.getvalue()
            buffer.close()

            if not content:
                await delete_status_message(status_message)
                await send_rejection(owner_message)
                return

            image_data.append(
                (
                    content,
                    f"mailbox_{item.message_id}.jpg",
                )
            )

        # Sightengine စစ်ဆေးမှုအားလုံး အောင်မြင်ပြီးပါက တင်မည်
        media = []

        for index, (content, filename) in enumerate(image_data):
            media.append(
                InputMediaPhoto(
                    media=BufferedInputFile(
                        content,
                        filename=filename,
                    ),
                    caption=caption if index == 0 and caption else None,
                )
            )

        sent_messages = await bot.send_media_group(
            chat_id=CHANNEL_ID,
            media=media,
        )

        channel_message_ids = [
            item.message_id for item in sent_messages
        ]

        await delete_status_message(status_message)

        await send_success(
            message=owner_message,
            owner_id=owner_id,
            channel_message_ids=channel_message_ids,
        )

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Album processing အမှား")

        await delete_status_message(status_message)

        try:
            await owner_message.answer(
                "⚠️ Album ကို စစ်ဆေးခြင်း သို့မဟုတ် Channel သို့ "
                "တင်ခြင်း မအောင်မြင်ပါ။ ထပ်မံကြိုးစားပေးပါ။"
            )
        except Exception:
            logger.exception("Album error message ပို့မရပါ။")


# =========================================================
# RENDER HEALTH CHECK SERVER
# =========================================================

async def health_handler(request):
    return web.json_response(
        {
            "status": "ok",
            "service": "Telegram Mailbox Bot",
        }
    )


async def run_web_server():
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=PORT,
    )

    await site.start()

    logger.info("Web server started on port %s", PORT)

    # Server ကို အသက်ရှင်နေစေရန်
    await asyncio.Event().wait()


# =========================================================
# START BOT
# =========================================================

async def main():
    required = {
        "SIGHTENGINE_API_USER": SIGHTENGINE_API_USER,
        "SIGHTENGINE_API_SECRET": SIGHTENGINE_API_SECRET,
        "SIGHTENGINE_WORKFLOW_ID": SIGHTENGINE_WORKFLOW_ID,
    }

    missing = [
        name for name, value in required.items() if not value
    ]

    if missing:
        logger.warning(
            "Render Environment Variables မပြည့်စုံပါ: %s",
            ", ".join(missing),
        )

    logger.info("Telegram Mailbox Bot စတင်နေပါသည်။")
    logger.info("Channel: %s", CHANNEL_ID)

    await asyncio.gather(
        dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        ),
        run_web_server(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot ရပ်တန့်လိုက်ပါပြီ။")
