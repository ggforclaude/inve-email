import base64
import re
from datetime import datetime, timedelta
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm

def _set_korean_font():
    candidates = ["Malgun Gothic", "NanumGothic", "AppleGothic", "DejaVu Sans"]
    available = {f.name for f in fm.fontManager.ttflist}
    for font in candidates:
        if font in available:
            matplotlib.rc("font", family=font)
            return
    matplotlib.rc("font", family="DejaVu Sans")

_set_korean_font()
matplotlib.rc("axes", unicode_minus=False)
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pykrx import stock as krx

_ticker_cache: dict[str, str] = {}  # 회사명 -> 티커코드


def _build_cache():
    global _ticker_cache
    if _ticker_cache:
        return
    print("  [주식] 종목 목록 로딩 중...")
    today = datetime.now().strftime("%Y%m%d")
    for market in ["KOSPI", "KOSDAQ"]:
        for ticker in krx.get_market_ticker_list(today, market=market):
            name = krx.get_market_ticker_name(ticker)
            _ticker_cache[name] = ticker
    print(f"  [주식] {len(_ticker_cache)}개 종목 로드 완료")


def find_ticker(company_name: str) -> tuple[str, str] | tuple[None, None]:
    """회사명으로 (티커, 정확한종목명) 반환. 없으면 (None, None)."""
    _build_cache()
    clean = company_name.strip().replace(" ", "")

    # 정확한 이름 매칭
    for name, ticker in _ticker_cache.items():
        if name.replace(" ", "") == clean:
            return ticker, name

    # 부분 매칭 (짧은 이름 우선)
    candidates = [
        (name, ticker)
        for name, ticker in _ticker_cache.items()
        if clean in name.replace(" ", "") or name.replace(" ", "") in clean
    ]
    if candidates:
        best = min(candidates, key=lambda x: len(x[0]))
        return best[1], best[0]

    return None, None


def generate_chart_base64(ticker: str, company_name: str) -> str | None:
    """최근 1주일 주가 차트를 base64 PNG로 반환."""
    end = datetime.now()
    start = end - timedelta(days=14)  # 영업일 여유

    try:
        df = krx.get_market_ohlcv(
            start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), ticker
        )
        df = df.tail(7)
        if df.empty or len(df) < 2:
            return None

        fig, ax = plt.subplots(figsize=(7, 2.8))

        closes = df["종가"]
        colors = [
            "#e74c3c" if c >= o else "#3498db"
            for o, c in zip(df["시가"], closes)
        ]
        ax.bar(df.index, closes, color=colors, alpha=0.75, width=0.6)
        ax.plot(df.index, closes, "o-", color="#2c3e50", linewidth=1.5, markersize=4)

        last = closes.iloc[-1]
        first = closes.iloc[0]
        chg = (last - first) / first * 100
        chg_str = f"{chg:+.1f}%"
        color = "#e74c3c" if chg >= 0 else "#3498db"

        ax.set_title(
            f"{company_name}  |  {last:,}원  ({chg_str})",
            fontsize=10,
            color=color,
        )
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, _: f"{int(x):,}")
        )
        ax.grid(True, alpha=0.25)
        fig.tight_layout()

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()

    except Exception as e:
        print(f"  [차트 오류] {company_name} ({ticker}): {e}")
        return None


def extract_companies(summary: str) -> list[str]:
    """요약 텍스트의 ## 헤더에서 회사명 추출."""
    names = re.findall(r"^##\s+(.+)$", summary, re.MULTILINE)
    return [n.strip() for n in names if "시장" not in n and "📌" not in n]


def build_charts(summary: str) -> dict[str, str]:
    """회사명 → base64 차트 딕셔너리 반환."""
    companies = extract_companies(summary)
    charts = {}
    for name in companies:
        ticker, matched = find_ticker(name)
        if ticker:
            print(f"  [차트] {name} → {matched} ({ticker})")
            img = generate_chart_base64(ticker, matched)
            if img:
                charts[name] = img
        else:
            print(f"  [차트] {name} → 종목 미확인, 스킵")
    return charts
