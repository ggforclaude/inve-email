import os
import time
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """당신은 투자 뉴스 분석 전문가입니다.
텔레그램 채널에서 수집된 투자 관련 메시지들을 회사/종목별로 분류하고 요약합니다.

규칙:
1. 같은 회사/종목에 대한 여러 메시지를 하나로 통합하여 요약
2. 회사명을 정확히 파악 (종목코드, 영문명, 한글명 모두 인식)
3. 각 회사별로 핵심 내용만 간결하게 요약 (불릿 포인트 사용)
4. 투자에 중요한 정보(실적, 공시, 계약, 이슈 등) 위주로 정리
5. 특정 회사와 무관한 시장 전반 뉴스는 "📌 시장 전반" 섹션에 정리
6. 출력은 반드시 한국어로 작성
7. 형식 예시:
   ## 삼성전자
   - 2분기 영업이익 10조 예상 (시장 컨센서스 상회)
   - 반도체 감산 종료 검토 중

   ## SK하이닉스
   - HBM3E 양산 시작, 엔비디아 공급 확정
"""


def summarize_messages(messages: list[dict], period_label: str) -> str:
    """메시지 목록을 회사별로 요약합니다."""
    if not messages:
        return f"[{period_label}] 해당 기간에 수집된 메시지가 없습니다."

    # 메시지를 텍스트로 변환 (토큰 절약을 위해 날짜+내용만)
    raw_text = "\n\n".join(
        f"[{m['date']}][{m.get('channel', '')}] {m['text']}" for m in messages
    )

    # 메시지가 매우 많으면 청크로 나누어 처리
    chunks = _split_into_chunks(raw_text, max_chars=150000)

    if len(chunks) == 1:
        return _call_claude(chunks[0], period_label)

    # 여러 청크면 각각 요약 후 다시 합쳐서 최종 요약
    partial_summaries = []
    for i, chunk in enumerate(chunks):
        label = f"{period_label} (파트 {i+1}/{len(chunks)})"
        partial = _call_claude(chunk, label)
        partial_summaries.append(partial)

    combined = "\n\n---\n\n".join(partial_summaries)
    final = _merge_summaries(combined, period_label)
    return final


def _split_into_chunks(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    lines = text.split("\n\n")
    chunks, current = [], []
    current_len = 0
    for line in lines:
        if current_len + len(line) > max_chars and current:
            chunks.append("\n\n".join(current))
            current, current_len = [], 0
        current.append(line)
        current_len += len(line)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _call_claude(text: str, period_label: str) -> str:
    user_msg = f"""아래는 {period_label} 기간 동안 텔레그램 채널에 올라온 투자 뉴스입니다.
회사/종목별로 분류하고 핵심 내용을 요약해주세요.

{text}"""
    return _claude_with_retry(user_msg)


def _merge_summaries(combined: str, period_label: str) -> str:
    user_msg = f"""아래는 {period_label} 기간의 투자 뉴스를 부분별로 요약한 내용입니다.
같은 회사에 대한 내용을 하나로 합쳐서 최종 요약본을 만들어주세요.

{combined}"""
    return _claude_with_retry(user_msg)


def _claude_with_retry(user_msg: str, max_retries: int = 5) -> str:
    """429/529 에러 시 지수 백오프로 재시도합니다."""
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            wait = 60 * (attempt + 1)
            print(f"  [Rate Limit] {wait}초 대기 후 재시도 ({attempt+1}/{max_retries})...")
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            if e.status_code == 529:
                wait = 30 * (attempt + 1)
                print(f"  [Overloaded] {wait}초 대기 후 재시도 ({attempt+1}/{max_retries})...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("최대 재시도 횟수를 초과했습니다.")
