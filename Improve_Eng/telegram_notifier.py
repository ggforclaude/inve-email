"""
Improve_Eng/telegram_notifier.py
GitHub Actions에서 텔레그램으로 일일 학습 알림을 발송합니다.
"""
import os
import logging
import requests
from datetime import date

log = logging.getLogger(__name__)

TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
PAGES_URL = os.environ.get("PAGES_BASE_URL", "https://ggforclaude.github.io/inve-email")


def send_daily_notification(today: date, day_number: int, lesson: dict) -> None:
    if not TOKEN or not CHAT_ID:
        log.warning("텔레그램 자격증명 없음 — 알림 건너뜀")
        return

    page_url = f"{PAGES_URL}/{today}/"
    icon     = lesson.get("icon", "📚")
    title    = lesson.get("title", "Daily English")
    subtitle = lesson.get("subtitle", "")

    text = (
        f"📚 <b>오늘의 영어 테스트</b> — Day {day_number}\n\n"
        f"📅 {today.strftime('%Y년 %m월 %d일 (%a)')}\n\n"
        f"{icon} <b>Today's Lesson:</b> {title}\n"
        f"    {subtitle}\n\n"
        f"👇 아래 링크를 눌러 테스트를 시작하세요\n"
        f"<a href=\"{page_url}\">{page_url}</a>\n\n"
        f"<i>4개 영역 · 12문항 · 약 20분</i>"
    )

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": False},
            timeout=10,
        )
        r.raise_for_status()
        log.info(f"텔레그램 알림 발송 완료 → chat_id={CHAT_ID}")
    except Exception as e:
        log.error(f"텔레그램 발송 실패: {e}")
