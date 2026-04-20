import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RECIPIENT = os.getenv("RECIPIENT_EMAIL", "ggulbok2@gmail.com")


def send_summary_email(subject: str, body: str, charts: dict[str, str] | None = None):
    """요약 내용을 이메일로 발송합니다. charts = {회사명: base64_png}"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT

    html_body = _build_html(body, charts or {})

    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())

    print(f"[이메일 발송 완료] {subject} → {RECIPIENT}")


def _build_html(text: str, charts: dict[str, str]) -> str:
    lines = text.split("\n")
    html_lines = []

    for line in lines:
        if line.startswith("## "):
            company = line[3:].strip()
            html_lines.append(f'<h2 style="margin-bottom:4px;color:#1a1a2e">{company}</h2>')
            # 회사명이 charts에 있으면 차트 삽입
            chart_b64 = _find_chart(company, charts)
            if chart_b64:
                html_lines.append(
                    f'<img src="data:image/png;base64,{chart_b64}" '
                    f'style="width:100%;max-width:650px;margin:6px 0 10px 0;border-radius:6px;" />'
                )
        elif line.startswith("# "):
            html_lines.append(f'<h1 style="color:#1a1a2e">{line[2:]}</h1>')
        elif line.startswith("- "):
            html_lines.append(f'<li style="margin:3px 0">{line[2:]}</li>')
        elif line.startswith("---"):
            html_lines.append('<hr style="border:none;border-top:1px solid #ddd;margin:16px 0">')
        elif line.strip() == "":
            html_lines.append("<br>")
        else:
            html_lines.append(f"<p>{line}</p>")

    return f"""<html>
<body style="font-family:'Malgun Gothic',Arial,sans-serif;max-width:750px;margin:auto;padding:24px;color:#222;">
{''.join(html_lines)}
<p style="margin-top:32px;font-size:11px;color:#999;">자동 생성 | 여의도스토리2 · 세종데이터2013</p>
</body></html>"""


def _find_chart(company: str, charts: dict[str, str]) -> str | None:
    """회사명으로 차트 검색 (부분 매칭 허용)."""
    if company in charts:
        return charts[company]
    for key, val in charts.items():
        if key in company or company in key:
            return val
    return None
