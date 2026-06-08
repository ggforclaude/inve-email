"""
Improve_Eng/telegram_notifier.py
텔레그램으로 세 가지 메시지를 발송합니다:

  1. send_learning_message  - 오늘의 5영역 학습 콘텐츠 (먼저 발송)
  2. send_daily_notification - 퀴즈 링크 + 간단 안내 (학습 후 발송)
  3. send_detailed_feedback  - 어제 오답 상세 피드백 (오답 있을 때만)

메시지 분리 이유:
  학습(배움) → 퀴즈(테스트) 순서로 제공해 학습 효과를 높입니다.
  회상 훈련(Retrieval Practice) 원리: 배운 직후 퀴즈로 장기 기억 강화.
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
SEP = "─" * 28


def send_learning_message(today: date, day_number: int, learning: dict) -> None:
    """오늘의 7영역 학습 콘텐츠 발송.
    순서: 문법 → 듣기(오디오+스크립트) → 비즈니스 → 발음 → 어휘 → 독해 → 어원
    내용이 길어 자동으로 분할 전송.
    """
    if not TOKEN or not CHAT_ID:
        log.warning("텔레그램 자격증명 없음 — 학습 메시지 건너뜀")
        return

    grammar  = learning.get("grammar", {})
    listen   = learning.get("listening", {})
    business = learning.get("business", {})
    reading  = learning.get("reading", {})
    pron     = learning.get("pronunciation", {})
    vocab    = learning.get("vocabulary", [])
    etym     = learning.get("etymology_lesson", {})

    # ── 문법 섹션 ────────────────────────────────────────────────────
    grammar_examples = "\n".join(
        f"  ✅ <code>{ex.get('en','')}</code>\n     → {ex.get('kr','')}"
        for ex in grammar.get("examples", [])
    )
    grammar_block = "\n".join(filter(None, [
        f"{SEP}",
        f"🔤 <b>문법: {grammar.get('topic_en','')} ({grammar.get('topic_kr','')})</b>",
        "",
        grammar.get("core_rule", ""),
        "",
        f"📌 <b>언제 쓰나:</b> {grammar.get('when_to_use','')}",
        "",
        "<b>예문:</b>",
        grammar_examples,
        "",
        f"❌ <code>{grammar.get('contrast_en','')}</code>",
        f"   → {grammar.get('contrast_kr','')}",
        "",
        f"⚠️ <b>한국인 실수:</b> {grammar.get('common_mistakes','')}",
        "",
        f"💡 <i>{grammar.get('remember','')}</i>",
    ]))

    # ── 듣기 섹션 (오디오 URL or 페이지 링크 포함) ───────────────────
    audio_url = listen.get("audio_url", "")
    page_url  = listen.get("page_url", "")
    if audio_url:
        audio_line = f'🎧 <a href="{audio_url}">오디오 직접 듣기</a>'
    elif page_url:
        audio_line = f'🎧 <a href="{page_url}">{listen.get("source","")} 에서 듣기</a>'
    else:
        audio_line = "🎧 (오디오 링크 없음 — 스크립트로 학습)"

    listen_block = "\n".join(filter(None, [
        f"{SEP}",
        f"🎧 <b>듣기: {listen.get('source','')} — {listen.get('title','')[:50]}</b>",
        "",
        audio_line,
        "",
        f"🇬🇧 <i>{listen.get('script_en','')}</i>",
        "",
        f"🇰🇷 {listen.get('script_kr','')}",
        "",
        f"📝 핵심 어휘: {listen.get('key_vocab','')}",
    ]))

    # ── 비즈니스 섹션 ─────────────────────────────────────────────────
    biz_block = "\n".join(filter(None, [
        f"{SEP}",
        f'💼 <b>비즈니스: "{business.get("expression","")}"</b> — {business.get("meaning_kr","")}',
        "",
        f'<code>{business.get("example_en","")}</code>',
        f'→ {business.get("example_kr","")}',
        f'<i>📌 {business.get("when_to_use","")}</i>',
    ]))

    # ── 발음 섹션 ─────────────────────────────────────────────────────
    pron_ex = " | ".join(pron.get("examples", []))
    pron_block = "\n".join(filter(None, [
        f"{SEP}",
        f"🔊 <b>발음: {pron.get('focus','')}</b>",
        "",
        pron.get("rule", ""),
        "",
        f"<code>{pron_ex}</code>",
        "",
        f"⚠️ {pron.get('common_error','')}",
        f"연습: <i>{pron.get('practice_sentence','')}</i>",
        f"💡 {pron.get('tip','')}",
    ]))

    # ── 어휘 섹션 ─────────────────────────────────────────────────────
    vocab_lines = []
    for v in vocab:
        vocab_lines += [
            f"• <b>{v.get('word','')}</b> [{v.get('level','')}] — {v.get('meaning_kr','')}",
            f"  연어: <i>{v.get('collocation','')}</i>",
            f"  <code>{v.get('example_en','')}</code> → {v.get('example_kr','')}",
            "",
        ]
    vocab_block = "\n".join(filter(None, [
        f"{SEP}",
        "📝 <b>오늘의 어휘 (3단어 + 콜로케이션)</b>",
        "",
        *vocab_lines,
    ]))

    # ── 독해 전략 섹션 ────────────────────────────────────────────────
    reading_block = "\n".join(filter(None, [
        f"{SEP}",
        f"📖 <b>독해 전략: {reading.get('strategy','')}</b>",
        "",
        reading.get("how_to", ""),
        f"<i>{reading.get('why_effective','')}</i>",
        "",
        "<b>예시 지문:</b>",
        f"<i>{reading.get('example_passage','')}</i>",
        "",
        f"<b>적용:</b> {reading.get('example_application','')}",
    ]))

    # ── 어원 섹션 ─────────────────────────────────────────────────────
    etym_block = "\n".join(filter(None, [
        f"{SEP}",
        f'🌱 <b>어원: "{etym.get("word","")}"</b> — {etym.get("meaning_kr","")}',
        "",
        f"출처: {etym.get('origin','')}",
        etym.get("story_kr", ""),
        f"<i>💡 {etym.get('memory_tip','')}</i>",
    ]))

    header = f"📚 <b>Day {day_number} — 오늘의 영어 레슨</b>\n📅 {today.strftime('%Y.%m.%d')}"
    footer = f"\n{SEP}\n⬇️ 잠시 후 퀴즈 링크가 도착합니다!"

    full_text = "\n\n".join([
        header,
        grammar_block,
        listen_block,
        biz_block,
        pron_block,
        vocab_block,
        reading_block,
        etym_block,
    ]) + footer

    # 오디오 파일이 있으면 별도 sendAudio로 먼저 발송 시도
    if audio_url:
        ok = _send_audio(audio_url, caption=f"🎧 {listen.get('source','')} — {listen.get('title','')[:60]}")
        if ok:
            log.info("  오디오 파일 발송 성공")

    chunks = _split_message(full_text, TELEGRAM_MAX)
    for i, chunk in enumerate(chunks):
        suffix = f"\n<i>({i+1}/{len(chunks)})</i>" if len(chunks) > 1 else ""
        _send(chunk + suffix)

    log.info(f"텔레그램 학습 메시지 발송 완료 ({len(chunks)}개)")


def send_daily_notification(today: date, day_number: int, grammar_topic: str) -> None:
    """퀴즈 링크 발송 (학습 메시지 이후)."""
    if not TOKEN or not CHAT_ID:
        log.warning("텔레그램 자격증명 없음 — 알림 건너뜀")
        return

    page_url = f"{PAGES_URL}/{today}/"

    text = (
        f"📝 <b>Day {day_number} — 오늘의 퀴즈</b>\n\n"
        f"🎧 듣기 1클립 (약 2-3분) × 2문항\n"
        f"✏️ 문법: {grammar_topic}\n"
        f"📖 독해 3문항 · 🗣️ 말하기 3문항\n\n"
        f"<b>총 11문항 · 약 15분</b>\n\n"
        f"레슨 내용을 바탕으로 문제를 풀어보세요!\n"
        f'👇 <a href="{page_url}">퀴즈 시작하기</a>'
    )

    _send(text)
    log.info("텔레그램 퀴즈 알림 발송 완료")


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
        f"{SEP}\n"
    )

    full_text = header + feedback_text

    chunks = _split_message(full_text, TELEGRAM_MAX)
    for i, chunk in enumerate(chunks):
        suffix = f"\n<i>({i+1}/{len(chunks)})</i>" if len(chunks) > 1 else ""
        _send(chunk + suffix)

    log.info(f"텔레그램 상세 피드백 발송 완료 ({len(chunks)}개 메시지)")


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _send_audio(audio_url: str, caption: str = "") -> bool:
    """오디오 URL을 Telegram sendAudio로 발송. 성공하면 True."""
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendAudio",
            json={
                "chat_id": CHAT_ID,
                "audio":   audio_url,
                "caption": caption[:1024],
            },
            timeout=20,
        )
        result = r.json()
        if result.get("ok"):
            return True
        log.warning(f"sendAudio 실패: {result.get('description','')}")
        return False
    except Exception as e:
        log.warning(f"sendAudio 예외: {e}")
        return False


def _send(text: str) -> None:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id":                  CHAT_ID,
                "text":                     text,
                "parse_mode":               "HTML",
                "disable_web_page_preview": True,
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
        cut = text.rfind("\n\n", 0, max_len)
        if cut == -1:
            cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()

    return [c for c in chunks if c]
