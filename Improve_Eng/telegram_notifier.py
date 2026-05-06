"""
Improve_Eng/telegram_notifier.py
텔레그램으로 두 가지 메시지를 발송합니다:
  1. send_daily_notification  - 오늘의 학습 링크 + Daily Lesson 요약
  2. send_detailed_feedback   - 어제 오답 상세 피드백 (오답 있을 때만, 별도 메시지)
"""
import os
import logging
import requests
from datetime import date, timedelta

log = logging.getLogger(__name__)

TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
PAGES_URL = os.environ.get("PAGES_BASE_URL", "https://ggforclaude.github.io/inve-email")

TELEGRAM_MAX = 4000  # Telegram 메시지 최대 길이 (4096 - 여유분)


def send_daily_notification(today: date, day_number: int, lesson: dict) -> None:
    """오늘의 학습 페이지 링크 + Lesson 요약 발송."""
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
        f"🎧 듣기 3클립 (Short / Medium / Long)\n"
        f"📝 총 15문항 · 약 25분\n\n"
        f"👇 아래 링크를 눌러 테스트를 시작하세요\n"
        f'<a href="{page_url}">{page_url}</a>'
    )

    _send(text)
    log.info(f"텔레그램 알림 발송 완료 (daily_notification)")


def send_detailed_feedback(today: date, feedback_text: str) -> None:
    """어제 오답 상세 피드백 발송. 길면 자동으로 분할 전송."""
    if not TOKEN or not CHAT_ID:
        return
    if not feedback_text:
        return

    yesterday = today - timedelta(days=1)
    header = (
        f"📖 <b>어제 오답 상세 피드백</b> ({yesterday.strftime('%m/%d')})\n"
        f"틀린 문제를 기초부터 상세히 정리했습니다.\n"
        f"{'─' * 28}\n"
    )

    full_text = header + feedback_text

    # Telegram 4096자 제한으로 분할 전송
    chunks = _split_message(full_text, TELEGRAM_MAX)
    for i, chunk in enumerate(chunks):
        suffix = f"\n<i>({i+1}/{len(chunks)})</i>" if len(chunks) > 1 else ""
        _send(chunk + suffix)

    log.info(f"텔레그램 상세 피드백 발송 완료 ({len(chunks)}개 메시지)")


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

def _send(text: str) -> None:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id":                  CHAT_ID,
                "text":                     text,
                "parse_mode":               "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        r.raise_for_status()
    except Exception as e:
        log.error(f"텔레그램 발송 실패: {e}")


def _split_message(text: str, max_len: int) -> list[str]:
    """텍스트를 max_len 이하의 청크로 분할 (단락 경계 우선)."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # 단락 경계(\n\n)에서 분할 시도
        cut = text.rfind("\n\n", 0, max_len)
        if cut == -1:
            cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()

    return [c for c in chunks if c]
