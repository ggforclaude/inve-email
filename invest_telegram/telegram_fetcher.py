import os
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
CHANNELS = [ch.strip() for ch in os.getenv("TELEGRAM_CHANNELS", "YeouidoStory2").split(",")]
SESSION_STRING = os.getenv("TELEGRAM_SESSION_STRING", "")


def _make_client() -> TelegramClient:
    if SESSION_STRING:
        return TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    return TelegramClient("session_yeoui", API_ID, API_HASH)


async def fetch_messages(start_dt: datetime, end_dt: datetime) -> list[dict]:
    """지정된 기간의 모든 채널 메시지를 가져옵니다."""
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)

    all_messages = []
    async with _make_client() as client:
        for channel in CHANNELS:
            print(f"  채널 수집 중: {channel}")
            async for msg in client.iter_messages(channel, reverse=True, offset_date=start_dt):
                if msg.date > end_dt:
                    break
                if msg.date < start_dt:
                    continue

                text = msg.text or msg.message or ""
                if not text.strip():
                    continue

                all_messages.append({
                    "id": msg.id,
                    "channel": channel,
                    "date": msg.date.strftime("%Y-%m-%d %H:%M"),
                    "text": text.strip(),
                })

    all_messages.sort(key=lambda m: m["date"])
    return all_messages
