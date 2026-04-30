"""
Improve_Eng/main.py
매일 08:00 KST GitHub Actions에서 실행되는 영어 학습 이메일 발송 스크립트.

실행 흐름:
  1. 전날 Google Form 응답 읽기 + 채점
  2. CEFR 레벨 계산 (7일 롤링)
  3. RSS에서 오늘 콘텐츠 수집
  4. Claude API로 영역별 문제 3개씩 생성
  5. 오답 분석 HTML 생성 (Claude)
  6. HTML 이메일 작성 → Gmail 발송
  7. 오늘 문제를 Google Sheets에 저장 (내일 채점용)
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
    from question_generator import generate_all_questions, generate_wrong_analysis
    from level_tracker import LevelTracker
    from email_sender import send_daily_email

    today      = datetime.now(KST).date()
    tracker    = LevelTracker()
    day_number = tracker.get_day_number(today)
    is_baseline = day_number <= 7

    log.info(f"{'='*55}")
    log.info(f"Improve_Eng 시작: {today}  Day {day_number}  baseline={is_baseline}")
    log.info(f"{'='*55}")

    # ① 전날 채점
    log.info("[1/5] 전날 응답 채점...")
    prev_results = tracker.get_yesterday_results(today)

    # ② 현재 레벨 계산
    current_levels = tracker.calculate_current_levels()
    log.info(f"[2/5] 현재 레벨: {current_levels}")

    # ③ 콘텐츠 수집
    log.info("[3/5] RSS 콘텐츠 수집...")
    content = await fetch_daily_content(today)

    # ④ 문제 생성
    log.info("[4/5] 문제 생성 (Claude)...")
    questions = await generate_all_questions(
        content=content,
        current_levels=current_levels,
        is_baseline=is_baseline,
        day_number=day_number,
    )

    # ⑤ 오답 분석
    wrong_analysis = None
    if prev_results and prev_results.get("wrong_items"):
        log.info("오답 분석 생성...")
        wrong_analysis = await generate_wrong_analysis(prev_results["wrong_items"])

    # ⑥ 이메일 발송
    log.info("[5/5] 이메일 발송...")
    await send_daily_email(
        today=today,
        day_number=day_number,
        questions=questions,
        content=content,
        prev_results=prev_results,
        current_levels=current_levels,
        wrong_analysis=wrong_analysis,
    )

    # ⑦ 오늘 문제 Sheets 저장
    tracker.save_today_questions(today, questions)

    log.info(f"{'='*55}")
    log.info("완료")
    log.info(f"{'='*55}")


if __name__ == "__main__":
    asyncio.run(main())
