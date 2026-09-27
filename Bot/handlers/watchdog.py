import time
from collections import defaultdict

from aiogram import Router
from aiogram.types import Message, ChatPermissions

from config import SPAM_WINDOW, SPAM_LIMIT, REPEAT_LIMIT, MUTE_SECONDS
from database import ensure_chat, ensure_user, inc_messages
from permissions import get_level
from utils.logger import log_action

router = Router()

_history: dict[tuple[int, int], list[float]] = defaultdict(list)
_repeat: dict[tuple[int, int], list] = defaultdict(lambda: ["", 0])

MUTE = ChatPermissions(can_send_messages=False)


@router.message()
async def watchdog(message: Message):
    """Счёт активности + анти-спам в одном обработчике."""
    if message.chat.type not in ("group", "supergroup"):
        return
    if not message.from_user or message.from_user.is_bot:
        return

    # ---------- 1. Счётчик активности ----------
    await ensure_chat(message.chat.id)
    await ensure_user(
        message.from_user.id, message.chat.id,
        message.from_user.username or "",
    )
    await inc_messages(message.from_user.id, message.chat.id)

    # ---------- 2. Анти-спам ----------
    if not message.text:
        return
    lvl = await get_level(message.bot, message.chat.id, message.from_user.id)
    if lvl >= 2:  # модераторов не трогаем
        return

    key = (message.chat.id, message.from_user.id)
    now = time.time()

    hist = [t for t in _history[key] if now - t <= SPAM_WINDOW]
    hist.append(now)
    _history[key] = hist

    triggered = False
    reason = ""
    if len(hist) > SPAM_LIMIT:
        triggered = True
        reason = "флуд"
    else:
        last_text, count = _repeat[key]
        count = count + 1 if message.text == last_text else 1
        _repeat[key] = [message.text, count]
        if count >= REPEAT_LIMIT:
            triggered = True
            reason = "повтор сообщений"

    if triggered:
        try:
            await message.chat.restrict(
                message.from_user.id,
                MUTE,
                until_date=int(now) + MUTE_SECONDS,
            )
            _history[key].clear()
            _repeat[key] = ["", 0]
            await message.reply(
                f"🔇 {message.from_user.mention_html()} замучен на "
                f"{MUTE_SECONDS // 60} мин. ({reason})",
                parse_mode="HTML",
            )
            await log_action(
                message.bot, message.chat.id,
                f"🔇 <b>Анти-спам</b>\n"
                f"Кто: {message.from_user.full_name} (<code>{message.from_user.id}</code>)\n"
                f"Причина: {reason}",
            )
        except Exception:
            pass