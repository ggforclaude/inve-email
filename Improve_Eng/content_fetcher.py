"""
Improve_Eng/content_fetcher.py
BBC / VOA / ESL RSS에서 일일 학습 콘텐츠를 수집합니다.

듣기 3-티어 구조:
  SHORT  (~1-3분): BBC News Minute, BBC The English We Speak, VOA Learning English
  MEDIUM (~4-7분): BBC 6 Minute English, BBC 6 Minute Grammar, BBC Lingohack
  LONG   (~8-15분): BBC English At Work, ESL Podcast, All Ears English
"""
import feedparser
import requests
import logging
from bs4 import BeautifulSoup
from datetime import date

log = logging.getLogger(__name__)

AUDIO_EXTS = (".mp3", ".m4a", ".aac", ".ogg", ".wav", ".opus")

# ── 듣기 소스 (3-티어) ───────────────────────────────────────────────────────

LISTENING_SHORT = [  # ~1-3분
    {
        "name": "BBC The English We Speak",
        "rss":  "https://podcasts.files.bbci.co.uk/p02pc9s3.rss",
        "duration_hint": "약 3분",
    },
    {
        "name": "BBC Global News Minute",
        "rss":  "https://podcasts.files.bbci.co.uk/p0bf37qw.rss",
        "duration_hint": "약 1분",
    },
    {
        "name": "VOA Learning English News",
        "rss":  "https://learningenglish.voanews.com/api/zovijqmz_q",
        "duration_hint": "약 2분",
    },
]

LISTENING_MEDIUM = [  # ~4-7분
    {
        "name": "BBC 6 Minute English",
        "rss":  "https://podcasts.files.bbci.co.uk/p02pc9pj.rss",
        "duration_hint": "약 6분",
    },
    {
        "name": "BBC 6 Minute Grammar",
        "rss":  "https://podcasts.files.bbci.co.uk/p02pc9v1.rss",
        "duration_hint": "약 6분",
    },
    {
        "name": "BBC Lingohack",
        "rss":  "https://feeds.bbci.co.uk/learningenglish/english/features/lingohack/rss.xml",
        "duration_hint": "약 3분",
    },
    {
        "name": "BBC Learning English Conversations",
        "rss":  "https://podcasts.files.bbci.co.uk/p02pc9zn.rss",
        "duration_hint": "약 5분",
    },
]

LISTENING_LONG = [  # ~8-15분
    {
        "name": "BBC English At Work",
        "rss":  "https://podcasts.files.bbci.co.uk/p02pc9qx.rss",
        "duration_hint": "약 12분",
    },
    {
        "name": "ESL Podcast",
        "rss":  "https://www.eslpod.com/eslpod_feed.xml",
        "duration_hint": "약 15분",
    },
    {
        "name": "All Ears English",
        "rss":  "https://www.allearsenglish.com/feed/podcast",
        "duration_hint": "약 10분",
    },
]

# ── 독해 소스 ────────────────────────────────────────────────────────────────

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

# ── 말하기 소스 ──────────────────────────────────────────────────────────────

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
    """날짜 기반으로 콘텐츠 수집. 듣기는 3-티어(short/medium/long) 리스트로 반환."""
    idx      = today.toordinal()
    week_idx = (idx // 7) % len(GRAMMAR_CURRICULUM)

    # 3-티어 듣기: 각 티어마다 날짜 기반 소스 순환
    short_src  = LISTENING_SHORT[idx % len(LISTENING_SHORT)]
    medium_src = LISTENING_MEDIUM[idx % len(LISTENING_MEDIUM)]
    long_src   = LISTENING_LONG[idx % len(LISTENING_LONG)]

    ls = _fetch_from_source(short_src);  ls["tier"] = "short";  ls["duration_hint"] = short_src["duration_hint"]
    lm = _fetch_from_source(medium_src); lm["tier"] = "medium"; lm["duration_hint"] = medium_src["duration_hint"]
    ll = _fetch_from_source(long_src);   ll["tier"] = "long";   ll["duration_hint"] = long_src["duration_hint"]

    reading  = _fetch_from_source(READING_SOURCES[idx % len(READING_SOURCES)])
    speaking = _fetch_from_source(SPEAKING_SOURCES[idx % len(SPEAKING_SOURCES)])

    topic, level, topic_kr = GRAMMAR_CURRICULUM[week_idx]

    return {
        "listening": [ls, lm, ll],
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
        return {"source": source["name"], "title": "Daily Practice", "url": "", "audio_url": "", "text": ""}


def _extract_audio_url(entry) -> str:
    """RSS 항목에서 오디오 URL을 추출. mp3/m4a/aac/ogg 등 모든 형식 지원."""
    # enclosures 필드 (BBC, VOA, ESL 표준)
    for enc in getattr(entry, "enclosures", []):
        href = enc.get("href", enc.get("url", ""))
        mime = enc.get("type", "")
        if href and ("audio" in mime or any(href.lower().endswith(ext) for ext in AUDIO_EXTS)):
            return href

    # links 필드 (일부 피드)
    for lnk in getattr(entry, "links", []):
        href = lnk.get("href", "")
        mime = lnk.get("type", "")
        if href and ("audio" in mime or any(href.lower().endswith(ext) for ext in AUDIO_EXTS)):
            return href

    # media_content 필드 (일부 피드)
    media = getattr(entry, "media_content", [])
    for m in (media if isinstance(media, list) else []):
        href = m.get("url", "")
        mime = m.get("type", "")
        if href and ("audio" in mime or any(href.lower().endswith(ext) for ext in AUDIO_EXTS)):
            return href

    # itunes:new-feed-url 같은 확장 필드에서 직접 mp3 링크 탐색
    for key in vars(entry):
        val = getattr(entry, key, "")
        if isinstance(val, str) and any(val.lower().endswith(ext) for ext in AUDIO_EXTS):
            return val

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
