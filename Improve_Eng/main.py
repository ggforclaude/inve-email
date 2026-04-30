"""
Improve_Eng/main.py
매일 06:00 KST GitHub Actions에서 실행되는 영어 학습 페이지 생성 스크립트.

실행 흐름:
  1. Google Sheets → 전날 결과 읽기 (Apps Script가 저장)
  2. CEFR 레벨 계산 (7일 롤링)
  3. RSS에서 오늘 콘텐츠 수집
  4. Claude API → 영역별 문제 3개씩 생성
  5. Claude API → 오늘의 학습 포인트 (Daily Lesson) 생성
  6. Claude API → 전날 오답 분석 HTML 생성
  7. HTML 테스트 페이지 빌드 → docs/YYYY-MM-DD/index.html 저장
  8. 오늘 문제를 Google Sheets 저장 (내일 채점용)
  9. 텔레그램으로 알림 발송
"""
import asyncio
import logging
import sys
import os
from datetime import datetime
import pytz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")


async def main() -> None:
    from content_fetcher import fetch_daily_content
    from question_generator import (
        generate_all_questions,
        generate_daily_lesson,
        generate_wrong_analysis,
    )
    from level_tracker import LevelTracker
    from page_builder import build_daily_page
    from telegram_notifier import send_daily_notification

    today      = datetime.now(KST).date()
    tracker    = LevelTracker()
    day_number = tracker.get_day_number(today)
    is_baseline = day_number <= 7

    log.info("=" * 55)
    log.info(f"Improve_Eng 시작: {today}  Day {day_number}  baseline={is_baseline}")
    log.info("=" * 55)

    # ① 전날 결과 읽기 (Apps Script가 Responses 시트에 저장)
    log.info("[1/7] 전날 결과 읽기...")
    prev_results = tracker.get_yesterday_results(today)

    # ② 레벨 계산
    current_levels = tracker.calculate_current_levels()
    log.info(f"[2/7] 현재 레벨: {current_levels}")

    # ③ RSS 콘텐츠 수집
    log.info("[3/7] RSS 콘텐츠 수집...")
    content = await fetch_daily_content(today)

    # ④ 문제 생성
    log.info("[4/7] 문제 생성 (Claude)...")
    questions = await generate_all_questions(
        content=content,
        current_levels=current_levels,
        is_baseline=is_baseline,
        day_number=day_number,
    )

    # ⑤ 오늘의 학습 포인트 생성
    log.info("[5/7] Daily Lesson 생성 (Claude)...")
    grammar_info = content.get("grammar", {})
    daily_lesson = await generate_daily_lesson(
        grammar_topic    = grammar_info.get("topic", ""),
        grammar_topic_kr = grammar_info.get("korean", ""),
        reading_source   = content.get("reading", {}).get("source", ""),
        current_levels   = current_levels,
        day_number       = day_number,
    )
    log.info(f"  Lesson: [{daily_lesson.get('type')}] {daily_lesson.get('title')}")

    # ⑥ 오답 분석
    wrong_analysis = None
    if prev_results and prev_results.get("wrong_items"):
        log.info("  오답 분석 생성...")
        wrong_analysis = await generate_wrong_analysis(prev_results["wrong_items"])

    # ⑦ HTML 페이지 빌드
    log.info("[6/7] HTML 페이지 생성...")
    page_path = build_daily_page(
        today=today,
        day_number=day_number,
        questions=questions,
        content=content,
        daily_lesson=daily_lesson,
        current_levels=current_levels,
        prev_wrong_analysis=wrong_analysis,
    )
    log.info(f"  저장 완료: {page_path}")

    # ⑧ 오늘 문제 Sheets 저장
    tracker.save_today_questions(today, questions)
    log.info("  문제 Sheets 저장 완료")

    # ⑨ 텔레그램 알림
    log.info("[7/7] 텔레그램 알림 발송...")
    send_daily_notification(today, day_number, daily_lesson)

    log.info("=" * 55)
    log.info("완료")
    log.info("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
