"""
Improve_Eng/page_builder.py
일일 영어 테스트 HTML 페이지를 생성합니다.
docs/YYYY-MM-DD/index.html 로 저장 → GitHub Pages 자동 배포.

특징:
- 오디오 플레이어 인라인 재생 (HTML5 <audio>)
- 라디오 버튼 클릭으로 답 선택 (페이지 이탈 없음)
- 제출 시 즉시 채점 (클라이언트 JS)
- 채점 결과 인라인 표시 (정답/오답·설명)
- Apps Script GET으로 결과 저장 (no-cors, fire-and-forget)
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
) -> pathlib.Path:
    """HTML 파일 생성 후 경로 반환."""
    html = _render(today, day_number, questions, content,
                   daily_lesson, current_levels, prev_wrong_analysis)
    base = pathlib.Path(__file__).parent.parent / "docs" / str(today)
    base.mkdir(parents=True, exist_ok=True)
    out = base / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


# ── 데이터 추출 ───────────────────────────────────────────────────────────────

def _flatten_questions(questions: dict):
    """questions dict → (correct_list, explanation_list, domain_idx_list, all_qs)"""
    correct, explanations, domain_idxs, all_qs = [], [], [], []
    for i, domain in enumerate(DOMAINS):
        for q in questions.get(domain, []):
            correct.append(q.get("correct", "A").strip().upper())
            explanations.append(q.get("explanation", ""))
            domain_idxs.append(i)
            all_qs.append((domain, q))
    return correct, explanations, domain_idxs, all_qs


# ── HTML 렌더링 ───────────────────────────────────────────────────────────────

def _render(today, day_number, questions, content, daily_lesson, current_levels, prev_wrong_analysis):
    correct, explanations, domain_idxs, all_qs = _flatten_questions(questions)
    total = len(correct)

    # JS에 임베드할 데이터
    js_correct  = json.dumps(correct, ensure_ascii=False)
    js_expls    = json.dumps(explanations, ensure_ascii=False)
    js_dnames   = json.dumps([DOMAINS[i] for i in domain_idxs], ensure_ascii=False)
    js_date     = str(today)
    js_asurl    = APPS_SCRIPT_URL

    # 섹션 HTML
    sections_html = ""
    q_num = 0
    for domain in DOMAINS:
        qs = questions.get(domain, [])
        if not qs:
            continue
        domain_q_start = q_num
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

  {_prev_analysis_html(prev_wrong_analysis)}

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

  <div class="results-panel" id="resultsPanel" style="display:none">
  </div>

</div>

<script>
const CORRECT   = {js_correct};
const EXPLS     = {js_expls};
const DNAMES    = {js_dnames};
const TOTAL     = {total};
const TODAY     = "{js_date}";
const AS_URL    = "{js_asurl}";
const DOMAINS_KR = {{listening:"듣기",grammar:"문법",reading:"독해",speaking:"말하기"}};

let answers   = new Array(TOTAL).fill(null);
let submitted = false;

// 답 선택
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

  // 채점
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

    // 문항 시각화
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
    ${{wrongItems.length > 0 ? '<div class="wrong-title">오답 분석</div>' + wrongHtml : '<div class="all-correct">전체 정답! 완벽해요 🌟</div>'}}
    <div class="result-note">내일 아침 테스트 페이지에서 추가 피드백을 확인하세요.</div>
  `;
  panel.style.display = "block";
  panel.scrollIntoView({{behavior: "smooth", block: "start"}});

  document.getElementById("submitArea").style.display = "none";
}}

function saveResults(answers, correct, domSc) {{
  if (!AS_URL) return;
  const params = new URLSearchParams({{
    date: TODAY,
    answers: answers.join(","),
    correct,
    listening: domSc.listening.c + "/" + domSc.listening.t,
    grammar:   domSc.grammar.c   + "/" + domSc.grammar.t,
    reading:   domSc.reading.c   + "/" + domSc.reading.t,
    speaking:  domSc.speaking.c  + "/" + domSc.speaking.t,
  }});
  fetch(AS_URL + "?" + params.toString(), {{mode:"no-cors"}}).catch(() => {{}});
}}
</script>
</body>
</html>"""


# ── 섹션 HTML 빌더 ────────────────────────────────────────────────────────────

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
  <p class="hdr-meta">4개 영역 · {sum(1 for d in DOMAINS)} 섹션 · 약 20분</p>
  <div class="lv-badges">{badges}</div>
</header>"""


def _prev_analysis_html(analysis_html: Optional[str]) -> str:
    if not analysis_html:
        return ""
    return f"""<div class="card analysis-card">
  <div class="card-label">🔍 어제 오답 분석</div>
  {analysis_html}
</div>"""


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


def _section_html(domain: str, questions: list, content_item: dict, start_num: int) -> str:
    icon, label, color, bg = DOMAIN_META[domain]
    source = content_item.get("source", "")
    title  = content_item.get("title", "")
    url    = content_item.get("url", "")

    src_line = (f'<a class="src-link" href="{url}">{source}</a> · {title[:45]}' if url
                else f'<span>{source}</span>')

    # 듣기: 오디오 플레이어
    extra_html = ""
    if domain == "listening":
        audio_url    = content_item.get("audio_url", "")
        original_url = url
        play_url     = audio_url or original_url
        if play_url:
            if audio_url:
                extra_html = f"""<div class="audio-box">
      <p class="audio-hint">▼ 음성을 먼저 들은 후 문제를 풀어보세요</p>
      <audio controls controlsList="nodownload" style="width:100%;border-radius:8px">
        <source src="{audio_url}" type="audio/mpeg">
        <a href="{audio_url}" target="_blank">음성 링크 열기</a>
      </audio>
    </div>"""
            else:
                extra_html = f"""<div class="audio-box">
      <p class="audio-hint">외부 페이지에서 음성을 들은 후 돌아와 문제를 풀어보세요</p>
      <a class="audio-link-btn" href="{play_url}" target="_blank">🎧 음성 바로 듣기</a>
    </div>"""

    # 독해: 지문
    elif domain == "reading":
        passage = content_item.get("text", "")
        if passage:
            short = passage[:900]
            if len(passage) > 900:
                short += "…"
            extra_html = f"""<div class="passage-box">
      <div class="passage-label">📄 지문</div>
      <p class="passage-text">{short}</p>
    </div>"""

    # 말하기: 쉐도잉 스크립트
    elif domain == "speaking" and questions:
        script = questions[0].get("shadowing_script", "")
        tip    = questions[0].get("pronunciation_tip", "")
        if script:
            extra_html = f"""<div class="shadow-box">
      <div class="shadow-label">🎯 오늘의 쉐도잉 스크립트 (3회 반복)</div>
      <p class="shadow-text">{script}</p>
      {f'<p class="shadow-tip">🔊 {tip}</p>' if tip else ""}
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
    idx     = q_num  # 0-based index for JS

    opts_html = ""
    for letter in ["A", "B", "C", "D"]:
        txt = options.get(letter, "")
        if not txt:
            continue
        opts_html += f"""<button class="opt" data-q="{idx}" data-l="{letter}" type="button">
    <span class="opt-letter">{letter}</span>
    <span class="opt-text">{txt}</span>
  </button>"""

    expl = q.get("explanation", "")

    return f"""<div class="question" id="q{idx}">
  <div class="q-text">
    <span class="q-num">{q_num + 1}</span>
    {text}
    <span class="q-level" style="background:{lv_col}">{level}</span>
  </div>
  <div class="opts">{opts_html}</div>
  <div class="expl" id="expl{idx}" style="display:none">💬 {expl}</div>
</div>"""


# ── CSS ───────────────────────────────────────────────────────────────────────

def _css() -> str:
    return """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
  background: #f0f2f5;
  color: #1a1a2e;
  line-height: 1.6;
}

/* HEADER */
header {
  background: linear-gradient(135deg, #1a1a2e, #0f3460);
  padding: 24px 20px 20px;
  color: #fff;
}
.hdr-top { display: flex; justify-content: space-between; align-items: center;
           font-size: 11px; color: #8899bb; letter-spacing: 1.5px;
           text-transform: uppercase; margin-bottom: 10px; }
.hdr-date { background: rgba(255,255,255,.12); padding: 3px 10px; border-radius: 20px; }
.hdr-title { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
.hdr-meta { font-size: 12px; color: #8899bb; margin-bottom: 14px; }
.lv-badges { display: flex; flex-wrap: wrap; gap: 6px; }
.lv-badge { font-size: 11px; font-weight: 700; padding: 3px 10px;
            border-radius: 20px; color: #1a1a2e; }

/* CONTAINER */
.container { max-width: 680px; margin: 0 auto; padding: 16px 12px 40px; }

/* CARDS */
.card { background: #fff; border-radius: 14px; padding: 20px;
        margin-bottom: 16px; box-shadow: 0 2px 10px rgba(0,0,0,.06); }

/* PREV ANALYSIS */
.analysis-card { border-left: 4px solid #f97316; background: #fff7ed; }
.card-label { font-size: 11px; font-weight: 700; color: #c2410c;
              text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }

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
.section-source { font-size: 11px; color: #9ca3af; margin-top: 2px; }
.src-link { color: #9ca3af; text-decoration: none; }
.src-link:hover { color: #6b7280; }

/* AUDIO */
.audio-box { background: #e0f2fe; border: 1px solid #7dd3fc; border-radius: 10px;
             padding: 14px 16px; margin-bottom: 16px; }
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
.shadow-text { font-size: 15px; line-height: 1.8; color: #1a1a2e; font-weight: 500; }
.shadow-tip { font-size: 12px; color: #92400e; margin-top: 8px; font-style: italic; }

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
              border-radius: 12px; border: none; cursor: pointer;
              transition: opacity .2s; }
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
