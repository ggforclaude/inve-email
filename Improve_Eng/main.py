"""
Improve_Eng/main.py
매일 04:00 KST GitHub Actions에서 실행되는 영어 학습 페이지 생성 스크립트.

실행 흐름:
  1. Google Sheets → 전날 결과 읽기
  2. CEFR 레벨 계산 (7일 롤링)
  3. RSS에서 오늘 콘텐츠 수집 (SHORT 듣기 1클립)
  4. Claude API → 듣기 스크립트 생성 (영문 + 한글)
  5. Claude API → 5영역 학습 콘텐츠 생성 (문법/듣기/비즈니스/독해/어원)
  6. Claude API → 영역별 퀴즈 문제 생성 (총 11문항)
  7. Claude API → 전날 오답 짧은 분석 HTML 생성
  8. Claude API → 전날 오답 상세 분석 생성 (HTML + Telegram 텍스트)
  9. HTML 테스트 페이지 빌드 → docs/YYYY-MM-DD/index.html 저장
 10. 오늘 문제를 Google Sheets 저장 (내일 채점용)
 11. 텔레그램: ① 학습 콘텐츠 메시지 발송
 12. 텔레그램: ② 퀴즈 링크 발송 (학습 직후)
 13. 텔레그램: ③ 어제 오답 상세 피드백 발송 (오답 있을 때만)
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
        generate_listening_script,
        generate_daily_learning,
        generate_wrong_analysis,
        generate_detailed_wrong_analysis,
    )
    from level_tracker import LevelTracker
    from page_builder import build_daily_page
    from telegram_notifier import (
        send_learning_message,
        send_daily_notification,
        send_detailed_feedback,
    )

    today      = datetime.now(KST).date()
    tracker    = LevelTracker()
    day_number = tracker.get_day_number(today)
    is_baseline = day_number <= 7

    log.info("=" * 55)
    log.info(f"Improve_Eng 시작: {today}  Day {day_number}  baseline={is_baseline}")
    log.info("=" * 55)

    # ① 전날 결과 읽기
    log.info("[1] 전날 결과 읽기...")
    prev_results = tracker.get_yesterday_results(today)

    # ② 레벨 계산
    current_levels = tracker.calculate_current_levels()
    log.info(f"[2] 현재 레벨: {current_levels}")

    # ③ RSS 콘텐츠 수집 (SHORT 단일 클립)
    log.info("[3] RSS 콘텐츠 수집...")
    content = await fetch_daily_content(today)

    # ④ 듣기 스크립트 생성 (영문 + 한글)
    log.info("[4] 듣기 스크립트 생성 (Claude)...")
    listening_script = await generate_listening_script(content["listening"])
    log.info(f"  스크립트 생성 완료: {len(listening_script.get('script_en', ''))}자")

    # ⑤ 5영역 학습 콘텐츠 생성
    log.info("[5] 5영역 학습 콘텐츠 생성 (Claude)...")
    grammar_info  = content.get("grammar", {})
    etymology     = content.get("etymology", {})
    daily_learning = await generate_daily_learning(
        grammar_info    = grammar_info,
        listening_item  = content["listening"],
        listening_script = listening_script,
        etymology       = etymology,
        current_levels  = current_levels,
        day_number      = day_number,
    )
    log.info(f"  학습 콘텐츠 생성 완료: 문법={grammar_info.get('topic', '')[:30]}")

    # ⑥ 퀴즈 문제 생성 (총 11문항)
    log.info("[6] 퀴즈 문제 생성 (Claude)...")
    questions = await generate_all_questions(
        content        = content,
        current_levels = current_levels,
        is_baseline    = is_baseline,
        day_number     = day_number,
    )

    # ⑦ 오답 짧은 분석 (당일 인라인용)
    wrong_analysis    = None
    detailed_analysis = None
    if prev_results and prev_results.get("wrong_items"):
        log.info("[7] 오답 짧은 분석 생성...")
        wrong_analysis = await generate_wrong_analysis(prev_results["wrong_items"])

        log.info("[8] 오답 상세 분석 생성...")
        detailed_analysis = await generate_detailed_wrong_analysis(prev_results["wrong_items"])
    else:
        log.info("[7-8] 오답 없음 — 분석 건너뜀")

    # ⑨ HTML 페이지 빌드
    log.info("[9] HTML 페이지 생성...")
    page_path = build_daily_page(
        today                 = today,
        day_number            = day_number,
        questions             = questions,
        content               = content,
        daily_learning        = daily_learning,
        current_levels        = current_levels,
        prev_wrong_analysis   = wrong_analysis,
        prev_detailed_analysis = detailed_analysis.get("html") if detailed_analysis else None,
    )
    log.info(f"  저장 완료: {page_path}")

    # ⑩ 오늘 문제 Sheets 저장
    tracker.save_today_questions(today, questions)
    log.info("[10] 문제 Sheets 저장 완료")

    # ⑪ 텔레그램: 학습 콘텐츠 (먼저 발송)
    log.info("[11] 텔레그램 학습 메시지 발송...")
    send_learning_message(today, day_number, daily_learning)

    # ⑫ 텔레그램: 퀴즈 링크 (학습 직후)
    log.info("[12] 텔레그램 퀴즈 링크 발송...")
    send_daily_notification(today, day_number, grammar_info.get("korean", grammar_info.get("topic", "")))

    # ⑬ 텔레그램: 어제 오답 상세 피드백
    if detailed_analysis and detailed_analysis.get("telegram"):
        log.info("[13] 텔레그램 오답 피드백 발송...")
        send_detailed_feedback(today, detailed_analysis["telegram"])

    log.info("=" * 55)
    log.info("완료")
    log.info("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
