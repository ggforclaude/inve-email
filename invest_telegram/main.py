"""
텔레그램 채널 투자뉴스 요약 → 주가 차트 → 이메일 발송

사용법:
  python main.py                     # 지난 24시간 (일일 실행용)
  python main.py --catchup           # 2026-04-01 ~ 2026-04-19 하루씩 19개 발송
  python main.py --date 2026-04-20   # 특정 날짜 하루치만
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone

from telegram_fetcher import fetch_messages
from summarizer import summarize_messages
from stock_chart import build_charts
from emailer import send_summary_email

CATCHUP_START = datetime(2026, 4, 1, tzinfo=timezone.utc)
CATCHUP_END   = datetime(2026, 4, 19, tzinfo=timezone.utc)


async def _process_and_send(start: datetime, end: datetime, label: str, subject: str):
    messages = await fetch_messages(start, end)
    print(f"  → {len(messages)}개 메시지 수집")
    if not messages:
        print("  → 메시지 없음, 스킵")
        return

    summary = summarize_messages(messages, label)

    print("  → 주가 차트 생성 중...")
    charts = build_charts(summary)
    print(f"  → {len(charts)}개 차트 생성 완료")

    send_summary_email(subject, summary, charts)


async def run_daily():
    """지난 24시간 요약 → 이메일."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=24)
    label = now.strftime("%Y년 %m월 %d일")
    print(f"[일일 실행] {start.strftime('%Y-%m-%d %H:%M')} ~ {now.strftime('%Y-%m-%d %H:%M')} UTC")
    await _process_and_send(start, now, f"{label} 투자 뉴스", f"[투자뉴스] {label} 요약")


async def run_catchup():
    """2026-04-01 ~ 2026-04-19 하루씩 처리 (총 19개 이메일)."""
    current = CATCHUP_START
    day_num = 1

    while current <= CATCHUP_END:
        next_day = current + timedelta(days=1)
        label = current.strftime("%Y년 %m월 %d일")
        print(f"[캐치업 {day_num}/19] {label}")

        await _process_and_send(
            current, next_day,
            f"{label} 투자 뉴스",
            f"[투자뉴스] {label} 요약"
        )

        current = next_day
        day_num += 1
        print("  → 60초 대기 중...")
        await asyncio.sleep(60)


async def run_specific_date(date_str: str):
    """특정 날짜 하루치 처리."""
    date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    label = date.strftime("%Y년 %m월 %d일")
    print(f"[특정일] {label}")
    await _process_and_send(
        date, date + timedelta(days=1),
        f"{label} 투자 뉴스", f"[투자뉴스] {label} 요약"
    )


if __name__ == "__main__":
    if "--catchup" in sys.argv:
        asyncio.run(run_catchup())
    elif "--date" in sys.argv:
        idx = sys.argv.index("--date")
        asyncio.run(run_specific_date(sys.argv[idx + 1]))
    else:
        asyncio.run(run_daily())
