"""
Improve_Eng/page_builder.py
일일 영어 테스트 HTML 페이지를 생성합니다.
docs/YYYY-MM-DD/index.html 로 저장 → GitHub Pages 자동 배포.

변경사항:
  - 듣기 3-티어 섹션 (Short/Medium/Long 각각)
  - 다음날 상세 오답 분석 (긴 설명)
  - 말하기 섹션에 Web Speech API 음성 녹음 + 발음 체크 기능
"""
import json
import os
import pathlib
from datetime import date
from typing import Optional

APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL", "")
PAGES_BASE_URL  = os.environ.get("PAGES_BASE_URL", "https://ggforclaude.github.io/inve-email")

DOMAINS = ["listening", "grammar", "reading", "speaking"]
DOMAIN_META = {
    "listening": ("🎧", "Listening",  "#0ea5e9", "#e0f2fe"),
    "grammar":   ("✏️", "Grammar",    "#8b5cf6", "#ede9fe"),
    "reading":   ("📖", "Reading",    "#22c55e", "#dcfce7"),
    "speaking":  ("🗣️", "Speaking",   "#f59e0b", "#fef9c3"),
}
TIER_META = {
    "short":  ("⚡", "Short",  "#0ea5e9", "#e0f2fe"),
    "medium": ("🎵", "Medium", "#0284c7", "#bae6fd"),
    "long":   ("🎙️", "Long",   "#0369a1", "#7dd3fc"),
}
LEVEL_COLOR = {"A2": "#6ee7b7", "B1": "#93c5fd", "B2": "#c4b5fd", "C1": "#fca5a5"}
LESSON_COLORS = {
    "GRAMMAR":       ("#eef2ff", "#4338ca", "#818cf8"),
    "EXPRESSION":    ("#fff7ed", "#c2410c", "#fb923c"),
    "VOCABULARY":    ("#f0fdf4", "#15803d", "#4ade80"),
    "PRONUNCIATION": ("#fdf4ff", "#7e22ce", "#c084fc"),
    "STRATEGY":      ("#eff6ff", "#1d4ed8", "#60a5fa"),
}


def build_daily_page(
    today: date,
    day_number: int,
    questions: dict,
    content: dict,
    daily_lesson: dict,
    current_levels: dict,
    prev_wrong_analysis: Optional[str],
    prev_detailed_analysis: Optional[str] = None,
) -> pathlib.Path:
    html = _render(today, day_number, questions, content,
                   daily_lesson, current_levels, prev_wrong_analysis, prev_detailed_analysis)
    base = pathlib.Path(__file__).parent.parent / "docs" / str(today)
    base.mkdir(parents=True, exist_ok=True)
    out = base / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


# ── 데이터 추출 ───────────────────────────────────────────────────────────────

def _flatten_questions(questions: dict):
    """questions dict → (correct_list, explanation_list, domain_list, all_qs)
    듣기는 그룹 구조에서 펼쳐서 처리."""
    correct, explanations, domain_list, all_qs = [], [], [], []

    # 듣기: [{"audio": ..., "questions": [...]}, ...]
    for group in questions.get("listening", []):
        for q in group.get("questions", []):
            correct.append(q.get("correct", "A").strip().upper())
            explanations.append(q.get("explanation", ""))
            domain_list.append("listening")
            all_qs.append(("listening", q))

    for domain in ["grammar", "reading", "speaking"]:
        for q in questions.get(domain, []):
            correct.append(q.get("correct", "A").strip().upper())
            explanations.append(q.get("explanation", ""))
            domain_list.append(domain)
            all_qs.append((domain, q))

    return correct, explanations, domain_list, all_qs


# ── HTML 렌더링 ───────────────────────────────────────────────────────────────

def _render(today, day_number, questions, content, daily_lesson, current_levels,
            prev_wrong_analysis, prev_detailed_analysis):
    correct, explanations, domain_list, all_qs = _flatten_questions(questions)
    total = len(correct)

    js_correct = json.dumps(correct, ensure_ascii=False)
    js_expls   = json.dumps(explanations, ensure_ascii=False)
    js_dnames  = json.dumps(domain_list, ensure_ascii=False)
    js_date    = str(today)
    js_asurl   = APPS_SCRIPT_URL

    # 섹션 HTML 구성
    sections_html = ""
    q_num = 0

    # 듣기: 3개 그룹 각각 섹션
    for group in questions.get("listening", []):
        audio_item = group["audio"]
        qs         = group["questions"]
        sections_html += _listening_group_html(audio_item, qs, q_num)
        q_num += len(qs)

    # 나머지 도메인
    for domain in ["grammar", "reading", "speaking"]:
        qs = questions.get(domain, [])
        if not qs:
            continue
        sections_html += _section_html(domain, qs, content.get(domain, {}), q_num)
        q_num += len(qs)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>Day {day_number} — Improve English</title>
<style>
{_css()}
</style>
</head>
<body>

{_header_html(today, day_number, current_levels)}

<div class="container">

  {_prev_analysis_html(prev_wrong_analysis, prev_detailed_analysis)}

  {_lesson_html(daily_lesson)}

  <div class="progress-wrap" id="progressWrap">
    <div class="progress-label">
      <span>진행률</span>
      <span id="progressText">0 / {total} 문항</span>
    </div>
    <div class="progress-bar-bg">
      <div class="progress-bar-fill" id="progressFill" style="width:0%"></div>
    </div>
  </div>

  {sections_html}

  <div class="submit-area" id="submitArea">
    <p class="submit-hint">모든 문항에 답한 후 제출하세요</p>
    <button class="btn-submit" id="submitBtn" onclick="submitAnswers()">
      📝 제출하기
    </button>
  </div>

  <div class="results-panel" id="resultsPanel" style="display:none"></div>

</div>

<script>
const CORRECT  = {js_correct};
const EXPLS    = {js_expls};
const DNAMES   = {js_dnames};
const TOTAL    = {total};
const TODAY    = "{js_date}";
const AS_URL   = "{js_asurl}";
const DOMAINS_KR = {{listening:"듣기",grammar:"문법",reading:"독해",speaking:"말하기"}};

let answers   = new Array(TOTAL).fill(null);
let submitted = false;

document.querySelectorAll(".opt").forEach(btn => {{
  btn.addEventListener("click", function() {{
    if (submitted) return;
    const q = parseInt(this.dataset.q);
    const l = this.dataset.l;
    document.querySelectorAll(`.opt[data-q="${{q}}"]`).forEach(b => b.classList.remove("sel"));
    this.classList.add("sel");
    answers[q] = l;
    updateProgress();
  }});
}});

function updateProgress() {{
  const n = answers.filter(a => a !== null).length;
  document.getElementById("progressText").textContent = n + " / " + TOTAL + " 문항";
  document.getElementById("progressFill").style.width = (n / TOTAL * 100) + "%";
}}

function submitAnswers() {{
  if (submitted) return;
  const unanswered = answers.filter(a => a === null).length;
  if (unanswered > 0) {{
    alert("아직 " + unanswered + "문항에 답하지 않았어요.");
    return;
  }}
  submitted = true;
  document.getElementById("submitBtn").disabled = true;
  document.getElementById("submitBtn").textContent = "채점 중...";

  let correct = 0;
  const domSc = {{listening:{{c:0,t:0}},grammar:{{c:0,t:0}},reading:{{c:0,t:0}},speaking:{{c:0,t:0}}}};
  const wrongItems = [];

  answers.forEach((ans, i) => {{
    const domain = DNAMES[i];
    const ok     = CORRECT[i];
    const isOk   = ans === ok;
    if (isOk) {{ correct++; domSc[domain].c++; }}
    else {{ wrongItems.push({{q:i+1, domain, chosen:ans, correct:ok, expl:EXPLS[i]}}); }}
    domSc[domain].t++;

    const qEl = document.getElementById("q" + i);
    if (qEl) qEl.classList.add(isOk ? "q-correct" : "q-wrong");
    document.querySelectorAll(`.opt[data-q="${{i}}"]`).forEach(b => {{
      if (b.dataset.l === ok)  b.classList.add("opt-correct");
      if (b.dataset.l === ans && !isOk) b.classList.add("opt-wrong");
    }});
    const explEl = document.getElementById("expl" + i);
    if (explEl) explEl.style.display = "block";
  }});

  showResults(correct, domSc, wrongItems);
  saveResults(answers, correct, domSc);
}}

function showResults(correct, domSc, wrongItems) {{
  const pct   = Math.round(correct / TOTAL * 100);
  const color = pct >= 80 ? "#22c55e" : pct >= 60 ? "#f59e0b" : "#ef4444";
  const emoji = pct >= 80 ? "🎉" : pct >= 60 ? "👍" : "💪";

  let domHtml = "";
  ["listening","grammar","reading","speaking"].forEach(d => {{
    const s = domSc[d];
    const p = s.t > 0 ? Math.round(s.c / s.t * 100) : 0;
    const c = p >= 80 ? "#22c55e" : p >= 60 ? "#f59e0b" : "#ef4444";
    domHtml += `<div class="dom-score"><div class="dom-pct" style="color:${{c}}">${{p}}%</div><div class="dom-name">${{DOMAINS_KR[d]}}</div></div>`;
  }});

  let wrongHtml = "";
  wrongItems.forEach(w => {{
    wrongHtml += `<div class="wrong-item"><span class="wrong-tag">${{DOMAINS_KR[w.domain]}}</span> Q${{w.q}} — 선택: <b>${{w.chosen}}</b> / 정답: <b>${{w.correct}}</b><div class="wrong-expl">${{w.expl}}</div></div>`;
  }});

  const panel = document.getElementById("resultsPanel");
  panel.innerHTML = `
    <div class="result-score" style="color:${{color}}">${{emoji}} ${{pct}}%</div>
    <div class="result-sub">${{correct}} / ${{TOTAL}} 정답</div>
    <div class="dom-scores">${{domHtml}}</div>
    ${{wrongItems.length > 0 ? '<div class="wrong-title">오늘의 오답</div>' + wrongHtml : '<div class="all-correct">전체 정답! 완벽해요 🌟</div>'}}
    <div class="result-note">내일 아침 테스트 페이지에서 상세 피드백을 확인하세요.</div>
  `;
  panel.style.display = "block";
  panel.scrollIntoView({{behavior: "smooth", block: "start"}});
  document.getElementById("submitArea").style.display = "none";
}}

function saveResults(answers, correct, domSc) {{
  if (!AS_URL) return;
  // 문항별 정오답: 정답이면 "O", 틀리면 "X"
  const qResults = answers.map((ans, i) => (ans === CORRECT[i] ? "O" : "X")).join(",");
  const params = new URLSearchParams({{
    date: TODAY, answers: answers.join(","), correct,
    results: qResults,
    listening: domSc.listening.c + "/" + domSc.listening.t,
    grammar:   domSc.grammar.c   + "/" + domSc.grammar.t,
    reading:   domSc.reading.c   + "/" + domSc.reading.t,
    speaking:  domSc.speaking.c  + "/" + domSc.speaking.t,
  }});
  fetch(AS_URL + "?" + params.toString(), {{mode:"no-cors"}}).catch(() => {{}});
}}

// ── 말하기 음성 인식 ───────────────────────────────────────────────────────
const TH_WORDS   = new Set(["the","this","that","these","those","think","thought","through","three","there","their","they","though","than","then","them","with","both","other","another","either"]);
const RL_WORDS   = new Set(["really","result","role","rule","level","rely","rally","recall","roll","relate","rely","already","world","early","clearly","regularly","literally","carefully"]);
const FINAL_CLUSTERS = new Set(["next","text","acts","helped","asked","mixed","worked","talked","jumped","changed","missed","fixed","asked","looked","passed"]);
const SHORT_VOWELS   = new Set(["ship","sheet","hit","heat","sit","seat","bit","beat","live","leave","fill","feel","will","wheel","it","eat"]);

function getPhonemeIssue(word) {{
  if (TH_WORDS.has(word))         return "th 발음 — 혀끝을 윗니에 살짝 대고 공기를 내뱉으세요 (예: /ð/ or /θ/)";
  if (RL_WORDS.has(word))         return "r/l 구분 — r은 혀를 말아 올리고, l은 혀끝을 윗잇몸에";
  if (FINAL_CLUSTERS.has(word))   return "어말 자음군 — 끝 자음 두 개를 모두 발음하세요";
  if (SHORT_VOWELS.has(word))     return "모음 길이 — 짧은 소리와 긴 소리를 구분하세요";
  if (word.endsWith("ed"))        return "-ed 발음 — /t/, /d/, /ɪd/ 중 올바른 발음 확인";
  if (word.endsWith("s") || word.endsWith("es")) return "-s 발음 — /s/, /z/, /ɪz/ 중 올바른 발음";
  if (word.includes("v"))         return "v 발음 — 윗니를 아랫입술에 대고 진동시키세요 (b와 구분)";
  if (word.includes("f") && word.length > 2) return "f 발음 — 윗니를 아랫입술에 대고 공기를 내뱉으세요";
  return "";
}}

function startSpeechRecognition(scriptId, btnId, statusId, transcriptId, feedbackId) {{
  const scriptEl = document.getElementById(scriptId);
  const script   = scriptEl ? scriptEl.textContent.trim() : "";
  const btn      = document.getElementById(btnId);
  const statusEl = document.getElementById(statusId);
  const transEl  = document.getElementById(transcriptId);
  const feedEl   = document.getElementById(feedbackId);

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {{
    statusEl.textContent = "⚠️ Chrome 또는 Edge에서 지원됩니다";
    return;
  }}

  const rec = new SR();
  rec.lang = "en-US";
  rec.interimResults = true;
  rec.maxAlternatives = 1;

  btn.textContent = "⏹ 중지";
  btn.onclick = () => rec.stop();
  statusEl.textContent = "🔴 녹음 중...";
  transEl.textContent = "";
  feedEl.innerHTML = "";

  let finalTranscript = "";

  rec.onresult = e => {{
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {{
      if (e.results[i].isFinal) finalTranscript += e.results[i][0].transcript + " ";
      else interim += e.results[i][0].transcript;
    }}
    transEl.textContent = (finalTranscript + interim).trim();
  }};

  rec.onend = () => {{
    btn.textContent = "🎤 다시 녹음";
    btn.onclick = () => startSpeechRecognition(scriptId, btnId, statusId, transcriptId, feedbackId);
    statusEl.textContent = "✅ 녹음 완료";
    analyzeSpeech(finalTranscript.trim(), script, feedEl);
  }};

  rec.onerror = e => {{
    statusEl.textContent = "❌ 오류: " + e.error;
    btn.textContent = "🎤 다시 시도";
    btn.onclick = () => startSpeechRecognition(scriptId, btnId, statusId, transcriptId, feedbackId);
  }};

  rec.start();
}}

function analyzeSpeech(spoken, expected, feedEl) {{
  if (!spoken) {{ feedEl.innerHTML = '<div class="rec-warn">음성이 감지되지 않았습니다. 다시 시도해 주세요.</div>'; return; }}

  const normalize = s => s.toLowerCase().replace(/[^a-z'\\s]/g,"").split(/\\s+/).filter(Boolean);
  const expWords = normalize(expected);
  const spkSet   = new Set(normalize(spoken));

  const missed = expWords.filter(w => !spkSet.has(w));
  const score  = Math.round((1 - missed.length / Math.max(expWords.length, 1)) * 100);

  if (missed.length === 0) {{
    feedEl.innerHTML = '<div class="rec-perfect">🌟 완벽합니다! 모든 단어가 인식되었어요.</div>';
    return;
  }}

  let html = `<div class="rec-score">정확도: <b style="color:${{score>=80?'#22c55e':score>=60?'#f59e0b':'#ef4444'}}">${{score}}%</b> (${{expWords.length - missed.length}}/${{expWords.length}} 단어 인식)</div>`;
  html += '<div class="rec-missed"><b>인식되지 않은 단어:</b><ul>';
  missed.forEach(w => {{
    const tip = getPhonemeIssue(w);
    html += `<li><b>${{w}}</b>${{tip ? ' <span class="rec-tip">→ ' + tip + '</span>' : ''}}</li>`;
  }});
  html += '</ul></div>';

  if (score < 70) {{
    html += '<div class="rec-advice">💡 천천히 또렷하게 다시 말해보세요. 속도보다 정확성이 중요합니다.</div>';
  }} else if (score < 90) {{
    html += '<div class="rec-advice">👍 거의 다 됐어요! 위 단어들을 집중 연습해 보세요.</div>';
  }}

  feedEl.innerHTML = html;
}}
</script>
</body>
</html>"""


# ── 섹션 빌더 ─────────────────────────────────────────────────────────────────

def _header_html(today: date, day_number: int, current_levels: dict) -> str:
    badges = ""
    kr_map = {"listening": "듣기", "grammar": "문법", "reading": "독해", "speaking": "말하기"}
    for domain in DOMAINS:
        icon, _, color, _ = DOMAIN_META[domain]
        lvl = current_levels.get(domain, "B1")
        col = LEVEL_COLOR.get(lvl, "#e5e7eb")
        badges += f'<span class="lv-badge" style="background:{col}">{icon} {kr_map[domain]}: {lvl}</span>'

    return f"""<header>
  <div class="hdr-top">
    <span class="hdr-sub">Improve English &nbsp;·&nbsp; Day {day_number}</span>
    <span class="hdr-date">{today.strftime('%b %d, %Y')}</span>
  </div>
  <h1 class="hdr-title">오늘의 영어 테스트 📚</h1>
  <p class="hdr-meta">4개 영역 · 듣기 3클립 포함 · 약 25분</p>
  <div class="lv-badges">{badges}</div>
</header>"""


def _prev_analysis_html(short_html: Optional[str], detailed_html: Optional[str]) -> str:
    if not short_html and not detailed_html:
        return ""

    parts = []

    if short_html:
        parts.append(f"""<div class="card analysis-card">
  <div class="card-label">🔍 어제 오답 요약</div>
  {short_html}
</div>""")

    if detailed_html:
        parts.append(f"""<div class="card detail-card">
  <div class="card-label">📚 어제 오답 상세 분석</div>
  <p class="detail-intro">틀린 문제를 기초부터 다시 정리했습니다. 오늘 테스트 전에 읽어보세요.</p>
  {detailed_html}
</div>""")

    return "\n".join(parts)


def _lesson_html(lesson: dict) -> str:
    ltype   = lesson.get("type", "EXPRESSION")
    bg, fg, acc = LESSON_COLORS.get(ltype, ("#f8f9fb", "#374151", "#6b7280"))
    icon    = lesson.get("icon", "📚")
    title   = lesson.get("title", "")
    subtitle= lesson.get("subtitle", "")
    key_pt  = lesson.get("key_point", "")
    examples= lesson.get("examples", [])
    tip     = lesson.get("tip", "")
    remember= lesson.get("remember", "")

    ex_html = ""
    for ex in examples:
        ex_html += f"""<div class="lesson-ex">
      <div class="lesson-ex-text">"{ex.get('text','')}"</div>
      <div class="lesson-ex-note">{ex.get('note','')}</div>
    </div>"""

    return f"""<div class="card lesson-card" style="background:{bg};border-color:{acc}">
  <div class="lesson-header">
    <span class="lesson-type-badge" style="background:{fg};color:#fff">{ltype}</span>
    <span class="lesson-icon">{icon}</span>
  </div>
  <h2 class="lesson-title" style="color:{fg}">{title}</h2>
  <p class="lesson-subtitle">{subtitle}</p>
  <div class="lesson-keypoint">{key_pt}</div>
  <div class="lesson-examples">{ex_html}</div>
  {f'<div class="lesson-tip">💡 {tip}</div>' if tip else ""}
  {f'<div class="lesson-remember" style="border-color:{acc};color:{fg}">🧠 {remember}</div>' if remember else ""}
</div>"""


def _listening_group_html(audio_item: dict, questions: list, start_num: int) -> str:
    """듣기 3-티어 중 하나의 섹션 HTML."""
    tier         = audio_item.get("tier", "medium")
    duration     = audio_item.get("duration_hint", "")
    t_icon, t_label, t_color, t_bg = TIER_META.get(tier, TIER_META["medium"])

    source = audio_item.get("source", "")
    title  = audio_item.get("title", "")
    url    = audio_item.get("url", "")
    audio_url = audio_item.get("audio_url", "")

    src_line = (f'<a class="src-link" href="{url}">{source}</a> · {title[:50]}' if url
                else f'<span>{source}</span>')

    # 오디오 플레이어 — 항상 무언가 표시
    if audio_url:
        audio_html = f"""<div class="audio-box">
      <p class="audio-hint">▼ 음성을 먼저 들은 후 문제를 풀어보세요 ({duration})</p>
      <audio controls controlsList="nodownload" style="width:100%;border-radius:8px">
        <source src="{audio_url}" type="audio/mpeg">
        <source src="{audio_url}" type="audio/mp4">
        <a href="{audio_url}" target="_blank">음성 파일 직접 열기</a>
      </audio>
    </div>"""
    elif url:
        audio_html = f"""<div class="audio-box">
      <p class="audio-hint">외부 사이트에서 음성을 들은 후 돌아와 문제를 풀어보세요 ({duration})</p>
      <a class="audio-link-btn" href="{url}" target="_blank">🎧 {source} 에서 듣기</a>
    </div>"""
    else:
        audio_html = f"""<div class="audio-box audio-box-warn">
      <p class="audio-hint">⚠️ 오디오 링크를 찾을 수 없습니다. 아래 문제는 텍스트 기반으로 풀어보세요.</p>
    </div>"""

    qs_html = "".join(_question_html(start_num + i, q) for i, q in enumerate(questions))

    return f"""<div class="card section-card">
  <div class="section-header">
    <div class="section-icon-wrap" style="background:{t_bg}">{t_icon}</div>
    <div>
      <div class="section-title" style="color:{t_color}">
        Listening · {t_label}
        <span class="duration-badge">{duration}</span>
      </div>
      <div class="section-source">{src_line}</div>
    </div>
  </div>
  {audio_html}
  {qs_html}
</div>"""


def _section_html(domain: str, questions: list, content_item: dict, start_num: int) -> str:
    icon, label, color, bg = DOMAIN_META[domain]
    source = content_item.get("source", "")
    title  = content_item.get("title", "")
    url    = content_item.get("url", "")

    src_line = (f'<a class="src-link" href="{url}">{source}</a> · {title[:45]}' if url
                else f'<span>{source}</span>')

    extra_html = ""

    if domain == "reading":
        passage = content_item.get("text", "")
        if passage:
            short = passage[:900] + ("…" if len(passage) > 900 else "")
            extra_html = f"""<div class="passage-box">
      <div class="passage-label">📄 지문</div>
      <p class="passage-text">{short}</p>
    </div>"""

    elif domain == "speaking" and questions:
        script = questions[0].get("shadowing_script", "")
        tip    = questions[0].get("pronunciation_tip", "")
        if script:
            safe_script = script.replace('"', '&quot;').replace("'", "&#39;")
            extra_html = f"""<div class="shadow-box">
      <div class="shadow-label">🎯 오늘의 쉐도잉 스크립트</div>
      <p class="shadow-text" id="shadowScript0">{script}</p>
      {f'<p class="shadow-tip">🔊 {tip}</p>' if tip else ""}

      <div class="record-box">
        <div class="record-title">🎙️ 발음 녹음 & 체크</div>
        <p class="record-hint">스크립트를 보며 따라 말하고, 녹음 버튼을 눌러보세요. Chrome/Edge에서 동작합니다.</p>
        <div class="record-controls">
          <button class="btn-record" id="recBtn0"
            onclick="startSpeechRecognition('shadowScript0','recBtn0','recStatus0','recTranscript0','recFeedback0')">
            🎤 녹음 시작
          </button>
          <span class="rec-status" id="recStatus0"></span>
        </div>
        <div class="rec-transcript-box">
          <span class="rec-label">인식된 음성:</span>
          <p id="recTranscript0" class="rec-text-output">—</p>
        </div>
        <div id="recFeedback0" class="rec-feedback"></div>
      </div>
    </div>"""

    qs_html = "".join(_question_html(start_num + i, q) for i, q in enumerate(questions))

    return f"""<div class="card section-card">
  <div class="section-header">
    <div class="section-icon-wrap" style="background:{bg}">{icon}</div>
    <div>
      <div class="section-title" style="color:{color}">Section · {label}</div>
      <div class="section-source">{src_line}</div>
    </div>
  </div>
  {extra_html}
  {qs_html}
</div>"""


def _question_html(q_num: int, q: dict) -> str:
    text    = q.get("question", "")
    options = q.get("options", {})
    level   = q.get("level", "B1")
    lv_col  = LEVEL_COLOR.get(level, "#e5e7eb")

    opts_html = ""
    for letter in ["A", "B", "C", "D"]:
        txt = options.get(letter, "")
        if not txt:
            continue
        opts_html += f"""<button class="opt" data-q="{q_num}" data-l="{letter}" type="button">
    <span class="opt-letter">{letter}</span>
    <span class="opt-text">{txt}</span>
  </button>"""

    expl = q.get("explanation", "")

    return f"""<div class="question" id="q{q_num}">
  <div class="q-text">
    <span class="q-num">{q_num + 1}</span>
    {text}
    <span class="q-level" style="background:{lv_col}">{level}</span>
  </div>
  <div class="opts">{opts_html}</div>
  <div class="expl" id="expl{q_num}" style="display:none">💬 {expl}</div>
</div>"""


# ── CSS ───────────────────────────────────────────────────────────────────────

def _css() -> str:
    return """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
  background: #f0f2f5; color: #1a1a2e; line-height: 1.6;
}

/* HEADER */
header { background: linear-gradient(135deg, #1a1a2e, #0f3460); padding: 24px 20px 20px; color: #fff; }
.hdr-top { display: flex; justify-content: space-between; align-items: center;
           font-size: 11px; color: #8899bb; letter-spacing: 1.5px;
           text-transform: uppercase; margin-bottom: 10px; }
.hdr-date { background: rgba(255,255,255,.12); padding: 3px 10px; border-radius: 20px; }
.hdr-title { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
.hdr-meta { font-size: 12px; color: #8899bb; margin-bottom: 14px; }
.lv-badges { display: flex; flex-wrap: wrap; gap: 6px; }
.lv-badge { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; color: #1a1a2e; }

/* CONTAINER */
.container { max-width: 680px; margin: 0 auto; padding: 16px 12px 40px; }

/* CARDS */
.card { background: #fff; border-radius: 14px; padding: 20px;
        margin-bottom: 16px; box-shadow: 0 2px 10px rgba(0,0,0,.06); }

/* PREV ANALYSIS */
.analysis-card { border-left: 4px solid #f97316; background: #fff7ed; }
.card-label { font-size: 11px; font-weight: 700; color: #c2410c;
              text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }

/* DETAILED ANALYSIS */
.detail-card { border-left: 4px solid #6366f1; background: #f5f3ff; }
.detail-card .card-label { color: #4338ca; }
.detail-intro { font-size: 13px; color: #4b5563; margin-bottom: 16px; }
.detail-item { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px;
               padding: 16px; margin-bottom: 14px; }
.detail-q-label { font-size: 14px; font-weight: 700; color: #1a1a2e; margin-bottom: 12px;
                  padding-bottom: 8px; border-bottom: 1px solid #e5e7eb; }
.detail-section { margin-bottom: 10px; }
.detail-section b { font-size: 12px; color: #6366f1; display: block; margin-bottom: 4px; }
.detail-section p { font-size: 13px; color: #374151; line-height: 1.7; }
.detail-ex { font-size: 13px; color: #374151; padding: 4px 0; }
.detail-tip { font-size: 13px; font-weight: 600; color: #4338ca;
              background: #eef2ff; padding: 8px 12px; border-radius: 8px; margin-top: 10px; }

/* LESSON */
.lesson-card { border: 1.5px solid; }
.lesson-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.lesson-type-badge { font-size: 10px; font-weight: 700; padding: 2px 8px;
                     border-radius: 4px; letter-spacing: 1px; }
.lesson-icon { font-size: 20px; }
.lesson-title { font-size: 18px; font-weight: 700; margin-bottom: 4px; }
.lesson-subtitle { font-size: 13px; color: #555; margin-bottom: 12px; }
.lesson-keypoint { font-size: 14px; background: rgba(0,0,0,.04); padding: 10px 12px;
                   border-radius: 8px; margin-bottom: 12px; }
.lesson-examples { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.lesson-ex { border-left: 3px solid currentColor; padding: 8px 12px;
             background: rgba(0,0,0,.03); border-radius: 0 6px 6px 0; }
.lesson-ex-text { font-size: 14px; font-weight: 600; font-style: italic; margin-bottom: 3px; }
.lesson-ex-note { font-size: 12px; color: #666; }
.lesson-tip { font-size: 13px; color: #555; background: rgba(0,0,0,.04);
              padding: 10px 12px; border-radius: 8px; margin-bottom: 10px; }
.lesson-remember { font-size: 13px; font-weight: 600; border: 1.5px solid;
                   padding: 8px 12px; border-radius: 8px; }

/* PROGRESS */
.progress-wrap { background: #fff; border-radius: 10px; padding: 12px 16px;
                 margin-bottom: 16px; box-shadow: 0 2px 10px rgba(0,0,0,.06); }
.progress-label { display: flex; justify-content: space-between;
                  font-size: 12px; color: #6b7280; margin-bottom: 6px; }
.progress-bar-bg { background: #e5e7eb; border-radius: 4px; height: 6px; }
.progress-bar-fill { background: linear-gradient(90deg, #22c55e, #0ea5e9);
                     height: 6px; border-radius: 4px; transition: width .3s; }

/* SECTION */
.section-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.section-icon-wrap { width: 40px; height: 40px; border-radius: 10px;
                     display: flex; align-items: center; justify-content: center;
                     font-size: 18px; flex-shrink: 0; }
.section-title { font-size: 15px; font-weight: 700; }
.duration-badge { font-size: 10px; background: #e0f2fe; color: #0369a1;
                  padding: 2px 8px; border-radius: 20px; margin-left: 6px; font-weight: 600; }
.section-source { font-size: 11px; color: #9ca3af; margin-top: 2px; }
.src-link { color: #9ca3af; text-decoration: none; }
.src-link:hover { color: #6b7280; }

/* AUDIO */
.audio-box { background: #e0f2fe; border: 1px solid #7dd3fc; border-radius: 10px;
             padding: 14px 16px; margin-bottom: 16px; }
.audio-box-warn { background: #fef9c3; border-color: #fde047; }
.audio-box-warn .audio-hint { color: #854d0e; }
.audio-hint { font-size: 12px; color: #0369a1; margin-bottom: 8px; }
.audio-link-btn { display: inline-block; background: #0ea5e9; color: #fff;
                  font-size: 14px; font-weight: 600; padding: 10px 20px;
                  border-radius: 8px; text-decoration: none; }

/* PASSAGE */
.passage-box { background: #f8faf8; border: 1px solid #bbddc0; border-left: 4px solid #22c55e;
               border-radius: 10px; padding: 14px 16px; margin-bottom: 16px; }
.passage-label { font-size: 11px; font-weight: 700; color: #166534;
                 text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
.passage-text { font-size: 14px; line-height: 1.8; color: #1a1a2e; }

/* SHADOWING */
.shadow-box { background: #fefce8; border: 1px solid #fde047; border-radius: 10px;
              padding: 14px 16px; margin-bottom: 16px; }
.shadow-label { font-size: 11px; font-weight: 700; color: #a16207;
                text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
.shadow-text { font-size: 15px; line-height: 1.8; color: #1a1a2e; font-weight: 500; margin-bottom: 12px; }
.shadow-tip { font-size: 12px; color: #92400e; margin-bottom: 12px; font-style: italic; }

/* RECORDING */
.record-box { background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 10px;
              padding: 14px 16px; margin-top: 8px; }
.record-title { font-size: 13px; font-weight: 700; color: #0369a1; margin-bottom: 6px; }
.record-hint { font-size: 12px; color: #0369a1; margin-bottom: 10px; }
.record-controls { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.btn-record { background: #0ea5e9; color: #fff; border: none; border-radius: 8px;
              padding: 9px 18px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-record:hover { background: #0284c7; }
.rec-status { font-size: 12px; color: #6b7280; }
.rec-transcript-box { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px;
                      padding: 10px 12px; margin-bottom: 10px; min-height: 40px; }
.rec-label { font-size: 11px; font-weight: 700; color: #9ca3af;
             text-transform: uppercase; letter-spacing: 1px; display: block; margin-bottom: 4px; }
.rec-text-output { font-size: 14px; color: #374151; font-style: italic; }
.rec-feedback { font-size: 13px; }
.rec-perfect { color: #16a34a; font-weight: 700; padding: 10px; background: #dcfce7;
               border-radius: 8px; text-align: center; }
.rec-warn { color: #9a3412; background: #fff7ed; padding: 8px 12px; border-radius: 8px; }
.rec-score { font-size: 15px; margin-bottom: 10px; padding: 8px 12px;
             background: #f9fafb; border-radius: 8px; }
.rec-missed { background: #fff; border: 1px solid #fca5a5; border-radius: 8px;
              padding: 12px; margin-bottom: 8px; }
.rec-missed ul { list-style: none; padding: 0; margin-top: 6px; }
.rec-missed li { padding: 4px 0; font-size: 13px; }
.rec-tip { font-size: 12px; color: #6b7280; font-style: italic; }
.rec-advice { font-size: 13px; color: #374151; background: #fffbeb;
              border: 1px solid #fde68a; padding: 8px 12px; border-radius: 8px; }

/* QUESTIONS */
.question { margin-bottom: 20px; padding: 14px; border-radius: 10px;
            border: 1.5px solid #e5e7eb; transition: border-color .2s; }
.question.q-correct { border-color: #86efac; background: #f0fdf4; }
.question.q-wrong   { border-color: #fca5a5; background: #fff1f2; }
.q-text { font-size: 14px; font-weight: 600; margin-bottom: 12px; line-height: 1.5; }
.q-num { display: inline-flex; align-items: center; justify-content: center;
         width: 22px; height: 22px; background: #1a1a2e; color: #fff;
         border-radius: 50%; font-size: 10px; font-weight: 700;
         margin-right: 6px; flex-shrink: 0; }
.q-level { font-size: 10px; font-weight: 700; padding: 2px 7px;
           border-radius: 10px; margin-left: 6px; }
.opts { display: flex; flex-direction: column; gap: 7px; }
.opt { display: flex; align-items: center; gap: 10px; padding: 10px 13px;
       border: 1.5px solid #e5e7eb; border-radius: 8px; background: #fff;
       cursor: pointer; text-align: left; width: 100%; font-size: 14px;
       color: #374151; transition: all .15s; }
.opt:hover:not([disabled]) { border-color: #93c5fd; background: #eff6ff; }
.opt.sel { border-color: #3b82f6; background: #eff6ff; }
.opt.opt-correct { border-color: #22c55e !important; background: #dcfce7 !important; color: #166534 !important; }
.opt.opt-wrong   { border-color: #ef4444 !important; background: #fee2e2 !important; color: #991b1b !important; }
.opt-letter { width: 22px; height: 22px; border: 1.5px solid #d1d5db; border-radius: 50%;
              display: inline-flex; align-items: center; justify-content: center;
              font-size: 11px; font-weight: 700; color: #6b7280; flex-shrink: 0; }
.opt-text { flex: 1; }
.expl { font-size: 13px; color: #374151; background: #f9fafb; padding: 10px 12px;
        border-radius: 8px; margin-top: 10px; line-height: 1.6; }

/* SUBMIT */
.submit-area { text-align: center; padding: 24px 0; }
.submit-hint { font-size: 13px; color: #6b7280; margin-bottom: 12px; }
.btn-submit { background: linear-gradient(135deg, #1a1a2e, #0f3460); color: #fff;
              font-size: 16px; font-weight: 700; padding: 14px 40px;
              border-radius: 12px; border: none; cursor: pointer; transition: opacity .2s; }
.btn-submit:hover { opacity: .85; }
.btn-submit:disabled { opacity: .5; cursor: not-allowed; }

/* RESULTS */
.results-panel { background: #fff; border-radius: 14px; padding: 24px 20px;
                 margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0,0,0,.1); }
.result-score { font-size: 52px; font-weight: 800; text-align: center; }
.result-sub { text-align: center; font-size: 18px; color: #6b7280; margin-bottom: 20px; }
.dom-scores { display: flex; gap: 8px; justify-content: center; margin-bottom: 24px; flex-wrap: wrap; }
.dom-score { text-align: center; background: #f8f9fb; border-radius: 10px; padding: 12px 16px; min-width: 70px; }
.dom-pct { font-size: 22px; font-weight: 800; }
.dom-name { font-size: 11px; color: #9ca3af; margin-top: 3px; }
.wrong-title { font-size: 13px; font-weight: 700; color: #c2410c;
               text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }
.wrong-item { background: #fff7ed; border: 1px solid #fed7aa; border-left: 4px solid #f97316;
              border-radius: 8px; padding: 12px 14px; margin-bottom: 8px; font-size: 13px; }
.wrong-tag { background: #f97316; color: #fff; font-size: 10px; font-weight: 700;
             padding: 2px 6px; border-radius: 4px; margin-right: 6px; }
.wrong-expl { color: #78350f; margin-top: 6px; line-height: 1.5; }
.all-correct { text-align: center; font-size: 16px; font-weight: 700; color: #22c55e;
               padding: 20px; background: #dcfce7; border-radius: 10px; }
.result-note { font-size: 12px; color: #9ca3af; text-align: center; margin-top: 16px; }

@media (max-width: 480px) {
  .container { padding: 12px 8px 32px; }
  .card { padding: 16px 14px; }
  .hdr-title { font-size: 20px; }
}
"""
