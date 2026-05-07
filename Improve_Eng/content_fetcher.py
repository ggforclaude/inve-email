"""
Improve_Eng/content_fetcher.py
BBC / VOA / ESL RSS에서 일일 학습 콘텐츠를 수집합니다.

듣기 3-티어 구조:
  SHORT  (~1-3분): 5개 소스 풀에서 날짜 시드 셔플 → 오디오 있는 소스 우선
  MEDIUM (~4-7분): 6개 소스 풀에서 날짜 시드 셔플 → 오디오 있는 소스 우선
  LONG   (~8-15분): 5개 소스 풀에서 날짜 시드 셔플 → 오디오 있는 소스 우선

오디오를 못 가져올 경우: 에피소드 페이지 URL 링크 버튼으로 대체.
"""
import feedparser
import requests
import logging
import random
from bs4 import BeautifulSoup
from datetime import date

log = logging.getLogger(__name__)

AUDIO_EXTS = (".mp3", ".m4a", ".aac", ".ogg", ".wav", ".opus")

# ── 듣기 소스 (3-티어) ───────────────────────────────────────────────────────

LISTENING_SHORT = [  # ~1-3분: 5개 소스 풀
    {"name": "BBC The English We Speak",    "rss": "https://podcasts.files.bbci.co.uk/p02pc9s3.rss"},
    {"name": "BBC Global News Minute",      "rss": "https://podcasts.files.bbci.co.uk/p0bf37qw.rss"},
    {"name": "BBC Learning English Stories","rss": "https://podcasts.files.bbci.co.uk/p02pc9s1.rss"},
    {"name": "VOA Learning English",        "rss": "https://learningenglish.voanews.com/api/zovijqmz_q"},
    {"name": "BBC Lingohack",               "rss": "https://feeds.bbci.co.uk/learningenglish/english/features/lingohack/rss.xml"},
]

LISTENING_MEDIUM = [  # ~4-7분: 6개 소스 풀
    {"name": "BBC 6 Minute English",              "rss": "https://podcasts.files.bbci.co.uk/p02pc9pj.rss"},
    {"name": "BBC 6 Minute Grammar",              "rss": "https://podcasts.files.bbci.co.uk/p02pc9v1.rss"},
    {"name": "BBC Learning English Conversations","rss": "https://podcasts.files.bbci.co.uk/p02pc9zn.rss"},
    {"name": "BBC Business Daily",                "rss": "https://podcasts.files.bbci.co.uk/p002vsnb.rss"},
    {"name": "BBC Lingohack",                     "rss": "https://feeds.bbci.co.uk/learningenglish/english/features/lingohack/rss.xml"},
    {"name": "ESL Podcast",                       "rss": "https://www.eslpod.com/eslpod_feed.xml"},
]

LISTENING_LONG = [  # ~8-15분: 5개 소스 풀
    {"name": "BBC English At Work",               "rss": "https://podcasts.files.bbci.co.uk/p02pc9qx.rss"},
    {"name": "ESL Podcast",                       "rss": "https://www.eslpod.com/eslpod_feed.xml"},
    {"name": "All Ears English",                  "rss": "https://www.allearsenglish.com/feed/podcast"},
    {"name": "BBC 6 Minute English",              "rss": "https://podcasts.files.bbci.co.uk/p02pc9pj.rss"},
    {"name": "BBC Learning English Conversations","rss": "https://podcasts.files.bbci.co.uk/p02pc9zn.rss"},
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

    # 3-티어 듣기: 날짜 시드 셔플 후 오디오 있는 소스 우선 선택
    ls = _pick_with_audio(LISTENING_SHORT,  seed=idx * 10 + 1)
    lm = _pick_with_audio(LISTENING_MEDIUM, seed=idx * 10 + 2)
    ll = _pick_with_audio(LISTENING_LONG,   seed=idx * 10 + 3)

    ls["tier"] = "short";  ls["duration_hint"] = "약 1-3분"
    lm["tier"] = "medium"; lm["duration_hint"] = "약 4-7분"
    ll["tier"] = "long";   ll["duration_hint"] = "약 8-15분"

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

def _pick_with_audio(sources: list, seed: int) -> dict:
    """날짜 시드로 소스 셔플 후 오디오 URL이 있는 첫 번째 결과 반환.
    오디오 없으면 페이지 URL이라도 있는 결과, 그것도 없으면 첫 번째 결과."""
    rng = random.Random(seed)
    order = list(range(len(sources)))
    rng.shuffle(order)

    first = None
    best_with_url = None

    for i in order:
        result = _fetch_from_source(sources[i])
        if first is None:
            first = result
        if result.get("audio_url"):
            log.info(f"  오디오 확보: [{sources[i]['name']}]")
            return result
        if result.get("url") and best_with_url is None:
            best_with_url = result
            log.info(f"  오디오 없음, 페이지 URL 보관: [{sources[i]['name']}]")
        else:
            log.info(f"  오디오·URL 없음, 다음 소스 시도: [{sources[i]['name']}]")

    if best_with_url:
        log.warning("  전체 소스 오디오 없음 — 페이지 링크 버튼으로 대체")
        return best_with_url

    log.warning("  전체 소스 실패 — 텍스트 전용 반환")
    return first or {}


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
