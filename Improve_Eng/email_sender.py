"""
Improve_Eng/email_sender.py
일일 영어 학습 HTML 이메일 작성 및 Gmail SMTP 발송.
Gmail 호환을 위해 인라인 스타일 사용.
"""
import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date
from typing import Optional

log = logging.getLogger(__name__)

FORM_URL    = os.environ.get("GOOGLE_FORM_URL", "#")
RECIPIENT   = os.environ.get("RECIPIENT_EMAIL", "minjoon5122@gmail.com")
GMAIL_USER  = os.environ.get("GMAIL_USER", "")
GMAIL_PW    = os.environ.get("GMAIL_APP_PASSWORD", "")

DOMAINS = ["listening", "grammar", "reading", "speaking"]
DOMAIN_META = {
    "listening": ("🎧", "듣기",   "#0ea5e9"),
    "grammar":   ("✏️", "문법",   "#8b5cf6"),
    "reading":   ("📖", "독해",   "#22c55e"),
    "speaking":  ("🗣️", "말하기", "#f59e0b"),
}
LEVEL_COLOR = {"A2": "#6ee7b7", "B1": "#93c5fd", "B2": "#c4b5fd", "C1": "#fca5a5"}

# ── 발송 진입점 ──────────────────────────────────────────────────────────────

async def send_daily_email(
    today: date,
    day_number: int,
    questions: dict,
    content: dict,
    prev_results: Optional[dict],
    current_levels: dict,
    wrong_analysis: Optional[str],
) -> None:
    html    = _build_html(today, day_number, questions, content,
                          prev_results, current_levels, wrong_analysis)
    subject = f"[Day {day_number}] 오늘의 영어 테스트 · {today.strftime('%b %d, %Y')}"
    _smtp_send(subject, html)


def _smtp_send(subject: str, html: str) -> None:
    if not GMAIL_USER or not GMAIL_PW:
        log.warning("Gmail 자격증명 없음 — 발송 건너뜀")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_PW)
        s.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())
    log.info(f"발송 완료 → {RECIPIENT}")


# ── HTML 조립 ────────────────────────────────────────────────────────────────

def _build_html(today, day_number, questions, content,
                prev_results, current_levels, wrong_analysis) -> str:
    sections = ""
    q_num = 1
    for domain in DOMAINS:
        qs = questions.get(domain, [])
        sections += _section(domain, qs, content.get(domain, {}), q_num)
        q_num += len(qs)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:16px;background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<div style="max-width:660px;margin:0 auto;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1);">

  {_header(today, day_number)}
  {_level_bar(current_levels, day_number)}
  {_score_cards(prev_results)}
  {_analysis_banner(wrong_analysis) if wrong_analysis else ""}
  {sections}
  {_submit_btn()}
  {_footer(day_number, prev_results)}

</div>
</body>
</html>"""


# ── 섹션별 빌더 ──────────────────────────────────────────────────────────────

def _header(today: date, day_number: int) -> str:
    return f"""
<div style="background:linear-gradient(135deg,#1a1a2e,#0f3460);padding:28px 30px 22px;">
  <div style="font-size:11px;color:rgba(255,255,255,0.45);letter-spacing:2px;text-transform:uppercase;margin-bottom:12px;">
    Improve English &nbsp;·&nbsp; Day {day_number}
    <span style="float:right;background:rgba(255,255,255,0.1);padding:3px 12px;border-radius:20px;font-size:11px;">
      {today.strftime('%a, %b %d %Y')}
    </span>
  </div>
  <div style="font-size:24px;font-weight:700;color:#ffffff;line-height:1.2;">오늘의 영어 테스트 📚</div>
  <div style="font-size:13px;color:rgba(255,255,255,0.5);margin-top:6px;">4개 영역 · 12문항 · 약 20분</div>
</div>"""


def _level_bar(levels: dict, day_number: int) -> str:
    if day_number <= 7:
        content = f"""<span style="color:#9ca3af;font-size:13px;">
          📊 베이스라인 측정 중 (Day {day_number}/7) — 모든 난이도를 고르게 출제합니다
        </span>"""
    else:
        badges = ""
        for d in DOMAINS:
            icon, name_kr, _ = DOMAIN_META[d]
            lvl = levels.get(d, "B1")
            col = LEVEL_COLOR.get(lvl, "#e5e7eb")
            badges += (
                f'<span style="background:{col};color:#1a1a2e;font-size:11px;'
                f'font-weight:700;padding:3px 10px;border-radius:20px;margin-right:6px;">'
                f'{icon} {name_kr}: {lvl}</span>'
            )
        content = f'<div style="font-size:11px;color:#9ca3af;margin-bottom:8px;">추정 현재 레벨</div>{badges}'

    return f"""
<div style="padding:14px 30px;background:#f8f9fb;border-bottom:1px solid #eef0f3;">
  {content}
</div>"""


def _score_cards(prev: Optional[dict]) -> str:
    if not prev:
        return ""
    cells = ""
    for d in DOMAINS:
        icon, name_kr, _ = DOMAIN_META[d]
        s     = prev.get("domain_scores", {}).get(d, {"correct": 0, "total": 0})
        pct   = int(s["correct"] / s["total"] * 100) if s["total"] else 0
        color = "#22c55e" if pct >= 80 else "#f59e0b" if pct >= 60 else "#ef4444"
        cells += (
            f'<td style="text-align:center;padding:12px 6px;background:#f8f9fb;'
            f'border-radius:10px;">'
            f'<div style="font-size:22px;font-weight:800;color:{color};">{pct}%</div>'
            f'<div style="font-size:11px;color:#9ca3af;margin-top:3px;">{icon} {name_kr}</div>'
            f'</td>'
        )
    return f"""
<div style="padding:16px 30px 0;">
  <div style="font-size:12px;color:#9ca3af;margin-bottom:8px;">어제({prev.get('date','')}) 결과</div>
  <table width="100%" cellpadding="4" cellspacing="4" style="border-collapse:separate;">
    <tr>{cells}</tr>
  </table>
</div>"""


def _analysis_banner(html_content: str) -> str:
    return f"""
<div style="margin:16px 30px 0;background:#fff7ed;border:1px solid #fed7aa;
     border-left:4px solid #f97316;border-radius:10px;padding:14px 18px;">
  <div style="font-size:11px;font-weight:700;color:#c2410c;text-transform:uppercase;
       letter-spacing:1px;margin-bottom:10px;">🔍 어제 오답 분석</div>
  <style>
    .wi{{margin-bottom:8px;font-size:14px;color:#78350f;line-height:1.5;}}
    .wi .tag{{background:#f97316;color:#fff;font-size:10px;font-weight:700;
              padding:2px 7px;border-radius:4px;margin-right:6px;}}
  </style>
  {html_content}
</div>"""


def _section(domain: str, questions: list, content_item: dict, start_num: int) -> str:
    icon, name_kr, color = DOMAIN_META[domain]
    source = content_item.get("source", "")
    title  = content_item.get("title", "")
    url    = content_item.get("url", "")
    src_line = (
        f'<a href="{url}" style="color:#9ca3af;text-decoration:none;">{source}</a>'
        f' · {title[:50]}' if url else source
    )

    # 말하기: 첫 문제에서 쉐도잉 스크립트 추출
    script_html = ""
    if domain == "speaking" and questions:
        script = questions[0].get("shadowing_script", "")
        tip    = questions[0].get("pronunciation_tip", "")
        if script:
            tip_html = (
                f'<div style="font-size:12px;color:#92400e;margin-top:8px;font-style:italic;">'
                f'{tip}</div>'
            ) if tip else ""
            script_html = f"""
<div style="background:#fefce8;border:1px solid #fde047;border-radius:10px;
     padding:14px 16px;margin-bottom:14px;">
  <div style="font-size:11px;font-weight:700;color:#a16207;text-transform:uppercase;
       letter-spacing:1px;margin-bottom:8px;">🎯 오늘의 쉐도잉 스크립트 (3회 반복)</div>
  <div style="font-size:15px;color:#1a1a2e;line-height:1.8;">{script}</div>
  {tip_html}
</div>"""

    qs_html = "".join(_question(start_num + i, q) for i, q in enumerate(questions))

    return f"""
<div style="padding:22px 30px;border-bottom:1px solid #eef0f3;">
  <div style="display:flex;align-items:center;margin-bottom:16px;">
    <div style="width:36px;height:36px;background:{color}22;border-radius:9px;
         display:flex;align-items:center;justify-content:center;
         font-size:16px;margin-right:10px;flex-shrink:0;">{icon}</div>
    <div>
      <div style="font-size:15px;font-weight:700;color:#1a1a2e;">Section · {name_kr}</div>
      <div style="font-size:11px;color:#9ca3af;margin-top:2px;">{src_line}</div>
    </div>
  </div>
  {script_html}
  {qs_html}
</div>"""


def _question(q_num: int, q: dict) -> str:
    text    = q.get("question", "")
    options = q.get("options", {})
    level   = q.get("level", "B1")
    lv_col  = LEVEL_COLOR.get(level, "#e5e7eb")

    opts_html = ""
    for letter in ["A", "B", "C", "D"]:
        txt = options.get(letter, "")
        if not txt:
            continue
        opts_html += (
            f'<div style="display:flex;align-items:center;gap:10px;padding:10px 13px;'
            f'border:1.5px solid #e5e7eb;border-radius:8px;margin-bottom:7px;'
            f'font-size:14px;color:#374151;">'
            f'<span style="width:22px;height:22px;border:1.5px solid #d1d5db;'
            f'border-radius:50%;display:inline-flex;align-items:center;justify-content:center;'
            f'font-size:11px;font-weight:700;color:#6b7280;flex-shrink:0;">{letter}</span>'
            f'{txt}</div>'
        )

    return f"""
<div style="margin-bottom:18px;">
  <div style="font-size:14px;font-weight:600;color:#1a1a2e;margin-bottom:10px;line-height:1.5;">
    <span style="display:inline-flex;align-items:center;justify-content:center;
         width:20px;height:20px;background:#1a1a2e;color:#fff;border-radius:50%;
         font-size:10px;font-weight:700;margin-right:6px;flex-shrink:0;">{q_num}</span>
    {text}
    <span style="background:{lv_col};color:#1a1a2e;font-size:10px;font-weight:700;
         padding:2px 7px;border-radius:10px;margin-left:6px;">{level}</span>
  </div>
  {opts_html}
</div>"""


def _submit_btn() -> str:
    return f"""
<div style="padding:20px 30px 24px;background:#f8f9fb;text-align:center;">
  <div style="font-size:13px;color:#6b7280;margin-bottom:12px;">
    아래 버튼을 눌러 Q1~Q12 답안을 순서대로 제출하세요
  </div>
  <a href="{FORM_URL}"
     style="display:inline-block;background:linear-gradient(135deg,#1a1a2e,#0f3460);
            color:#fff;font-size:15px;font-weight:700;padding:12px 34px;
            border-radius:10px;text-decoration:none;">
    📝 답안 제출하기 (Google Form)
  </a>
  <div style="font-size:12px;color:#9ca3af;margin-top:10px;">
    내일 아침 메일에서 채점 결과와 오답 분석을 확인하실 수 있습니다
  </div>
</div>"""


def _footer(day_number: int, prev: Optional[dict]) -> str:
    if prev and prev.get("total"):
        pct  = int(prev["correct"] / prev["total"] * 100)
        right = f'어제 점수 <strong style="color:#22c55e;font-size:16px;">{pct}%</strong>'
    else:
        right = '<strong style="color:#22c55e;">학습 시작! 화이팅 🎯</strong>'
    return f"""
<div style="background:#1a1a2e;padding:16px 30px;">
  <table width="100%"><tr>
    <td style="font-size:12px;color:rgba(255,255,255,0.4);">
      Improve_Eng · Day {day_number}<br>{RECIPIENT}
    </td>
    <td style="text-align:right;font-size:12px;color:rgba(255,255,255,0.6);">
      {right}
    </td>
  </tr></table>
</div>"""
