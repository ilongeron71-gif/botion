from database import get_log_channel


async def log_action(bot, chat_id, text: str):
    """Отправляет сообщение в лог-канал чата (если он настроен)."""
    log_chat = await get_log_channel(chat_id)
    if not log_chat:
        return
    try:
        await bot.send_message(log_chat, text, parse_mode="HTML")
    except Exception:
        pass