"""
Improve_Eng/question_generator.py
Claude API로 영역별 문제와 오답 분석을 생성합니다.
- 문제 생성: claude-haiku-4-5 (빠르고 저렴)
- 오답 분석: claude-sonnet-4-6 (품질 우선)
"""
import anthropic
import json
import logging

log = logging.getLogger(__name__)
_client = anthropic.Anthropic()

LEVEL_ORDER = ["A2", "B1", "B2", "C1"]
LEVEL_COLORS = {"A2": "초급", "B1": "중하급", "B2": "중상급", "C1": "고급"}

DOMAIN_KR = {
    "listening": "듣기",
    "grammar":   "문법",
    "reading":   "독해",
    "speaking":  "말하기",
}


def _adaptive_mix(current_level: str) -> list[tuple[str, int]]:
    """현재 레벨 1문항 + 상위 레벨 2문항 구성."""
    idx      = LEVEL_ORDER.index(current_level) if current_level in LEVEL_ORDER else 1
    next_lvl = LEVEL_ORDER[min(idx + 1, len(LEVEL_ORDER) - 1)]
    return [(current_level, 1), (next_lvl, 2)]

# 베이스라인 1~7일: A2·B1·B2 각 1문항으로 전 레벨 탐색
BASELINE_MIX = [("A2", 1), ("B1", 1), ("B2", 1)]


# ── 메인 진입점 ──────────────────────────────────────────────────────────────

async def generate_all_questions(
    content: dict,
    current_levels: dict,
    is_baseline: bool,
    day_number: int,
) -> dict:
    """4개 영역 문제를 순차 생성 (각 3문항)."""
    results = {}
    for domain in ["listening", "grammar", "reading", "speaking"]:
        mix = BASELINE_MIX if is_baseline else _adaptive_mix(
            current_levels.get(domain, "B1")
        )
        try:
            if domain == "grammar":
                results[domain] = await _gen_grammar(content["grammar"], mix)
            elif domain == "speaking":
                results[domain] = await _gen_speaking(content["speaking"], mix)
            else:
                results[domain] = await _gen_content_questions(
                    domain, content[domain], mix
                )
        except Exception as e:
            log.error(f"[{domain}] 문제 생성 실패: {e}")
            results[domain] = _fallback_questions(domain)

    return results


async def generate_wrong_analysis(wrong_items: list[dict]) -> str:
    """틀린 문항을 분석해 한국어 HTML 설명문을 반환."""
    if not wrong_items:
        return ""

    items_text = "\n".join(
        f"- [{DOMAIN_KR.get(item['domain'], item['domain'])}·{item['level']}] "
        f"Q: {item['question'][:80]}\n"
        f"  정답: {item['correct']} / 선택: {item.get('chosen', '?')}\n"
        f"  설명: {item['explanation'][:120]}"
        for item in wrong_items[:5]
    )

    prompt = f"""영어 학습 코치로서, 학습자가 어제 틀린 문제를 분석해 주세요.

[오답 목록]
{items_text}

규칙:
- 각 오답마다 1~2줄의 핵심 학습 포인트를 한국어로 작성
- 틀린 원인(혼동 포인트)과 올바른 규칙을 간결하게 설명
- 전체 200자 이내
- 아래 HTML 형식만 반환 (다른 텍스트 없이):

<div class="wi"><span class="tag">[영역]</span> <b>핵심</b>: 설명...</div>
<div class="wi"><span class="tag">[영역]</span> <b>핵심</b>: 설명...</div>"""

    resp = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


# ── 영역별 문제 생성 ─────────────────────────────────────────────────────────

async def _gen_content_questions(domain: str, content_item: dict, mix: list) -> list[dict]:
    """듣기 / 독해: 수집된 텍스트 기반 문제 생성."""
    domain_kr   = DOMAIN_KR[domain]
    text        = content_item.get("text", "") or "(텍스트 없음)"
    source_name = content_item.get("source", "")
    total_q     = sum(n for _, n in mix)
    levels_desc = ", ".join(f"{l} {n}문항" for l, n in mix)

    prompt = f"""한국인 성인 영어 학습자를 위한 {domain_kr} 4지선다 문제 {total_q}개를 만드세요.

난이도 구성: {levels_desc}
출처: {source_name}

[참고 텍스트]
{text[:1500]}

규칙:
- 문제와 보기는 영어로 작성
- explanation은 한국어로 (왜 정답인지, 오답 왜 틀렸는지 핵심만)
- 비즈니스·일상 맥락 우선
- 텍스트가 부족하면 주제에 맞게 창의적으로 보완

JSON 배열만 반환 (다른 텍스트 없이):
[
  {{
    "level": "B1",
    "question": "...",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct": "B",
    "explanation": "..."
  }}
]"""

    return _call_and_parse(prompt, mix)


async def _gen_grammar(grammar_info: dict, mix: list) -> list[dict]:
    """문법: 커리큘럼 주제 기반 문제 생성."""
    topic    = grammar_info["topic"]
    topic_kr = grammar_info["korean"]
    total_q  = sum(n for _, n in mix)
    levels_desc = ", ".join(f"{l} {n}문항" for l, n in mix)

    prompt = f"""한국인 성인 영어 학습자를 위한 문법 문제 출제자입니다.

오늘 주제: {topic} ({topic_kr})
난이도 구성: {levels_desc}
총 {total_q}문항

규칙:
- 비즈니스·실용 예문 위주
- 한국인이 자주 틀리는 패턴을 포함
- 빈칸 채우기 또는 올바른 문장 고르기 형식 혼용
- explanation은 핵심 문법 규칙을 한국어로 2~3줄 이내

JSON 배열만 반환:
[
  {{
    "level": "B1",
    "question": "...",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct": "B",
    "explanation": "..."
  }}
]"""

    return _call_and_parse(prompt, mix)


async def _gen_speaking(content_item: dict, mix: list) -> list[dict]:
    """말하기: 쉐도잉 스크립트 + 발음·표현 문제 3개 생성."""
    text        = content_item.get("text", "") or ""
    source_name = content_item.get("source", "")
    total_q     = sum(n for _, n in mix)
    levels_desc = ", ".join(f"{l} {n}문항" for l, n in mix)
    top_level   = mix[-1][0]

    prompt = f"""한국인 영어 학습자를 위한 말하기 학습 콘텐츠를 만드세요.

출처: {source_name}
참고 텍스트: {text[:800] if text else "비즈니스 영어 상황"}
난이도 구성: {levels_desc}

{total_q}개 문제를 아래 유형으로 구성:
1. 비즈니스 상황에서 적절한 표현 고르기 (level: {mix[0][0]})
2. 발음·억양 지식 문제 (연음, 강세 등) (level: {mix[1][0] if len(mix) > 1 else top_level})
3. 쉐도잉 스크립트 빈칸 채우기 (level: {top_level})

첫 번째 문제에 반드시 아래 필드 추가:
- "shadowing_script": 오늘 쉐도잉용 2~3문장 영어 스크립트 (비즈니스 맥락)
- "pronunciation_tip": 발음 팁 한국어 1줄 (예: 연음, 강세 주의점)

JSON 배열만 반환:
[
  {{
    "level": "B1",
    "shadowing_script": "...",
    "pronunciation_tip": "...",
    "question": "...",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct": "A",
    "explanation": "..."
  }},
  {{
    "level": "B1",
    "question": "...",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct": "C",
    "explanation": "..."
  }},
  {{
    "level": "B2",
    "question": "...",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct": "B",
    "explanation": "..."
  }}
]"""

    return _call_and_parse(prompt, mix)


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────

def _call_and_parse(prompt: str, mix: list) -> list[dict]:
    resp = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1800,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    return _parse_json(raw, mix)


def _parse_json(raw: str, mix: list) -> list[dict]:
    try:
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start == -1:
            raise ValueError("JSON 배열 없음")
        items = json.loads(raw[start:end])
        # level 누락 시 mix 순서로 보완
        levels_flat = [l for l, n in mix for _ in range(n)]
        for i, item in enumerate(items):
            if "level" not in item:
                item["level"] = levels_flat[i] if i < len(levels_flat) else mix[0][0]
        return items
    except Exception as e:
        log.warning(f"JSON 파싱 실패: {e} | 원본 앞 200자: {raw[:200]}")
        return _fallback_questions("unknown")


async def generate_daily_lesson(
    grammar_topic: str,
    grammar_topic_kr: str,
    reading_source: str,
    current_levels: dict,
    day_number: int,
) -> dict:
    """오늘의 학습 포인트를 Claude가 선택·생성. 문법/표현/어휘/발음/전략 중 최적 1개."""
    avg_level = max(
        ["A2", "B1", "B2", "C1"],
        key=lambda l: sum(1 for v in current_levels.values() if v >= l)
    ) if current_levels else "B1"

    prompt = f"""You are an English coach for a Korean business professional (targeting B2 by Oct 2026, current level ~{avg_level}).

Today's test covers:
- Grammar topic: {grammar_topic} ({grammar_topic_kr})
- Reading source: {reading_source}
- Day number: {day_number}

Choose ONE lesson type that adds the most value today and is NOT just a repeat of the grammar topic:
- GRAMMAR: a common confusion point Korean speakers face (different angle from today's test)
- EXPRESSION: a natural business idiom or phrase with 3 real-world examples
- VOCABULARY: 3 power words useful in business contexts, with collocations
- PRONUNCIATION: one sound/stress/rhythm issue specific to Korean speakers
- STRATEGY: a concrete study technique for one of today's 4 skills

Return ONLY valid JSON (no markdown, no extra text):
{{
  "type": "GRAMMAR|EXPRESSION|VOCABULARY|PRONUNCIATION|STRATEGY",
  "icon": "one emoji",
  "title": "Lesson title in English (max 8 words)",
  "subtitle": "한 줄 한국어 설명",
  "key_point": "The core rule or insight (English, 1-2 sentences)",
  "examples": [
    {{"text": "English example sentence", "note": "한국어 포인트"}},
    {{"text": "English example sentence", "note": "한국어 포인트"}},
    {{"text": "English example sentence", "note": "한국어 포인트"}}
  ],
  "tip": "실전 팁 한국어 1-2문장",
  "remember": "외우기 쉬운 한 줄 요약 (한국어 OK)"
}}"""

    try:
        resp = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        return json.loads(raw[start:end])
    except Exception as e:
        log.warning(f"daily_lesson 생성 실패: {e}")
        return {
            "type": "EXPRESSION",
            "icon": "💼",
            "title": "Business English of the Day",
            "subtitle": "오늘의 비즈니스 표현",
            "key_point": "\"Let's circle back\" means to return to a topic later.",
            "examples": [
                {"text": "Let's circle back on this after the meeting.", "note": "나중에 다시 논의하자"},
                {"text": "Can we circle back to the budget question?", "note": "예산 문제로 돌아가볼까요?"},
                {"text": "I'll circle back with you once I have the data.", "note": "데이터 확인 후 다시 연락드릴게요"},
            ],
            "tip": "회의에서 화제를 잠시 보류할 때 자연스럽게 쓸 수 있는 표현입니다.",
            "remember": "circle back = 나중에 다시 돌아오다",
        }


def _fallback_questions(domain: str) -> list[dict]:
    return [
        {
            "level": "B1",
            "question": "Which sentence is correct?",
            "options": {
                "A": "She go to the office every day.",
                "B": "She goes to the office every day.",
                "C": "She going to the office every day.",
                "D": "She gone to the office every day.",
            },
            "correct": "B",
            "explanation": "3인칭 단수 현재시제에서는 동사에 -s/es를 붙입니다. (She goes)",
        }
    ] * 3
