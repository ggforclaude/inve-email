"""
Improve_Eng/question_generator.py
Claude API로 영역별 문제와 학습 콘텐츠를 생성합니다.

듣기 구조: SHORT 클립 1개 × 2문항 (기존 3-티어 → 단일 클립으로 축소)
문제 총합: 듣기 2 + 문법 3 + 독해 3 + 말하기 3 = 11문항

신규 함수:
  generate_listening_script()  → 듣기 영문 + 한글 스크립트
  generate_daily_learning()    → 5영역 학습 콘텐츠 (문법/듣기/비즈니스/독해/어원)
    - 학습 연구 기반: 분산학습(SRS) + 교차연습(Interleaving) + 회상훈련(Retrieval practice)
"""
import anthropic
import json
import logging

log = logging.getLogger(__name__)
_client = anthropic.Anthropic()

LEVEL_ORDER  = ["A2", "B1", "B2", "C1"]
LEVEL_COLORS = {"A2": "초급", "B1": "중하급", "B2": "중상급", "C1": "고급"}

DOMAIN_KR = {
    "listening": "듣기",
    "grammar":   "문법",
    "reading":   "독해",
    "speaking":  "말하기",
}


def _adaptive_mix(current_level: str, n: int = 2) -> list[tuple[str, int]]:
    """현재 레벨 1문항 + 상위 레벨 n-1문항 (i+1 Input Hypothesis)."""
    idx      = LEVEL_ORDER.index(current_level) if current_level in LEVEL_ORDER else 1
    next_lvl = LEVEL_ORDER[min(idx + 1, len(LEVEL_ORDER) - 1)]
    if n == 1:
        return [(current_level, 1)]
    return [(current_level, 1), (next_lvl, n - 1)]


BASELINE_MIX_3 = [("A2", 1), ("B1", 1), ("B2", 1)]
BASELINE_MIX_2 = [("B1", 1), ("B2", 1)]


# ── 메인: 문제 생성 ───────────────────────────────────────────────────────────

async def generate_all_questions(
    content: dict,
    current_levels: dict,
    is_baseline: bool,
    day_number: int,
) -> dict:
    """11문항 생성: 듣기 2 + 문법 3 + 독해 3 + 말하기 3.
    content["listening"]은 단일 dict (리스트 아님).
    """
    results = {}

    # 듣기: 단일 SHORT 클립 × 2문항
    audio_item = content.get("listening", {})
    if is_baseline:
        listen_mix = [("B1", 2)]
    else:
        lvl = current_levels.get("listening", "B1")
        listen_mix = _adaptive_mix(lvl, n=2)
    try:
        qs = await _gen_content_questions("listening", audio_item, listen_mix)
    except Exception as e:
        log.error(f"[listening] 문제 생성 실패: {e}")
        qs = _fallback_questions("listening")[:2]
    results["listening"] = {"audio": audio_item, "questions": qs}

    # 문법 / 독해 / 말하기 (각 3문항)
    for domain in ["grammar", "reading", "speaking"]:
        mix = BASELINE_MIX_3 if is_baseline else _adaptive_mix(
            current_levels.get(domain, "B1"), n=3
        )
        try:
            if domain == "grammar":
                results[domain] = await _gen_grammar(content["grammar"], mix)
            elif domain == "speaking":
                results[domain] = await _gen_speaking(content["speaking"], mix)
            else:
                results[domain] = await _gen_content_questions(domain, content[domain], mix)
        except Exception as e:
            log.error(f"[{domain}] 문제 생성 실패: {e}")
            results[domain] = _fallback_questions(domain)

    return results


# ── 듣기 스크립트 생성 ────────────────────────────────────────────────────────

async def generate_listening_script(audio_item: dict) -> dict:
    """오디오 클립에 대한 영문 + 한글 스크립트 생성.
    RSS 텍스트를 기반으로 2-4문장 스크립트를 만들고, 한글 번역을 제공.
    Returns: {"script_en": str, "script_kr": str, "key_vocab": str}
    """
    title   = audio_item.get("title", "Daily English Practice")
    source  = audio_item.get("source", "")
    text    = audio_item.get("text", "")

    prompt = f"""You are creating a listening comprehension script for a Korean adult learning English.

Source: {source}
Title: {title}
Reference text (may be partial or empty):
{text[:800] if text else "(No reference text — create an appropriate short script)"}

Task: Write a SHORT listening script (2-4 sentences, ~60-80 words) that:
1. Is natural spoken English (not formal writing)
2. Contains 1-2 useful business or daily vocabulary words
3. Is based on the reference text topic (if available)
4. Is at B1-B2 level

Return ONLY valid JSON:
{{
  "script_en": "Full English script here (2-4 sentences, natural spoken style)",
  "script_kr": "정확한 한국어 번역 (직역이 아닌 자연스러운 번역)",
  "key_vocab": "핵심 어휘 1-2개: word1 — 한국어 뜻; word2 — 한국어 뜻"
}}"""

    try:
        resp = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw   = resp.content[0].text.strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        return json.loads(raw[start:end])
    except Exception as e:
        log.warning(f"listening_script 생성 실패: {e}")
        return {
            "script_en": "Today we're looking at a common English expression used in business settings. "
                         "When someone says 'Let's take this offline,' they mean continuing a conversation "
                         "privately, outside the current meeting.",
            "script_kr": "오늘은 비즈니스 환경에서 자주 쓰이는 영어 표현을 살펴봅니다. "
                         "'Let's take this offline'은 현재 회의 밖에서, "
                         "즉 개인적으로 대화를 이어가자는 의미입니다.",
            "key_vocab": "offline — 회의 밖에서 (오프라인 X); take [something] offline — 나중에 따로 논의하다",
        }


# ── 5영역 학습 콘텐츠 생성 ────────────────────────────────────────────────────

async def generate_daily_learning(
    grammar_info: dict,
    listening_item: dict,
    listening_script: dict,
    etymology: dict,
    pronunciation: dict,
    current_levels: dict,
    day_number: int,
) -> dict:
    """7영역 학습 콘텐츠 생성 (학습 연구 기반 설계).

    설계 원칙:
    - Spaced Repetition (Ebbinghaus): 새 내용 소개 후 다음 날 퀴즈로 회상
    - Interleaved Practice (Kornell & Bjork 2008): 매일 다른 문법/발음 카테고리
    - Input Hypothesis (Krashen): 현재 레벨 +1 수준의 입력
    - Elaborative Interrogation: 왜 그런지 설명 포함 (어원, 규칙 이유)
    - Collocation-based Vocabulary (Nation 2001): 문맥+연어로 어휘 학습

    Returns: {grammar, listening, business, reading, pronunciation, vocabulary, etymology_lesson}
    """
    avg_level = "B1"
    if current_levels:
        level_vals = {"A2": 0, "B1": 1, "B2": 2, "C1": 3}
        avg = sum(level_vals.get(v, 1) for v in current_levels.values()) / len(current_levels)
        avg_level = ["A2", "B1", "B2", "C1"][round(avg)]

    grammar_topic    = grammar_info.get("topic", "")
    grammar_topic_kr = grammar_info.get("korean", "")
    listen_title     = listening_item.get("title", "")
    listen_source    = listening_item.get("source", "")
    pron_focus       = pronunciation.get("focus", "")
    pron_rule        = pronunciation.get("rule", "")
    pron_examples    = pronunciation.get("examples", [])

    prompt = f"""You are an expert English coach for Korean business professionals.
Current level: ~{avg_level} | Day: {day_number}
Grammar topic today: {grammar_topic} ({grammar_topic_kr})
Pronunciation focus today: {pron_focus}
Etymology word: {etymology.get('word', '')}

Generate detailed learning content. Grammar and pronunciation MUST be thorough.
Return ONLY valid JSON (no markdown):
{{
  "grammar": {{
    "topic_en": "{grammar_topic}",
    "topic_kr": "{grammar_topic_kr}",
    "core_rule": "핵심 규칙 3-4문장 충분히 설명 (한국어) — 언제, 왜, 어떻게 쓰는지 포함",
    "when_to_use": "구체적으로 어떤 상황에서 사용하나 (한국어, 2-3문장)",
    "examples": [
      {{"en": "비즈니스 예문 1", "kr": "한국어 번역"}},
      {{"en": "비즈니스 예문 2", "kr": "한국어 번역"}},
      {{"en": "일상 예문 3", "kr": "한국어 번역"}}
    ],
    "contrast_en": "❌ 틀리기 쉬운 예문 (영어)",
    "contrast_kr": "왜 틀렸는지 설명 (한국어)",
    "common_mistakes": "한국인이 자주 틀리는 패턴 2-3가지 (한국어)",
    "remember": "외우기 쉬운 한 줄 기억법 (한국어, 20자 이내)"
  }},
  "business": {{
    "expression": "Business English expression",
    "meaning_kr": "한국어 의미",
    "example_en": "자연스러운 비즈니스 예문",
    "example_kr": "한국어 번역",
    "when_to_use": "어떤 상황에서 쓰나 (한국어 1줄)"
  }},
  "reading": {{
    "strategy": "독해 전략 이름 (한국어 OK)",
    "how_to": "적용 방법 (한국어, 2-3문장)",
    "why_effective": "연구 근거 포함 효과 설명 (한국어 1-2문장)",
    "example_passage": "3-4 sentence English passage (B1-B2 level, business or general topic)",
    "example_application": "위 지문에 이 전략을 어떻게 적용하나 (한국어, 2-3문장)"
  }},
  "pronunciation": {{
    "focus": "{pron_focus}",
    "rule": "{pron_rule}",
    "examples": {json.dumps(pron_examples, ensure_ascii=False)},
    "common_error": "한국인이 이 발음을 틀리는 방식과 이유 (한국어)",
    "practice_sentence": "이 발음을 연습할 수 있는 영어 문장 1개",
    "tip": "발음 교정 팁 (한국어, 1-2문장)"
  }},
  "vocabulary": [
    {{
      "word": "영단어1",
      "level": "B1 또는 B2",
      "meaning_kr": "한국어 뜻",
      "collocation": "자주 함께 쓰는 단어 조합 (영어, 2-3개)",
      "example_en": "자연스러운 예문",
      "example_kr": "한국어 번역"
    }},
    {{
      "word": "영단어2",
      "level": "B1 또는 B2",
      "meaning_kr": "한국어 뜻",
      "collocation": "자주 함께 쓰는 단어 조합 (영어, 2-3개)",
      "example_en": "자연스러운 예문",
      "example_kr": "한국어 번역"
    }},
    {{
      "word": "영단어3",
      "level": "B2",
      "meaning_kr": "한국어 뜻",
      "collocation": "자주 함께 쓰는 단어 조합 (영어, 2-3개)",
      "example_en": "자연스러운 예문",
      "example_kr": "한국어 번역"
    }}
  ],
  "etymology_lesson": {{
    "word": "{etymology.get('word', '')}",
    "origin": "{etymology.get('origin', '')}",
    "story_kr": "{etymology.get('story', '')}",
    "meaning_kr": "{etymology.get('meaning', '')}",
    "memory_tip": "어원 스토리로 단어를 기억하는 팁 (한국어, 1줄)"
  }}
}}"""

    try:
        resp = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw   = resp.content[0].text.strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        data  = json.loads(raw[start:end])
        data["listening"] = {
            "title":     listen_title,
            "source":    listen_source,
            "audio_url": listening_item.get("audio_url", ""),
            "page_url":  listening_item.get("url", ""),
            "script_en": listening_script.get("script_en", ""),
            "script_kr": listening_script.get("script_kr", ""),
            "key_vocab": listening_script.get("key_vocab", ""),
        }
        return data
    except Exception as e:
        log.warning(f"daily_learning 생성 실패: {e}")
        return _fallback_learning(grammar_topic, grammar_topic_kr, listening_item, listening_script, etymology, pronunciation)


def _fallback_learning(grammar_topic, grammar_topic_kr, listening_item, listening_script, etymology, pronunciation={}) -> dict:
    return {
        "grammar": {
            "topic_en":       grammar_topic,
            "topic_kr":       grammar_topic_kr,
            "core_rule":      "오늘 문법 규칙을 퀴즈 문제 해설에서 확인하세요.",
            "when_to_use":    "퀴즈를 풀며 맥락을 파악하세요.",
            "examples": [
                {"en": "I have worked here for five years.", "kr": "5년간 일해왔다 (지금도 재직 중)"},
                {"en": "She has already finished the report.", "kr": "그녀는 이미 보고서를 끝냈다"},
                {"en": "We have never met before.", "kr": "우리는 전에 만난 적이 없다"},
            ],
            "contrast_en":    "I worked here for five years.",
            "contrast_kr":    "단순과거 → 이미 그만뒀을 때 사용.",
            "common_mistakes": "① '어제' 같은 과거 시점과 현재완료 혼용 ② have+동사원형 실수",
            "remember":       "경험·결과·지속 → 현재완료",
        },
        "listening": {
            "title":     listening_item.get("title", ""),
            "source":    listening_item.get("source", ""),
            "audio_url": listening_item.get("audio_url", ""),
            "page_url":  listening_item.get("url", ""),
            "script_en": listening_script.get("script_en", ""),
            "script_kr": listening_script.get("script_kr", ""),
            "key_vocab": listening_script.get("key_vocab", ""),
        },
        "business": {
            "expression":  "Let's circle back",
            "meaning_kr":  "나중에 다시 돌아오다",
            "example_en":  "Let's circle back on the budget after the Q2 data arrives.",
            "example_kr":  "Q2 데이터가 나오면 예산 건으로 다시 돌아오죠.",
            "when_to_use": "회의 중 결론을 잠시 보류할 때",
        },
        "reading": {
            "strategy":            "Topic Sentence 스캔",
            "how_to":              "각 단락 첫 문장만 먼저 읽어 전체 구조를 파악한 후 세부 내용을 읽습니다.",
            "why_effective":       "스키마(schema) 형성 후 읽을 때 이해도가 30% 이상 향상됩니다.",
            "example_passage":     "The global economy has shown signs of recovery. Consumer spending increased by 3% last quarter. However, inflation remains a concern for policymakers.",
            "example_application": "첫 문장 'The global economy has shown signs of recovery'에서 주제를 파악한 후 나머지를 읽으면 세부 내용이 자연스럽게 연결됩니다.",
        },
        "pronunciation": {
            "focus":            pronunciation.get("focus", ""),
            "rule":             pronunciation.get("rule", ""),
            "examples":         pronunciation.get("examples", []),
            "common_error":     "한국어 발음 습관이 영향을 미칩니다.",
            "practice_sentence":"Please feel free to call me if you have any questions.",
            "tip":              "거울 앞에서 입 모양을 확인하며 연습하세요.",
        },
        "vocabulary": [
            {
                "word":       "allocate",
                "level":      "B2",
                "meaning_kr": "할당하다, 배정하다",
                "collocation": "allocate resources / allocate time / allocate budget",
                "example_en": "We need to allocate more resources to the marketing team.",
                "example_kr": "마케팅팀에 더 많은 자원을 배정해야 합니다.",
            },
        ],
        "etymology_lesson": {
            "word":       etymology.get("word", ""),
            "origin":     etymology.get("origin", ""),
            "story_kr":   etymology.get("story", ""),
            "meaning_kr": etymology.get("meaning", ""),
            "memory_tip": "어원 스토리를 이미지로 상상하면 오래 기억됩니다.",
        },
    }


# ── 오답 분석 ─────────────────────────────────────────────────────────────────

async def generate_wrong_analysis(wrong_items: list[dict]) -> str:
    """당일 인라인용 짧은 오답 설명 HTML (200자 이내)."""
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

<div class="wi"><span class="tag">[영역]</span> <b>핵심</b>: 설명...</div>"""

    resp = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


async def generate_detailed_wrong_analysis(wrong_items: list[dict]) -> dict:
    """다음날 상세 학습 피드백. Returns {"html": str, "telegram": str}."""
    if not wrong_items:
        return {"html": "", "telegram": ""}

    items_text = "\n".join(
        f"Q{i+1}. [{DOMAIN_KR.get(item['domain'], item['domain'])}·{item['level']}]\n"
        f"문제: {item['question']}\n"
        f"정답: {item['correct']} / 내 선택: {item.get('chosen', '?')}\n"
        f"기본 설명: {item.get('explanation', '')}"
        for i, item in enumerate(wrong_items[:5])
    )

    prompt = f"""당신은 한국인 비즈니스 영어 학습자를 가르치는 전문 영어 강사입니다.

[오답 목록]
{items_text}

각 오답에 대해 반드시 아래 5가지를 모두 작성하세요:
1. 핵심 개념: 기초부터 단계별 설명. 한국인이 헷갈리는 이유 명시
2. 문법/어휘 규칙: 정확한 규칙, 예외 사항 포함
3. 예시 3개 이상: 영어 예문 + 한국어 해석 (비즈니스 맥락 포함)
4. 한국인 실수 패턴: 비슷하게 틀리는 유사 패턴과 비교
5. 암기팁: 기억하기 쉬운 규칙 또는 연상법

JSON으로 반환 (다른 텍스트 없이):
{{
  "items": [
    {{
      "q_num": 1,
      "domain": "문법",
      "summary": "문제 한줄 요약",
      "concept": "핵심 개념 설명 (상세)",
      "rule": "문법/어휘 규칙",
      "examples": ["영어 예문 1 — 한국어 해석", "예문 2 — 해석", "예문 3 — 해석"],
      "common_mistakes": "한국인 실수 패턴 비교",
      "tip": "암기팁"
    }}
  ]
}}"""

    try:
        resp = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw   = resp.content[0].text.strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        data  = json.loads(raw[start:end])
        items = data.get("items", [])
    except Exception as e:
        log.warning(f"detailed_wrong_analysis 생성 실패: {e}")
        return {"html": "", "telegram": ""}

    html_parts = []
    for item in items:
        ex_html = "".join(
            f'<div class="detail-ex">• {ex}</div>'
            for ex in item.get("examples", [])
        )
        html_parts.append(f"""<div class="detail-item">
  <div class="detail-q-label">Q{item.get('q_num', '')}. [{item.get('domain', '')}] {item.get('summary', '')}</div>
  <div class="detail-section"><b>📌 핵심 개념</b><p>{item.get('concept', '')}</p></div>
  <div class="detail-section"><b>📐 규칙</b><p>{item.get('rule', '')}</p></div>
  <div class="detail-section"><b>💬 예시</b>{ex_html}</div>
  <div class="detail-section"><b>⚠️ 한국인 실수 패턴</b><p>{item.get('common_mistakes', '')}</p></div>
  <div class="detail-tip">🧠 암기팁: {item.get('tip', '')}</div>
</div>""")
    html = "\n".join(html_parts)

    tg_parts = []
    for item in items:
        ex_lines = "\n".join(f"  • {ex}" for ex in item.get("examples", []))
        tg_parts.append(
            f"<b>Q{item.get('q_num', '')}. [{item.get('domain', '')}] {item.get('summary', '')}</b>\n\n"
            f"📌 <b>핵심 개념</b>\n{item.get('concept', '')}\n\n"
            f"📐 <b>규칙</b>\n{item.get('rule', '')}\n\n"
            f"💬 <b>예시</b>\n{ex_lines}\n\n"
            f"⚠️ <b>실수 패턴</b>\n{item.get('common_mistakes', '')}\n\n"
            f"🧠 <b>암기팁</b>\n{item.get('tip', '')}"
        )
    telegram = "\n\n" + "─" * 30 + "\n\n".join(tg_parts)

    return {"html": html, "telegram": telegram}


# ── 영역별 문제 생성 ──────────────────────────────────────────────────────────

async def _gen_content_questions(domain: str, content_item: dict, mix: list) -> list[dict]:
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
- "shadowing_script": 오늘 쉐도잉용 2~3문장 영어 스크립트 (비즈니스 맥락, 자연스러운 구어체)
- "pronunciation_tip": 발음 팁 한국어 1줄

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


# ── 공통 헬퍼 ─────────────────────────────────────────────────────────────────

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
        levels_flat = [l for l, n in mix for _ in range(n)]
        for i, item in enumerate(items):
            if "level" not in item:
                item["level"] = levels_flat[i] if i < len(levels_flat) else mix[0][0]
        return items
    except Exception as e:
        log.warning(f"JSON 파싱 실패: {e} | 원본 앞 200자: {raw[:200]}")
        return _fallback_questions("unknown")


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
