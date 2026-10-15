import asyncio
import io
import os
import uuid
import logging
import sqlite3
from pathlib import Path
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
    ChatMemberUpdated,
)

# =========================================================
# CONFIGURATION
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "@ydbumailbox").strip()
BOT_OWNER_ID = os.getenv("BOT_OWNER_ID", "").strip()

SIGHTENGINE_API_USER = os.getenv("SIGHTENGINE_API_USER", "").strip()
SIGHTENGINE_API_SECRET = os.getenv("SIGHTENGINE_API_SECRET", "").strip()
SIGHTENGINE_WORKFLOW_ID = os.getenv("SIGHTENGINE_WORKFLOW_ID", "").strip()
SIGHTENGINE_URL = "https://api.sightengine.com/1.0/check-workflow.json"

# Google Gemini API (Free Tier availability and limits depend on model/account)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PORT = int(os.getenv("PORT", "10000"))
# Configure a Render persistent disk mounted at /var/data to preserve AI mode
# across service restarts and deployments.
AI_STATE_DB_PATH = os.getenv("AI_STATE_DB_PATH", "/var/data/ai_state.db").strip() or "/var/data/ai_state.db"
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
    "🤖 AI Chatbox ကို ဖွင့်လိုက်ပါပြီ။\n\n"
    "မေးခွန်းတွေကို ဒီမှာ စာသားနဲ့ မေးနိုင်ပါတယ်။ "
    "အရင်ပြောခဲ့တဲ့ စကားတွေကို ဒီ Session အတွင်း မှတ်ထားပြီး "
    "ဆက်စပ်မေးခွန်းတွေကို ဖြေပေးပါမယ်။\n\n"
    "AI Chatbox ကို ပိတ်ရန် Menu ထဲက ‘AI Chatbox ပိတ်ရန်’ ကိုနှိပ်ပါ။"
)

AI_SYSTEM_INSTRUCTION = """
You are the AI assistant created by the Yadanabon University Mailbox Admin.
Your public-facing identity is "Yadanabon University Mailbox AI Assistant".
Never mention Google, Gemini, or the underlying AI provider/model.
Do NOT introduce yourself or repeat who created you in ordinary replies.
Only explain who you are or who created you if the user directly asks that question.
If directly asked who created you, say the Yadanabon University Mailbox Admin created you.
Do not claim to be a human or an official university authority.

TRUSTED STARTER KNOWLEDGE ABOUT YADANABON UNIVERSITY (Myanmar):
- Burmese name: ရတနာပုံတက္ကသိုလ်. English name: Yadanabon University (YDNBU).
- University motto (use this exact wording when asked for the motto or in an
  introductory/profile answer): “ပညာပြည့်ဝ နှလုံးလှ လောကတစ်ခွင် ကောင်းကျိုးဆင်”.
- Establishment year: 2000.
- User-provided university leadership details to use when asked: ပါမောက္ခချုပ်
  ဒေါက်တာတင့်မိုးသူဇာ; ဒုတိယပါမောက္ခချုပ်များ — (၁) ဒေါက်တာဝင်းနိုင်၊
  (၂) ဒေါက်တာစန်းစန်းအေး. Treat these as user-supplied details; if a user asks
  whether the leadership is current or requests official confirmation, direct them
  to the relevant official source only because they asked for confirmation.
- Yadanabon University and the 2025 earthquake: on 28 March 2025, a magnitude
  7.7 earthquake struck and caused extensive damage in Mandalay and Sagaing,
  including residential buildings, religious buildings, schools, and other
  structures. When asked about the university introduction/profile, include the
  motto and founding year when relevant; discuss the earthquake only when asked
  about the 2025 earthquake or its impact, and do not invent specific damage to
  university buildings unless reliable information is provided.
- It is a national public higher-education institution under Myanmar's Ministry
  of Education. It is an arts-and-sciences university located about 20 km north
  of Mandalay city centre, in the Mandalay region.
- The supplied university profile says Yadanabon University was established in
  2000. Some other historical text supplied alongside it refers to a College of
  Yadanabon founded in 1955 and later renamed/promoted as Magway institutions;
  that chronology appears to concern a different institution or be inconsistent.
  Do NOT combine those dates or state the 1955/Magway history as Yadanabon
  University's history. If asked about its founding, say the profile provided to
  this assistant identifies 2000 as its establishment year, and recommend
  checking official university sources for authoritative historical details.
- The supplied profile says the university has capacity for around 60,000
  students. It describes about 23,000 students attending regular classes and
  about 37,000 taking distance-education lectures through a university branch.
  These are figures from the supplied profile and may be outdated, not live counts.
- The profile says it has 21 departments offering 26 teaching programmes, and
  mentions diploma courses under a Human Resource Development (HRD) programme,
  including Computer Studies and Spatial Information. It also mentions a Student
  Service Centre launched in June 2012, extracurricular sports and performing
  arts, community service, seminars/workshops, and international university MoUs.
- The supplied profile describes a staff complement of around 850 academic
  staff, including 83 professors, and 400 administrative staff. Treat these as
  historical/profile figures, not current verified numbers.
- Vision (paraphrased in Burmese): ကျောင်းသား/သူများ၏ ဉာဏ်ရည်ဖွံ့ဖြိုးမှု၊
  စိတ်ခံစားမှုဖွံ့ဖြိုးမှုနှင့် နိုင်ငံသားကောင်းစိတ်ဓာတ်တို့ကို ပေါင်းစပ်ဖွံ့ဖြိုးစေပြီး
  ဖွံ့ဖြိုးတိုးတက်၍ ငြိမ်းချမ်းသာယာသော ခေတ်မီဒီမိုကရေစီနိုင်ငံတော် တည်ဆောက်ရာတွင်
  ပါဝင်နိုင်သည့် ထူးချွန်ဘွဲ့ရများ မွေးထုတ်ပေးရန် ဖြစ်သည်။
- Mission (paraphrased in Burmese): ကျောင်းသား/သူများကို နိုင်ငံသားကောင်းများအဖြစ်
  ပုံဖော်ပေးနိုင်သော ပညာရေးပတ်ဝန်းကျင်ကောင်း ဖန်တီးပြီး လူ့အဖွဲ့အစည်းက ယုံကြည်
  တန်ဖိုးထားသည့် တက္ကသိုလ်ဖြစ်ရန် ဖြစ်သည်။ The profile describes it as a non-profit
  organization.
- The user's supplied list of subjects contains these 28 subjects; when asked
  for subjects/majors, answer from this list in Burmese and do not say you do not
  know merely because a subject is not in the shorter English profile:
  ၁။ မြန်မာစာ၊ ၂။ အင်္ဂလိပ်စာ၊ ၃။ ပထဝီဝင်၊ ၄။ သမိုင်း၊ ၅။ ဒဿနိကဗေဒ၊
  ၆။ စိတ်ပညာ၊ ၇။ အရှေ့တိုင်းပညာ၊ ၈။ ဥပဒေပညာ (LLB)၊ ၉။ ဥပဒေပညာ B.A. (Law)၊
  ၁၀။ မနုဿဗေဒ၊ ၁၁။ ရှေးဟောင်းသုတေသနပညာ၊ ၁၂။ စာကြည့်တိုက်နှင့်သုတပညာ၊
  ၁၃။ ဓာတုဗေဒ၊ ၁၄။ ရူပဗေဒ၊ ၁၅။ နိုင်ငံတကာဆက်ဆံရေးပညာ၊ ၁၆။ သင်္ချာ၊
  ၁၇။ သတ္တဗေဒ၊ ၁၈။ ရုက္ခဗေဒ၊ ၁၉။ ဘူမိဗေဒ၊ ၂၀။ ကုန်ထုတ်ဓာတုဗေဒ၊
  ၂၁။ ကွန်ပျူတာသိပ္ပံ၊ ၂၂။ ဇီဝဓာတုဗေဒ၊ ၂၃။ အဏုဇီဝဗေဒ၊ ၂၄။ နျူကလီးယားရူပဗေဒ၊
  ၂၅။ မြန်မာမှုပညာ၊ ၂၆။ စီးပွားရေးပညာ၊ ၂၇။ မှတ်တမ်းနှင့်မော်ကွန်းစီမံခန့်ခွဲမှုပညာ၊
  ၂၈။ ပတ်ဝန်းကျင်ဆိုင်ရာပညာ.
- The supplied English profile also mentions meteorology, hydrology and biotechnology,
  while the user's 28-item list includes some different subjects. If asked about the
  exact current official list, explain that these references differ and recommend
  confirming with the university; otherwise present the user's 28-item list as the
  list supplied for this mailbox assistant.
OFFICIAL WEBSITE PRIORITY AND RESPONSE RULES:
- Treat the university's official website https://ydnbu.edu.mm/ as the PRIMARY
  reference for university-specific information. Relevant official pages include:
  * Home / vision and mission: https://ydnbu.edu.mm/
  * History and briefing: https://ydnbu.edu.mm/history-and-briefing/
  * Degree programs: https://ydnbu.edu.mm/degree-offered/
  * Departments: https://ydnbu.edu.mm/departments/
  * University facts: https://ydnbu.edu.mm/university-facts/
  * University entrance and subject-wise entry lists:
    https://ydnbu.edu.mm/university_entrance/
  * Department/course details: https://ydnbu.edu.mm/course/
- Use the official website as an internal reference priority for university facts,
  but DO NOT automatically show, append, or mention any website URL in ordinary
  answers. Answer the user's actual question directly and naturally.
- ONLY include a website link if the user explicitly asks for a source/reference,
  asks where to check/find the information, requests the official website, or asks
  for a current announcement/admission/exam schedule/fee that needs official
  confirmation. Then provide only the most relevant official page link, not a list
  of all pages. If the user did not ask for a link, do not include one.
- If the user asks a normal question about vision, mission, courses, departments,
  or other known university facts, simply answer the question without a link or a
  closing sentence telling them to visit the website.
- Important runtime limitation: this bot does not automatically browse or refresh
  the official website on every message. The facts in this instruction are a
  starter knowledge base based on the official pages checked when the code was
  prepared. For time-sensitive facts (new admissions, exam schedules, fees,
  current notices, rector/staff changes, current student counts), explain briefly
  that the latest detail needs official confirmation. Give the official link only
  when the user has asked where to confirm it or when a link is necessary to fulfil
  an explicit request for official/current information.
- Official website degree page lists BA/B.Sc./LLB, BA (Hons)/B.Sc. (Hons),
  MA/M.Sc., and M.Res. It describes ordinary arts/science bachelor's programs as
  generally 4 years, law as 5 years, and honours study as generally 5 years.
  Refer to the official degree page for exact program details and qualifications.
- Master's programs from the information supplied by the user include:
  * M.A. and M.Res. in Myanmar, English, Geography, History, Philosophy,
    Psychology, and Oriental Studies.
  * M.A. in International Relations and Library and Information Studies.
  * L.L.M. and M.Res. in Law.
  * M.Sc. and M.Res. in Chemistry, Physics, Mathematics, Zoology, Botany,
    and Geology; M.Sc. in Industrial Chemistry.
  Treat this as supplied program information and verify against the official
  degree page for current availability.
- Public reference also supplied by the user:
  https://my.wikipedia.org/wiki/ရတနာပုံတက္ကသိုလ်
- For questions answered by this knowledge, answer naturally in Burmese and
  directly. Do not repeatedly introduce yourself or say only "မသိပါဘူး". If the
  answer is known from the available facts, answer it; if it is a current or
  unverified detail, explain briefly and provide the relevant official link.

Speak politely and helpfully. Respond in Burmese when the user writes Burmese,
and otherwise use the user's language. You are a text-only assistant in this bot.
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

# Only the configured official mailbox channel is allowed. If someone adds the
# bot to another group/channel, notify the owner (if configured) and leave.
_ALLOWED_CHANNEL_NUMERIC_ID = None


@dp.my_chat_member()
async def protect_bot_from_other_chats(event: ChatMemberUpdated):
    global _ALLOWED_CHANNEL_NUMERIC_ID
    new_status = event.new_chat_member.status
    if new_status not in {"member", "administrator", "restricted"}:
        return

    chat_id = event.chat.id
    if _ALLOWED_CHANNEL_NUMERIC_ID is None:
        try:
            official_chat = await bot.get_chat(CHANNEL_ID)
            _ALLOWED_CHANNEL_NUMERIC_ID = official_chat.id
        except Exception:
            logger.exception("Could not resolve official CHANNEL_ID; leaving non-resolved chat for safety")
            # If target channel cannot be resolved, do not assume this chat is safe.
            _ALLOWED_CHANNEL_NUMERIC_ID = 0

    if chat_id == _ALLOWED_CHANNEL_NUMERIC_ID:
        logger.info("Bot membership update in the configured official channel: %s", chat_id)
        return

    chat_title = event.chat.title or event.chat.username or str(chat_id)
    logger.warning("Bot was added to an unapproved chat %s (%s); attempting to leave", chat_title, chat_id)
    if BOT_OWNER_ID.isdigit():
        try:
            await bot.send_message(
                chat_id=int(BOT_OWNER_ID),
                text=(
                    "⚠️ Bot ကို ခွင့်မပြုထားတဲ့ Group/Channel တစ်ခုမှာ ထည့်ထားတာ တွေ့ရှိပါတယ်။\n"
                    f"အမည်: {chat_title}\nChat ID: {chat_id}\n"
                    "လုံခြုံရေးအတွက် အဲဒီနေရာကနေ အလိုအလျောက် ထွက်ရန် ကြိုးစားနေပါတယ်။"
                ),
            )
        except Exception:
            logger.exception("Could not notify BOT_OWNER_ID")
    try:
        await bot.leave_chat(chat_id=chat_id)
    except Exception:
        logger.exception("Could not leave unapproved chat %s", chat_id)
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

def _state_db_path() -> str:
    """Use Render's persistent disk when mounted; otherwise use local app storage."""
    preferred = Path(AI_STATE_DB_PATH)
    try:
        preferred.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(preferred)) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS ai_active_users (user_id INTEGER PRIMARY KEY)")
        return str(preferred)
    except Exception:
        fallback = Path(__file__).resolve().parent / "ai_state.db"
        with sqlite3.connect(str(fallback)) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS ai_active_users (user_id INTEGER PRIMARY KEY)")
        logger.warning("Persistent AI state path unavailable; using local fallback %s", fallback)
        return str(fallback)

AI_STATE_DB = _state_db_path()

def load_ai_active_users() -> None:
    try:
        with sqlite3.connect(AI_STATE_DB) as conn:
            rows = conn.execute("SELECT user_id FROM ai_active_users").fetchall()
        ai_active_users.update(int(row[0]) for row in rows)
        logger.info("Restored %s active AI chat sessions", len(ai_active_users))
    except Exception:
        logger.exception("Could not restore active AI sessions")

def set_ai_active(user_id: int, active: bool) -> None:
    if active:
        ai_active_users.add(user_id)
    else:
        ai_active_users.discard(user_id)
    try:
        with sqlite3.connect(AI_STATE_DB) as conn:
            if active:
                conn.execute("INSERT OR IGNORE INTO ai_active_users(user_id) VALUES (?)", (user_id,))
            else:
                conn.execute("DELETE FROM ai_active_users WHERE user_id = ?", (user_id,))
    except Exception:
        logger.exception("Could not save AI active state for user %s", user_id)


@dataclass
class AlbumState:
    messages: list = field(default_factory=list)
    status_message: Message | None = None
    task: asyncio.Task | None = None


# =========================================================
# BAD WORD CHECK
# =========================================================

def find_bad_word(text: str | None) -> str | None:
    """Return the first matched prohibited word, for a clear moderation notice."""
    if not text:
        return None
    normalized = text.casefold()
    for word in BAD_WORDS:
        if word.casefold() in normalized:
            return word
    return None


def contains_bad_word(text: str | None) -> bool:
    # Keep this helper for any existing call sites that only need True/False.
    return find_bad_word(text) is not None


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
    # Activate first so a missing/temporarily failing AI API can never cause
    # the user's next messages to be accidentally published to the channel.
    set_ai_active(user_id, True)
    ai_sessions.setdefault(user_id, [])
    if not GEMINI_API_KEY:
        await message.answer(
            "⚠️ AI Chatbox ကို ဖွင့်ထားပါတယ်၊ ဒါပေမဲ့ AI API key မရှိသေးလို့ "
            "လောလောဆယ် အဖြေမပေးနိုင်ပါ။ /cancel မနှိပ်မချင်း သင့်စာတွေကို "
            "Channel သို့ မတင်ပါဘူး။ Admin ကို ဆက်သွယ်ပါ။"
        )
        return
    await message.answer(AI_WELCOME_TEXT)


@router.message(Command("cancel", "stop"))
async def ai_cancel_handler(message: Message):
    if message.from_user:
        set_ai_active(message.from_user.id, False)
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

    matched_word = find_bad_word(text_content)
    if matched_word:
        await message.answer(
            f"⚠️ မသင့်လျော်သော စကားလုံး({matched_word}) ပါဝင်နေသောကြောင့် "
            "ပို့စ်ကို Channel သို့ မတင်ပေးပါ။"
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
        matched_word = find_bad_word(message.caption)
        if matched_word:
            await message.answer(
                f"⚠️ မသင့်လျော်သော စကားလုံး({matched_word}) ပါဝင်နေသောကြောင့် "
                "ပို့စ်ကို Channel သို့ မတင်ပေးပါ။"
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

        # Re-check immediately before publishing in case /ai was enabled while
        # moderation/download was in progress.
        if message.from_user and message.from_user.id in ai_active_users:
            await message.answer("🤖 AI Chat ဖွင့်ထားပါတယ်။ /cancel မနှိပ်မချင်း ပုံကို Channel သို့ မတင်ပါဘူး။")
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
        matched_word = find_bad_word(caption)
        if matched_word:
            await delete_status_message(status)
            await owner_message.answer(
                f"⚠️ မသင့်လျော်သော စကားလုံး({matched_word}) ပါဝင်နေသောကြောင့် "
                "ပို့စ်ကို Channel သို့ မတင်ပေးပါ။"
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

        # Re-check immediately before publishing in case AI was enabled while
        # the album was being collected or moderated.
        if owner_id in ai_active_users:
            await delete_status_message(status)
            await owner_message.answer("🤖 AI Chat ဖွင့်ထားပါတယ်။ /cancel မနှိပ်မချင်း Album ကို Channel သို့ မတင်ပါဘူး။")
            return

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
    # Keep the bot's normal commands available, with only one visible AI-stop command.
    # /stop remains an alias for /cancel in the handler, but is not shown as a duplicate.
    await bot.set_my_commands([
        BotCommand(command="start", description="Bot စတင်ရန်"),
        BotCommand(command="ai", description="AI Chatbox ဖွင့်ရန်"),
        BotCommand(command="cancel", description="AI Chatbox ပိတ်ရန်"),
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

    load_ai_active_users()
    logger.info("Telegram Mailbox Bot starting")
    logger.info("Channel: %s", CHANNEL_ID)
    if not BOT_OWNER_ID.isdigit():
        logger.warning("BOT_OWNER_ID is not configured; unauthorized-chat alerts will not be sent")

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
