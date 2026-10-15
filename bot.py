import asyncio
import io
import os
import uuid
import logging
from dataclasses import dataclass, field

import aiohttp
from aiohttp import web

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
    InputMediaPhoto,
    BotCommand,
    MenuButtonCommands,
)

# =========================================================
# CONFIGURATION
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "@ydbumailbox").strip()

SIGHTENGINE_API_USER = os.getenv("SIGHTENGINE_API_USER", "").strip()
SIGHTENGINE_API_SECRET = os.getenv("SIGHTENGINE_API_SECRET", "").strip()
SIGHTENGINE_WORKFLOW_ID = os.getenv("SIGHTENGINE_WORKFLOW_ID", "").strip()
SIGHTENGINE_URL = "https://api.sightengine.com/1.0/check-workflow.json"

# Google Gemini API (Free Tier availability and limits depend on model/account)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PORT = int(os.getenv("PORT", "10000"))
MAX_IMAGE_SIZE = 15 * 1024 * 1024
MAX_ALBUM_PHOTOS = 10
ALBUM_DEBOUNCE_SECONDS = 1.5
MAX_AI_HISTORY_MESSAGES = 20
MAX_AI_INPUT_CHARS = 12000
MAX_AI_OUTPUT_TOKENS = 2048

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

AI_WELCOME_TEXT = (
    "မင်္ဂလာပါရှင့်။ 🤖\n\n"
    "ကျွန်တော်/ကျွန်မက Yadanabon University Mailbox ရဲ့ AI Assistant ပါ။\n"
    "ဒီနေရာမှာ စာသားနဲ့ မေးခွန်းတွေ မေးနိုင်ပါတယ်။ "
    "အရင်ပြောခဲ့တဲ့ စကားတွေကို ဒီ Session အတွင်း မှတ်ထားပြီး "
    "ဆက်စပ်မေးခွန်းတွေကို ဖြေပေးနိုင်ပါတယ်။\n\n"
    "AI စကားပြောခြင်းကို ရပ်ရန် /cancel ကိုနှိပ်ပါ။\n"
    "စကားဝိုင်းမှတ်တမ်းကို ရှင်းရန် /clear ကိုနှိပ်ပါ။"
)

AI_SYSTEM_INSTRUCTION = """
You are the AI assistant for Yadanabon University Mailbox.
Your public-facing identity is "Yadanabon University Mailbox AI Assistant".
When asked who you are, introduce yourself as the AI assistant for Yadanabon
University Mailbox. Do not introduce yourself as Gemini or make Gemini your
personal name. Do not falsely claim to be a human, a university employee, an
official university authority, or to have verified university information
unless it was supplied in the conversation. If the user directly asks which AI technology powers you, answer honestly that this assistant uses Google Gemini. Speak politely and helpfully. Respond in Burmese when
the user writes Burmese, and otherwise use the user's language. Do not invent
official university announcements, dates, fees, policies, or contact details;
clearly say when you are unsure and recommend checking official sources.
You are a text-only assistant in this Telegram bot.
""".strip()

BAD_WORDS = list(dict.fromkeys([
    "ငါလိုးမ", "လီး", "စက်ပက်", "စောက်ဖုတ်", "စောက်ဖုတ်ပြဲမ",
    "မသာမ", "ဖာသည်မ", "မအေလိုး", "ခွေးမသား", "လီးပဲ",
    "ကိုယ်မေကိုလိုး", "နှမလိုး", "ငါလိုးမသား", "မင်းညီမငါလိုး",
    "မင်းအမေငါလိုး", "တစ်ဆွေလုံးတစ်မျိုးလုံးငါလိုး", "kmkl",
    "mal", "lee", "leee", "leeee", "စပ", "ခွေးတတောင်းစားမ",
    "လီးစုပ်", "မှုတ်ပေး", "စမူ", "စောက်ပက်", "ခွေးလိုးမသား",
    "လိုးမလား", "လိုးမယ်", "လိုးချင်တယ်", "ကုန်းပေးမယ်",
    "ဖင်ချ", "ဖင်ခံ", "ဖင်လိုး", "စောက်စိ", "စောက်ချီး",
    "ချီးပဲ", "လပြွတ်ပဲ", "လဥပဲ", "လီးတောင်နေတယ်", "လချီး",
    "ဂွေးဥ", "ဂွေးစိ", "နို့စို့ချင်တယ်", "နို့ကိုင်ချင်တယ်",
    "fuck", "shit", "bitch", "asshole", "ချေးပါ", "နှာဘူး",
    "စမူဆာ", "အီးပါ", "ခွေးမ", "ခွေးသူတောင်းစား", "ဆပ္ပတ်",
    "ဖင်လျက်", "ဖာခေါင်း", "ဖာမ", "ဘောမ", "အမေလိုး", "မအလ",
    "အခြောက်", "ထဘီခြုံ", "ငါလိုး", "ခွေးလိုး", "ချီးထုတ်",
    "လီးစား", "လီးဘဲ", "လီးစုပ့", "လိုးမ", "မေလိုး",
    "မင်းမေစက်ပက်", "မင်းမေမင်းလိုး", "ဖေလိုးမ", "ဖေလိုး",
    "အဖေလိုး", "စောက်ပက်စား", "စောက်ကောင်", "စောက်ကောင်မ",
    "စောက်ချီးစား", "ချီးလိုပဲ", "သုတ်ကောင်", "တုတ်ကြောင်မ",
    "သေခြင်းဆိုး", "ကုလားနာ", "သေနာကောင်", "ဖွတ်ကျား",
    "စောက်ရူး", "သေဂျင်းဇိုးလေး", "စောက်မွှေး", "လီးပြဲ",
    "ဖာသည်", "ဒစ်စုပ်", "ငါ့ဒစ်စုပ်",
]))

# =========================================================
# LOGGING / BOT
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN မရှိပါ။ Render Environment ကို စစ်ပါ။")
if not CHANNEL_ID:
    raise RuntimeError("CHANNEL_ID မရှိပါ။")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

post_registry = {}
album_states = {}
album_lock = asyncio.Lock()

# AI sessions are stored in RAM. They reset when the Render process restarts.
# Each Telegram user gets their own independent conversation history.
ai_sessions: dict[int, list[dict[str, str]]] = {}
ai_active_users: set[int] = set()
ai_locks: dict[int, asyncio.Lock] = {}


@dataclass
class AlbumState:
    messages: list = field(default_factory=list)
    status_message: Message | None = None
    task: asyncio.Task | None = None


# =========================================================
# BAD WORD CHECK
# =========================================================

def contains_bad_word(text: str | None) -> bool:
    if not text:
        return False
    normalized = text.casefold()
    return any(word.casefold() in normalized for word in BAD_WORDS)


# =========================================================
# GOOGLE GEMINI AI CHAT
# =========================================================

def get_ai_lock(user_id: int) -> asyncio.Lock:
    lock = ai_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        ai_locks[user_id] = lock
    return lock


def split_telegram_text(text: str, limit: int = 4000) -> list[str]:
    """Split long text into Telegram-safe messages without losing content."""
    if not text:
        return ["အဖြေမရရှိပါ။ ထပ်မံမေးမြန်းပေးပါ။"]
    return [text[i:i + limit] for i in range(0, len(text), limit)]


async def ask_gemini(user_id: int, user_text: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY မသတ်မှတ်ရသေးပါ။")

    history = ai_sessions.setdefault(user_id, [])
    history.append({"role": "user", "content": user_text})
    if len(history) > MAX_AI_HISTORY_MESSAGES:
        del history[:-MAX_AI_HISTORY_MESSAGES]

    # Gemini API uses "user" and "model" roles, unlike Gemini's "assistant".
    contents = []
    for item in history:
        role = "model" if item.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": item.get("content", "")}]})

    payload = {
        "systemInstruction": {"parts": [{"text": AI_SYSTEM_INSTRUCTION}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": MAX_AI_OUTPUT_TOKENS, "temperature": 0.7},
    }
    timeout = aiohttp.ClientTimeout(total=90)
    url = GEMINI_API_URL.format(model=GEMINI_MODEL)
    headers = {"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"}

    try:
        data = None
        for attempt in range(3):
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    raw = await response.text()
                    try:
                        data = await response.json(content_type=None)
                    except Exception:
                        logger.error("Gemini returned non-JSON response: %s", raw[:1000])
                        raise RuntimeError("Gemini API က မမှန်ကန်သော အဖြေ ပြန်ပေးခဲ့ပါတယ်။")
                    if response.status < 400:
                        break
                    error_obj = data.get("error") or {}
                    error_message = error_obj.get("message") or f"HTTP {response.status}"
                    logger.error("Gemini API error (%s): %s", response.status, error_message)
                    if response.status in (429, 500, 502, 503, 504) and attempt < 2:
                        await asyncio.sleep(2 ** (attempt + 1))
                        continue
                    raise RuntimeError(f"Gemini API error ({response.status}): {error_message}")

        candidates = (data or {}).get("candidates") or []
        parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
        answer = "\n".join(part.get("text", "") for part in parts if part.get("text")).strip()
        if not answer:
            logger.error("Gemini response contained no text: %s", data)
            raise RuntimeError("AI က စာသားအဖြေ မပြန်ပေးခဲ့ပါ။")

        history.append({"role": "assistant", "content": answer})
        if len(history) > MAX_AI_HISTORY_MESSAGES:
            del history[:-MAX_AI_HISTORY_MESSAGES]
        return answer
    except asyncio.CancelledError:
        if history and history[-1].get("role") == "user":
            history.pop()
        raise
    except Exception:
        if history and history[-1].get("role") == "user":
            history.pop()
        raise


@router.message(Command("ai"))
async def ai_start_handler(message: Message):
    if not message.from_user:
        return

    user_id = message.from_user.id
    if not GEMINI_API_KEY:
        await message.answer(
            "⚠️ AI စနစ်ကို မဖွင့်ရသေးပါ။ Admin က Render Environment မှာ "
            "GEMINI_API_KEY ထည့်သွင်းပေးရန် လိုအပ်ပါတယ်။"
        )
        return

    ai_active_users.add(user_id)
    ai_sessions.setdefault(user_id, [])
    await message.answer(AI_WELCOME_TEXT)


@router.message(Command("cancel", "stop"))
async def ai_cancel_handler(message: Message):
    if message.from_user:
        ai_active_users.discard(message.from_user.id)
    await message.answer(
        "🛑 AI Chat ကို ပိတ်လိုက်ပါပြီ။\n"
        "ယခုမှစပြီး စာသားပို့လျှင် Mailbox Channel သို့ ပုံမှန်တင်နိုင်ပါပြီ။\n"
        "AI ပြန်သုံးရန် /ai ကိုနှိပ်ပါ။"
    )


@router.message(Command("clear"))
async def ai_clear_handler(message: Message):
    if message.from_user:
        ai_sessions.pop(message.from_user.id, None)
        ai_sessions[message.from_user.id] = []
        await message.answer(
            "🧹 ဒီ Session ရဲ့ AI စကားပြောမှတ်တမ်းကို ရှင်းပြီးပါပြီ။"
        )
    else:
        await message.answer("ဒီလုပ်ဆောင်ချက်ကို အသုံးမပြုနိုင်ပါ။")


async def process_ai_text(message: Message):
    """Handle ordinary text as AI chat while this user has AI mode enabled."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    text_content = (message.text or "").strip()

    # Commands must be handled by their own command handlers.
    if text_content.startswith("/"):
        return

    if not text_content:
        await message.answer("မေးခွန်းကို စာသားနဲ့ ပို့ပေးပါ။")
        return

    if len(text_content) > MAX_AI_INPUT_CHARS:
        await message.answer(
            f"မေးခွန်းက ရှည်လွန်းပါတယ်။ စာလုံးရေ {MAX_AI_INPUT_CHARS:,} အတွင်း ပို့ပေးပါ။"
        )
        return

    if not GEMINI_API_KEY:
        await message.answer("⚠️ AI စနစ်ကို မသတ်မှတ်ရသေးပါ။ Admin ကို ဆက်သွယ်ပေးပါ။")
        return

    async with get_ai_lock(user_id):
        thinking = await message.answer("🤖 စဉ်းစားနေပါတယ်ရှင့်…")
        try:
            answer = await ask_gemini(user_id, text_content)
            await delete_status_message(thinking)
            for chunk in split_telegram_text(answer):
                await message.answer(chunk)
        except asyncio.CancelledError:
            await delete_status_message(thinking)
            raise
        except Exception as exc:
            logger.exception("Gemini chat failed for user %s", user_id)
            await delete_status_message(thinking)
            message_text = str(exc)
            if "GEMINI_API_KEY" in message_text:
                await message.answer(
                    "⚠️ AI စနစ်ကို မသတ်မှတ်ရသေးပါ။ Admin ကို ဆက်သွယ်ပေးပါ။"
                )
            elif "Gemini API error" in message_text:
                await message.answer(
                    "⚠️ AI API ချိတ်ဆက်မှု မအောင်မြင်ပါ။ Admin က Render Logs ထဲရှိ "
                    "Gemini API error ကို စစ်ဆေးပေးရန် လိုအပ်ပါတယ်။"
                )
            else:
                await message.answer(
                    "⚠️ AI အဖြေ မရရှိပါ။ ခဏနေမှ ပြန်စမ်းကြည့်ပါ။"
                )


# =========================================================
# SIGHTENGINE WORKFLOW
# =========================================================

async def check_nsfw_file(
    image_bytes: bytes,
    filename: str = "image.jpg",
) -> bool:
    """True only when the Sightengine workflow explicitly returns accept."""
    if not all([
        SIGHTENGINE_API_USER,
        SIGHTENGINE_API_SECRET,
        SIGHTENGINE_WORKFLOW_ID,
    ]):
        logger.error("Sightengine credentials or Workflow ID are missing.")
        return False

    timeout = aiohttp.ClientTimeout(total=60)
    form = aiohttp.FormData()
    form.add_field("api_user", SIGHTENGINE_API_USER)
    form.add_field("api_secret", SIGHTENGINE_API_SECRET)
    form.add_field("workflow", SIGHTENGINE_WORKFLOW_ID)
    form.add_field(
        "media",
        image_bytes,
        filename=filename,
        content_type="application/octet-stream",
    )

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(SIGHTENGINE_URL, data=form) as response:
                raw_text = await response.text()
                logger.info("Sightengine HTTP status: %s", response.status)
                try:
                    result = await response.json(content_type=None)
                except Exception:
                    logger.error("Sightengine JSON error: %s", raw_text[:1000])
                    return False

        if result.get("status") != "success":
            logger.error("Sightengine API failure: %s", result)
            return False

        summary = result.get("summary") or {}
        action = str(summary.get("action", "")).strip().lower()
        logger.info("Sightengine Workflow action: %s", action)

        if action == "accept":
            return True
        if action == "reject":
            logger.warning("Sightengine rejected image: %s", summary.get("reject_reason", []))
            return False

        logger.error("Unknown Sightengine action: %s", result)
        return False

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Sightengine request failed")
        return False


async def download_photo(message: Message):
    if not message.photo:
        return None

    buffer = io.BytesIO()
    try:
        await bot.download(file=message.photo[-1], destination=buffer)
        content = buffer.getvalue()
        if not content:
            logger.error("Downloaded photo is empty")
            return None
        if len(content) > MAX_IMAGE_SIZE:
            logger.warning("Photo exceeds size limit")
            return None
        return content
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Photo download failed")
        return None
    finally:
        buffer.close()


async def check_photo_message(message: Message) -> bool:
    content = await download_photo(message)
    if content is None:
        return False
    return await check_nsfw_file(
        content,
        filename=f"telegram_{message.message_id}.jpg",
    )


# =========================================================
# STATUS / DELETE BUTTONS
# =========================================================

async def send_rejection(message: Message):
    """Tell the sender that the image was rejected or could not be verified."""
    await message.answer(REJECT_TEXT)


async def delete_status_message(message: Message | None):
    if message is None:
        return
    try:
        await message.delete()
    except Exception:
        logger.warning("Could not delete temporary status message")


def make_delete_keyboard(token: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🗑️ ပို့စ်ဖျက်ရန်",
                callback_data=f"delete:{token}",
            )
        ]]
    )


def register_post(owner_id: int, message_ids: list[int]):
    token = uuid.uuid4().hex[:12]
    post_registry[token] = {
        "owner_id": owner_id,
        "message_ids": message_ids,
    }
    return token


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


@router.callback_query(F.data.startswith("delete:"))
async def delete_post_callback(callback: CallbackQuery):
    token = callback.data.split(":", 1)[1]
    record = post_registry.get(token)

    if not record:
        await callback.answer(
            "ဖျက်ရန် ပို့စ်အချက်အလက် မတွေ့ပါ။",
            show_alert=True,
        )
        return

    if callback.from_user.id != record["owner_id"]:
        await callback.answer(
            "ပို့စ်တင်ခဲ့သူသာ ဖျက်နိုင်ပါတယ်။",
            show_alert=True,
        )
        return

    failed = False
    for message_id in record["message_ids"]:
        try:
            await bot.delete_message(chat_id=CHANNEL_ID, message_id=message_id)
        except Exception:
            failed = True
            logger.exception("Failed to delete channel message %s", message_id)

    if failed:
        await callback.answer(
            "ဖျက်မရပါ။ Bot ရဲ့ Channel Admin ခွင့်ကို စစ်ပါ။",
            show_alert=True,
        )
    else:
        post_registry.pop(token, None)
        await callback.answer("ပို့စ်ကို ဖျက်ပြီးပါပြီ။")


# =========================================================
# START COMMAND
# =========================================================

@router.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "မင်္ဂလာပါရှင့်။ 📬\n\n"
        "Mailbox မှာ စာသား၊ ပုံနဲ့ Album ပုံတွေ ပေးပို့နိုင်ပါတယ်။\n"
        "ပုံတွေကို စစ်ဆေးပြီးမှ Channel သို့ တင်ပေးပါမယ်။\n\n"
        "🤖 AI နဲ့ စာသားစကားပြောရန် /ai ကိုနှိပ်ပါ။"
    )


# =========================================================
# TEXT POSTS
# =========================================================

@router.message(F.text)
async def text_handler(message: Message):
    text_content = message.text or ""
    if text_content.startswith("/"):
        return

    # CRITICAL ROUTING GUARD: while AI mode is active, NEVER publish the text
    # to the mailbox channel. Route it only to Gemini and return immediately.
    if message.from_user and message.from_user.id in ai_active_users:
        await process_ai_text(message)
        return

    if contains_bad_word(text_content):
        await message.answer(
            "⚠️ မသင့်လျော်သော စကားလုံးများ ပါဝင်နေသောကြောင့် "
            "ပို့စ်ကို Channel သို့ မတင်ထားပါ။"
        )
        return

    try:
        sent = await bot.send_message(chat_id=CHANNEL_ID, text=text_content)
        await send_success(
            message=message,
            owner_id=message.from_user.id,
            channel_message_ids=[sent.message_id],
        )
    except Exception:
        logger.exception("Text post failed")
        await message.answer(
            "⚠️ ပို့စ်ကို Channel သို့ တင်မရပါ။ "
            "Bot ရဲ့ Channel Admin ခွင့်ကို စစ်ပေးပါ။"
        )


# =========================================================
# SINGLE PHOTO
# =========================================================

@router.message(F.photo, ~F.media_group_id)
async def single_photo_handler(message: Message):
    if message.from_user and message.from_user.id in ai_active_users:
        await message.answer("🤖 AI Chat ဖွင့်ထားပါတယ်။ AI ပိတ်ရန် /cancel ကိုနှိပ်ပြီးမှ Mailbox သို့ ပုံပို့ပါ။")
        return

    status = None
    try:
        if contains_bad_word(message.caption):
            await message.answer(
                "⚠️ မသင့်လျော်သော စကားလုံးများ ပါဝင်နေသောကြောင့် "
                "ပို့စ်ကို Channel သို့ မတင်ထားပါ။"
            )
            return

        status = await message.answer(CHECKING_TEXT)
        accepted = await check_photo_message(message)
        await delete_status_message(status)
        status = None

        if not accepted:
            await send_rejection(message)
            return

        content = await download_photo(message)
        if content is None:
            await send_rejection(message)
            return

        token = uuid.uuid4().hex[:12]
        sent = await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=BufferedInputFile(
                content,
                filename=f"mailbox_{message.message_id}.jpg",
            ),
            caption=message.caption or None,
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
        logger.exception("Single photo processing failed")
        await delete_status_message(status)
        await message.answer(
            "⚠️ ပုံကို စစ်ဆေးခြင်း သို့မဟုတ် Channel သို့ "
            "တင်ခြင်း မအောင်မြင်ပါ။"
        )


# =========================================================
# ALBUM COLLECTOR
# =========================================================

@router.message(F.photo, F.media_group_id)
async def album_photo_handler(message: Message):
    if message.from_user and message.from_user.id in ai_active_users:
        await message.answer("🤖 AI Chat ဖွင့်ထားပါတယ်။ AI ပိတ်ရန် /cancel ကိုနှိပ်ပြီးမှ Mailbox သို့ Album ပို့ပါ။")
        return

    key = (message.chat.id, message.media_group_id)
    async with album_lock:
        state = album_states.get(key)
        if state is None:
            state = AlbumState()
            album_states[key] = state
            try:
                state.status_message = await message.answer(CHECKING_TEXT)
            except Exception:
                logger.exception("Could not send album checking message")

        state.messages.append(message)
        if state.task and not state.task.done():
            state.task.cancel()
        state.task = asyncio.create_task(process_album_after_delay(key))


async def process_album_after_delay(key):
    try:
        await asyncio.sleep(ALBUM_DEBOUNCE_SECONDS)
        async with album_lock:
            state = album_states.get(key)
            if state is None:
                return
            messages = sorted(state.messages, key=lambda item: item.message_id)
            status = state.status_message
            album_states.pop(key, None)
        await process_album(messages, status)

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Album collection failed")
        async with album_lock:
            state = album_states.pop(key, None)
        if state:
            await delete_status_message(state.status_message)


# =========================================================
# ALBUM PROCESSING
# =========================================================

async def process_album(messages: list[Message], status: Message | None):
    if not messages:
        await delete_status_message(status)
        return

    owner_message = messages[0]
    owner_id = owner_message.from_user.id

    try:
        if len(messages) < 2 or len(messages) > MAX_ALBUM_PHOTOS:
            await delete_status_message(status)
            await owner_message.answer(
                "⚠️ Album ပုံအရေအတွက် မမှန်ပါ။ ပုံ ၂ ပုံမှ ၁၀ ပုံအတွင်း ပေးပို့ပါ။"
            )
            return

        caption = next((item.caption for item in messages if item.caption), None)
        if contains_bad_word(caption):
            await delete_status_message(status)
            await owner_message.answer(
                "⚠️ မသင့်လျော်သော စကားလုံးများ ပါဝင်နေသောကြောင့် "
                "ပို့စ်ကို Channel သို့ မတင်ထားပါ။"
            )
            return

        prepared_images = []
        for item in messages:
            content = await download_photo(item)
            if content is None:
                await delete_status_message(status)
                await send_rejection(owner_message)
                return

            accepted = await check_nsfw_file(
                content,
                filename=f"album_{item.message_id}.jpg",
            )
            if not accepted:
                logger.warning("Album photo rejected: message_id=%s", item.message_id)
                await delete_status_message(status)
                await send_rejection(owner_message)
                return

            prepared_images.append((content, f"album_{item.message_id}.jpg"))

        media = []
        for index, (content, filename) in enumerate(prepared_images):
            media.append(
                InputMediaPhoto(
                    media=BufferedInputFile(content, filename=filename),
                    caption=caption if index == 0 and caption else None,
                )
            )

        sent_messages = await bot.send_media_group(chat_id=CHANNEL_ID, media=media)
        channel_ids = [item.message_id for item in sent_messages]
        await delete_status_message(status)
        await send_success(
            message=owner_message,
            owner_id=owner_id,
            channel_message_ids=channel_ids,
        )

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Album processing failed")
        await delete_status_message(status)
        await owner_message.answer(
            "⚠️ Album ကို စစ်ဆေးခြင်း သို့မဟုတ် Channel သို့ "
            "တင်ခြင်း မအောင်မြင်ပါ။"
        )


# =========================================================
# RENDER WEB SERVER
# =========================================================

async def health_handler(request):
    return web.json_response({"status": "ok", "service": "Telegram Mailbox Bot"})


async def run_web_server():
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("Web server started on port %s", PORT)
    await asyncio.Event().wait()


# =========================================================
# MAIN
# =========================================================

async def setup_bot_commands():
    await bot.set_my_commands([
        BotCommand(command="start", description="Mailbox စတင်ရန်"),
        BotCommand(command="ai", description="Mailbox AI နဲ့ စကားပြောရန်"),
        BotCommand(command="cancel", description="AI Chat ပိတ်ရန်"),
        BotCommand(command="stop", description="AI Chat ပိတ်ရန်"),
        BotCommand(command="clear", description="AI စကားပြောမှတ်တမ်း ရှင်းရန်"),
    ])
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())


async def main():
    missing = []
    if not SIGHTENGINE_API_USER:
        missing.append("SIGHTENGINE_API_USER")
    if not SIGHTENGINE_API_SECRET:
        missing.append("SIGHTENGINE_API_SECRET")
    if not SIGHTENGINE_WORKFLOW_ID:
        missing.append("SIGHTENGINE_WORKFLOW_ID")
    if missing:
        logger.error("Missing Sightengine Environment Variables: %s", ", ".join(missing))

    logger.info("Telegram Mailbox Bot starting")
    logger.info("Channel: %s", CHANNEL_ID)

    try:
        await setup_bot_commands()
    except Exception:
        logger.exception("Could not configure Telegram menu commands")

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
        logger.info("Bot stopped")
