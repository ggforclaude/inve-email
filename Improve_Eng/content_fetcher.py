"""
Improve_Eng/content_fetcher.py
BBC / VOA RSS에서 일일 학습 콘텐츠를 수집합니다.
날짜 기반 순환으로 매일 다른 소스를 사용합니다.
"""
import feedparser
import requests
import logging
from bs4 import BeautifulSoup
from datetime import date

log = logging.getLogger(__name__)

# ── 소스 정의 (도메인별, 순환 사용) ──────────────────────────────────────────

LISTENING_SOURCES = [
    {
        "name": "BBC 6 Minute English",
        "rss":  "https://feeds.bbci.co.uk/learningenglish/english/features/6-minute-english/rss.xml",
    },
    {
        "name": "BBC The English We Speak",
        "rss":  "https://feeds.bbci.co.uk/learningenglish/english/features/the-english-we-speak/rss.xml",
    },
    {
        "name": "VOA Learning English",
        "rss":  "https://learningenglish.voanews.com/api/zexg-voa-podcast-rss",
    },
]

READING_SOURCES = [
    {
        "name": "VOA Learning English News",
        "rss":  "https://learningenglish.voanews.com/api/zovijqmz_q",
    },
    {
        "name": "BBC Learning English Lingohack",
        "rss":  "https://feeds.bbci.co.uk/learningenglish/english/features/lingohack/rss.xml",
    },
]

SPEAKING_SOURCES = [
    {
        "name": "BBC Learning English Stories",
        "rss":  "https://podcasts.files.bbci.co.uk/p02pc9s1.rss",
    },
    {
        "name": "BBC Learning English Conversations",
        "rss":  "https://podcasts.files.bbci.co.uk/p02pc9zn.rss",
    },
]

# ── 문법 커리큘럼 (12주 순환) ─────────────────────────────────────────────────

GRAMMAR_CURRICULUM = [
    ("Present Perfect vs Simple Past",     "B1", "현재완료 vs 단순과거"),
    ("Second Conditional",                  "B2", "가정법 과거"),
    ("Modal Verbs (should / must / might)", "B1", "조동사"),
    ("Passive Voice",                       "B1", "수동태"),
    ("Reported Speech",                     "B2", "간접화법"),
    ("Third Conditional",                   "B2", "가정법 과거완료"),
    ("Relative Clauses",                    "B2", "관계절"),
    ("Articles (a / an / the)",             "B1", "관사"),
    ("Gerunds vs Infinitives",              "B2", "동명사 vs 부정사"),
    ("Phrasal Verbs – Business Context",    "B1", "구동사 (비즈니스)"),
    ("Mixed Conditionals",                  "B2", "혼합 가정법"),
    ("Past Perfect Tense",                  "B2", "과거완료"),
]


# ── 메인 진입점 ──────────────────────────────────────────────────────────────

async def fetch_daily_content(today: date) -> dict:
    """날짜 기반으로 4개 영역 콘텐츠를 각각 다른 소스에서 수집."""
    idx       = today.toordinal()
    week_idx  = (idx // 7) % len(GRAMMAR_CURRICULUM)

    listening = _fetch_from_source(LISTENING_SOURCES[idx % len(LISTENING_SOURCES)])
    reading   = _fetch_from_source(READING_SOURCES[idx % len(READING_SOURCES)])
    speaking  = _fetch_from_source(SPEAKING_SOURCES[idx % len(SPEAKING_SOURCES)])

    topic, level, topic_kr = GRAMMAR_CURRICULUM[week_idx]

    return {
        "listening": listening,
        "reading":   reading,
        "speaking":  speaking,
        "grammar": {
            "topic":  topic,
            "level":  level,
            "korean": topic_kr,
            "source": "British Council / Perfect English Grammar",
            "text":   "",
        },
    }


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

def _fetch_from_source(source: dict) -> dict:
    """RSS 피드에서 최신 항목 1개의 텍스트를 추출."""
    try:
        feed = feedparser.parse(source["rss"])
        if not feed.entries:
            raise ValueError("RSS 항목 없음")

        entry   = feed.entries[0]
        title   = entry.get("title", "")
        link    = entry.get("link", "")
        summary = entry.get("summary", entry.get("description", ""))
        text    = _clean_html(summary)

        # 요약이 너무 짧으면 본문 페이지 추가 수집
        if len(text) < 200 and link:
            scraped = _scrape_article(link)
            if scraped:
                text = scraped

        audio_url = _extract_audio_url(entry)
        log.info(f"[{source['name']}] 수집 완료: {title[:60]} | audio={'있음' if audio_url else '없음'}")
        return {
            "source":    source["name"],
            "title":     title,
            "url":       link,
            "audio_url": audio_url,
            "text":      text[:2000],
        }

    except Exception as e:
        log.warning(f"[{source['name']}] 수집 실패: {e} → Claude가 자체 생성")
        return {"source": source["name"], "title": "Daily Practice", "url": "", "text": ""}


def _extract_audio_url(entry) -> str:
    """RSS 항목에서 MP3/오디오 URL을 추출."""
    # enclosures 필드 (BBC, VOA 표준)
    for enc in getattr(entry, "enclosures", []):
        if "audio" in enc.get("type", "") or enc.get("href", "").endswith(".mp3"):
            return enc.get("href", "")
    # links 필드 (일부 피드)
    for lnk in getattr(entry, "links", []):
        if "audio" in lnk.get("type", "") or lnk.get("href", "").endswith(".mp3"):
            return lnk.get("href", "")
    return ""


def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    return " ".join(soup.get_text().split())


def _scrape_article(url: str) -> str:
    try:
        r = requests.get(
            url, timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; EnglishBot/1.0)"},
        )
        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        paragraphs = soup.find_all("p")
        return " ".join(p.get_text() for p in paragraphs)[:2000]
    except Exception:
        return ""
