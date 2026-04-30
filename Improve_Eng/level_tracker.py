"""
Improve_Eng/level_tracker.py
Google Sheets를 통해 문제 저장, 응답 채점, CEFR 레벨 계산을 담당합니다.

Sheets 구조:
  Questions      : 매일 생성된 문제와 정답 저장 (스크립트가 씀)
  Responses      : Google Form 응답 자동 연결 시트 (사용자가 제출)
  Level_History  : 일별 채점 결과와 추정 레벨 기록 (스크립트가 씀)
"""
import os
import json
import logging
from datetime import date, timedelta
from typing import Optional

log = logging.getLogger(__name__)

DOMAINS      = ["listening", "grammar", "reading", "speaking"]
LEVEL_ORDER  = ["A2", "B1", "B2", "C1"]
PASS_RATE    = 0.70   # 레벨 통과 기준 정확도
ROLLING_DAYS = 7      # 레벨 계산 롤링 윈도우

# Google Sheets 시트 이름
SH_QUESTIONS = "Questions"
SH_RESPONSES = "Responses"   # Google Form 자동 연결 시트명과 일치해야 함
SH_HISTORY   = "Level_History"

# Questions 시트 컬럼 인덱스
Q_DATE, Q_DOMAIN, Q_NUM, Q_LEVEL, Q_TEXT = 0, 1, 2, 3, 4
Q_OPT_A, Q_OPT_B, Q_OPT_C, Q_OPT_D     = 5, 6, 7, 8
Q_CORRECT, Q_EXPL, Q_SCRIPT              = 9, 10, 11

# Responses 시트: [timestamp, date_field, ans_q1 .. ans_q12]
R_DATE = 1
R_ANS_START = 2


class LevelTracker:
    def __init__(self):
        self._svc      = None
        self._sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")

    # ── Public API ────────────────────────────────────────────────────────────

    def save_today_questions(self, today: date, questions: dict) -> None:
        """오늘 생성된 문제를 Questions 시트에 저장 (내일 채점에 사용)."""
        rows  = []
        q_num = 1
        for domain in DOMAINS:
            for q in questions.get(domain, []):
                opts = q.get("options", {})
                rows.append([
                    str(today),
                    domain,
                    str(q_num),
                    q.get("level", "B1"),
                    q.get("question", ""),
                    opts.get("A", ""), opts.get("B", ""),
                    opts.get("C", ""), opts.get("D", ""),
                    q.get("correct", "A"),
                    q.get("explanation", ""),
                    q.get("shadowing_script", ""),
                ])
                q_num += 1
        self._append(SH_QUESTIONS, rows)
        log.info(f"문제 {len(rows)}개 저장 완료 ({today})")

    def get_yesterday_results(self, today: date) -> Optional[dict]:
        """전날 응답을 채점하고 결과 딕셔너리를 반환. 데이터 없으면 None."""
        yesterday  = str(today - timedelta(days=1))
        questions  = self._questions_for(yesterday)
        if not questions:
            log.info("어제 문제 데이터 없음 (첫 실행)")
            return None
        responses = self._responses_for(yesterday)
        if not responses:
            log.info("어제 응답 없음 (미제출)")
            return None
        return self._grade(questions, responses, yesterday)

    def calculate_current_levels(self) -> dict:
        """최근 ROLLING_DAYS일 Level_History를 읽어 영역별 추정 레벨 반환."""
        history = self._read(SH_HISTORY)[-ROLLING_DAYS:]
        return {d: self._estimate(history, i + 1) for i, d in enumerate(DOMAINS)}

    def get_day_number(self, today: date) -> int:
        """오늘까지의 학습 누적 일수 (Level_History 행 수 + 1)."""
        history = self._read(SH_HISTORY)
        return len(history) + 1

    # ── 채점 ─────────────────────────────────────────────────────────────────

    def _grade(self, questions: list, user_answers: list, date_str: str) -> dict:
        answers    = user_answers[0] if user_answers else []
        correct_ct = 0
        wrong      = []
        domain_sc  = {d: {"correct": 0, "total": 0} for d in DOMAINS}

        for q in questions:
            q_idx  = int(q[Q_NUM]) - 1        # 0-based
            domain = q[Q_DOMAIN]
            level  = q[Q_LEVEL]
            q_text = q[Q_TEXT]
            ans_ok = q[Q_CORRECT]
            expl   = q[Q_EXPL] if len(q) > Q_EXPL else ""
            chosen = answers[q_idx].strip().upper() if q_idx < len(answers) else ""

            domain_sc[domain]["total"] += 1
            if chosen == ans_ok.strip().upper():
                correct_ct += 1
                domain_sc[domain]["correct"] += 1
            else:
                wrong.append({
                    "domain": domain, "level": level,
                    "question": q_text, "correct": ans_ok,
                    "chosen": chosen,  "explanation": expl,
                })

        self._record_history(date_str, domain_sc)

        return {
            "date":         date_str,
            "total":        len(questions),
            "correct":      correct_ct,
            "domain_scores": domain_sc,
            "wrong_items":  wrong,
        }

    # ── 레벨 추정 ─────────────────────────────────────────────────────────────

    def _estimate(self, history: list, col: int) -> str:
        """
        Level_History 컬럼(col)의 최근 정확도 평균으로 레벨 추정.
        컬럼 순서: date(0) | listening(1) | grammar(2) | reading(3) | speaking(4)
        """
        if not history:
            return "B1"
        vals = []
        for row in history:
            try:
                vals.append(float(row[col]))
            except (IndexError, ValueError):
                pass
        if not vals:
            return "B1"
        avg = sum(vals) / len(vals)
        if avg >= 0.85:
            return "B2"
        elif avg >= PASS_RATE:
            return "B1"
        else:
            return "A2"

    def _record_history(self, date_str: str, domain_sc: dict) -> None:
        row = [date_str]
        for d in DOMAINS:
            s = domain_sc.get(d, {"correct": 0, "total": 0})
            acc = round(s["correct"] / s["total"], 3) if s["total"] else 0.0
            row.append(acc)
        self._append(SH_HISTORY, [row])

    # ── Sheets 읽기/쓰기 ─────────────────────────────────────────────────────

    def _get_service(self):
        if self._svc:
            return self._svc
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
        creds = service_account.Credentials.from_service_account_info(
            json.loads(sa_json),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        self._svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
        return self._svc

    def _read(self, sheet: str) -> list:
        if not self._sheet_id:
            return []
        try:
            result = (
                self._get_service()
                .spreadsheets().values()
                .get(spreadsheetId=self._sheet_id, range=f"{sheet}!A2:Z")
                .execute()
            )
            return result.get("values", [])
        except Exception as e:
            log.error(f"Sheets 읽기 실패 ({sheet}): {e}")
            return []

    def _append(self, sheet: str, rows: list) -> None:
        if not self._sheet_id or not rows:
            return
        try:
            (
                self._get_service()
                .spreadsheets().values()
                .append(
                    spreadsheetId=self._sheet_id,
                    range=f"{sheet}!A1",
                    valueInputOption="RAW",
                    body={"values": rows},
                )
                .execute()
            )
        except Exception as e:
            log.error(f"Sheets 쓰기 실패 ({sheet}): {e}")

    def _questions_for(self, date_str: str) -> list:
        return [r for r in self._read(SH_QUESTIONS) if r and r[0] == date_str]

    def _responses_for(self, date_str: str) -> list:
        """Google Form 응답 시트에서 해당 날짜 행만 반환 (답 부분만)."""
        rows = self._read(SH_RESPONSES)
        return [r[R_ANS_START:] for r in rows if len(r) > R_ANS_START and r[R_DATE] == date_str]
