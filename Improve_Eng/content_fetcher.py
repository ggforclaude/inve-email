"""
Improve_Eng/content_fetcher.py
BBC / VOA RSS에서 일일 학습 콘텐츠를 수집합니다.

듣기: SHORT 클립 1개만 사용 (약 2-3분). 오디오 없으면 페이지 URL로 대체.
문법: 24개 주제 일별 순환 (카테고리 교차 배치 → 같은 카테고리 최소 6일 간격).
어원: 30개 단어 일별 순환.
"""
import feedparser
import requests
import logging
import random
from bs4 import BeautifulSoup
from datetime import date

log = logging.getLogger(__name__)

AUDIO_EXTS = (".mp3", ".m4a", ".aac", ".ogg", ".wav", ".opus")

# ── 듣기 소스 (SHORT 전용, 약 2-3분) ─────────────────────────────────────────

LISTENING_SHORT = [
    # ── BBC Learning English (2-3분 클립) ─────────────────────────────────────
    {"name": "BBC The English We Speak",        "rss": "https://podcasts.files.bbci.co.uk/p02pc9s3.rss"},
    {"name": "BBC Global News Minute",          "rss": "https://podcasts.files.bbci.co.uk/p0bf37qw.rss"},
    {"name": "BBC Learning English Stories",    "rss": "https://podcasts.files.bbci.co.uk/p02pc9s1.rss"},
    {"name": "BBC Lingohack",                   "rss": "https://feeds.bbci.co.uk/learningenglish/english/features/lingohack/rss.xml"},
    {"name": "BBC English In A Minute",         "rss": "https://podcasts.files.bbci.co.uk/p0cms2fy.rss"},
    {"name": "BBC The Experiment",              "rss": "https://podcasts.files.bbci.co.uk/p02pc9s2.rss"},
    # ── VOA Learning English ───────────────────────────────────────────────────
    {"name": "VOA Learning English",            "rss": "https://learningenglish.voanews.com/api/zovijqmz_q"},
    {"name": "VOA Learning English Words",      "rss": "https://learningenglish.voanews.com/api/zrqpie$z_t"},
    # ── Business English ───────────────────────────────────────────────────────
    {"name": "BBC Business English Expressions","rss": "https://podcasts.files.bbci.co.uk/p002vsmz.rss"},
    {"name": "Speak Business English",          "rss": "https://speakbusinessenglish.libsyn.com/rss"},
    # ── Vocabulary & Phrases ──────────────────────────────────────────────────
    {"name": "Merriam-Webster Word of the Day", "rss": "https://www.merriam-webster.com/wotd/feed/rss2"},
    {"name": "Cambridge English Words",         "rss": "https://dictionary.cambridge.org/feed/"},
]

# ── 독해 소스 ─────────────────────────────────────────────────────────────────

READING_SOURCES = [
    {"name": "VOA Learning English News",       "rss": "https://learningenglish.voanews.com/api/zovijqmz_q"},
    {"name": "BBC Learning English Lingohack",  "rss": "https://feeds.bbci.co.uk/learningenglish/english/features/lingohack/rss.xml"},
]

# ── 말하기 소스 ───────────────────────────────────────────────────────────────

SPEAKING_SOURCES = [
    {"name": "BBC Learning English Stories",       "rss": "https://podcasts.files.bbci.co.uk/p02pc9s1.rss"},
    {"name": "BBC Learning English Conversations", "rss": "https://podcasts.files.bbci.co.uk/p02pc9zn.rss"},
]

# ── 문법 커리큘럼 (24개, 일별 순환) ─────────────────────────────────────────
# 카테고리별 교차 배치: 시제 / 조동사 / 가정·절 / 문장구조 / 어휘레벨 / 고급
# 동일 카테고리 최소 6일 간격 → 반복 학습 vs 새 주제 균형 유지
GRAMMAR_CURRICULUM = [
    # 1  시제: Present Perfect vs Simple Past
    ("Present Perfect vs Simple Past", "B1", "현재완료 vs 단순과거"),
    # 2  조동사: can / could
    ("Modal Verbs: can / could — 능력과 공손", "B1", "능력·공손 조동사"),
    # 3  절: First Conditional
    ("First Conditional", "B1", "실현 가능한 조건문"),
    # 4  구조: Passive Voice
    ("Passive Voice", "B1", "수동태"),
    # 5  어휘: Articles a / an / the
    ("Articles: a / an / the", "B1", "관사"),
    # 6  고급: Inversion for Emphasis
    ("Inversion for Emphasis", "B2", "강조 도치"),
    # 7  시제: Past Perfect
    ("Past Perfect Tense", "B2", "과거완료"),
    # 8  조동사: should / ought to / had better
    ("Modal Verbs: should / ought to / had better", "B1", "의무·충고 조동사"),
    # 9  절: Second Conditional
    ("Second Conditional", "B2", "가정법 과거"),
    # 10 구조: Reported Speech
    ("Reported Speech", "B2", "간접화법"),
    # 11 어휘: Gerunds vs Infinitives
    ("Gerunds vs Infinitives", "B2", "동명사 vs 부정사"),
    # 12 고급: Subjunctive Mood
    ("Subjunctive Mood", "B2", "가정법 현재 (요구·제안 구문)"),
    # 13 시제: Future Tenses
    ("Future Tenses: will / going to / present continuous", "B1", "미래 표현 3가지"),
    # 14 조동사: must / have to / need to
    ("Modal Verbs: must / have to / need to", "B1", "의무·필요 조동사"),
    # 15 절: Third Conditional & Mixed
    ("Third Conditional & Mixed Conditionals", "B2", "가정법 과거완료·혼합"),
    # 16 구조: Relative Clauses
    ("Relative Clauses: defining vs non-defining", "B2", "관계절"),
    # 17 어휘: Prepositions of Time
    ("Prepositions of Time: at / in / on / by", "B1", "시간 전치사"),
    # 18 고급: Ellipsis and Substitution
    ("Ellipsis and Substitution", "C1", "생략과 대용"),
    # 19 시제: Present Simple vs Continuous
    ("Present Simple vs Present Continuous", "A2", "단순현재 vs 현재진행"),
    # 20 어휘: Phrasal Verbs – Business
    ("Phrasal Verbs – Business Context", "B1", "구동사 (비즈니스)"),
    # 21 구조: Comparative & Superlative
    ("Comparative and Superlative Adjectives", "B1", "비교급·최상급"),
    # 22 어휘: Prepositions of Place
    ("Prepositions of Place: at / in / on / by", "B1", "장소 전치사"),
    # 23 시제: Past Simple vs Past Continuous
    ("Past Simple vs Past Continuous", "B1", "단순과거 vs 과거진행"),
    # 24 구조: Noun Clauses
    ("Noun Clauses and Embedded Questions", "B2", "명사절과 간접의문문"),
]

# ── 발음 커리큘럼 (15개, 일별 순환) ─────────────────────────────────────────
# 한국인이 특히 취약한 발음 포인트 — 매일 1가지 집중
PRONUNCIATION_CURRICULUM = [
    ("r vs l 구분",          "r은 혀를 말아 입천장에 닿지 않게, l은 혀끝을 윗잇몸에 확실히 댐",
     ["really /ríːli/", "rally /réli/", "river /rívər/", "liver /lívər/"]),
    ("f vs p 구분",          "f는 윗니를 아랫입술에 대고 바람, p는 두 입술로 터뜨림",
     ["food /fuːd/", "pool /puːl/", "fee /fiː/", "pea /piː/"]),
    ("v vs b 구분",          "v는 윗니를 아랫입술에 대고 진동, b는 두 입술로 막아 터뜨림",
     ["very /véri/", "berry /béri/", "vest /vest/", "best /best/"]),
    ("th 유성음 /ð/",        "혀끝을 윗니 사이에 살짝 내밀고 목소리 진동",
     ["the /ðə/", "this /ðɪs/", "that /ðæt/", "mother /mʌðər/"]),
    ("th 무성음 /θ/",        "혀끝을 윗니 사이에 살짝 내밀고 바람만 내보냄",
     ["think /θɪŋk/", "three /θriː/", "health /helθ/", "month /mʌnθ/"]),
    ("짧은 모음 vs 긴 모음",  "ship /ɪ/ vs sheep /iː/ — 입 모양과 길이 모두 다름",
     ["ship /ʃɪp/", "sheep /ʃiːp/", "hit /hɪt/", "heat /hiːt/"]),
    ("어말 자음 탈락 방지",   "한국어는 받침 뒤 모음을 붙이는 경향 — 마지막 자음만 닫고 끝내기",
     ["fact /fækt/", "next /nekst/", "helped /helpt/", "asked /æskt/"]),
    ("단어 강세: 2음절 명사", "명사는 보통 첫 음절 강세 — REcord, PROtest, PERmit",
     ["REcord", "PROtest", "PERmit", "CONtent"]),
    ("단어 강세: 2음절 동사", "동사는 보통 두 번째 음절 강세 — reCORD, proTEST, perMIT",
     ["reCORD", "proTEST", "perMIT", "conTENT"]),
    ("-ed 어미 발음 3가지",   "/t/: 무성음 뒤 | /d/: 유성음 뒤 | /ɪd/: t·d로 끝날 때",
     ["worked /wɜːrkt/", "called /kɔːld/", "wanted /wɒntɪd/", "needed /niːdɪd/"]),
    ("-s/-es 어미 발음 3가지","/ s/: 무성음 뒤 | /z/: 유성음 뒤 | /ɪz/: s·z·ch·sh로 끝날 때",
     ["books /bʊks/", "dogs /dɒgz/", "watches /wɒtʃɪz/", "buses /bʌsɪz/"]),
    ("연음 (Linking)",       "자음으로 끝나는 단어 + 모음으로 시작하는 단어는 이어서 발음",
     ["pick it up → pi-ki-tup", "turn it on → tur-ni-ton", "look at it → loo-ka-tit"]),
    ("약화 (Reduction)",     "기능어(of·to·for·and·at)는 빠르게 약화 — /ə/ 로 줄어듦",
     ["cup of tea → cupə tea", "a lot of → ə lɒtə", "want to → wanna"]),
    ("문장 강세와 리듬",      "내용어(명사·동사·형용사)는 강하게, 기능어(관사·전치사)는 약하게",
     ["I WANT to GO to the STORE", "She's WORKING on a NEW project"]),
    ("억양: 의문문",         "Yes/No 질문은 끝이 올라가고 ↗, Wh- 질문은 끝이 내려감 ↘",
     ["Are you READY? ↗", "Where are you GOING? ↘", "Did you SEE it? ↗"]),
]

# ── 어원 커리큘럼 (30개, 일별 순환) ─────────────────────────────────────────
# (단어, 원어, 어원 설명 한국어, 현대 의미)
ETYMOLOGY_CURRICULUM = [
    ("sincere",    "라틴어 sine cera (밀랍 없이)",     "로마 조각가가 결함을 밀랍으로 숨겼는데, 최고 작품은 밀랍 없이(sine cera) 완성됨",          "진실한, 진심 어린"),
    ("salary",     "라틴어 salarium (소금 급여)",       "로마 병사는 소금(sal)으로 급여를 받았음. salt와 같은 어근",                              "급여, 봉급"),
    ("muscle",     "라틴어 musculus (작은 쥐)",        "팔을 구부릴 때 근육이 움직이는 모습이 쥐처럼 보인다 하여",                                 "근육"),
    ("candidate",  "라틴어 candidatus (흰옷 입은)",    "로마 선거 출마자는 순결을 상징하는 흰 토가(candida)를 입었음",                            "후보자"),
    ("disaster",   "라틴어 dis + astrum (나쁜 별)",    "별의 위치가 나쁘면 재앙이 온다는 점성술 믿음에서 유래",                                   "재앙, 참사"),
    ("company",    "라틴어 com + panis (함께 빵을)",   "같이 빵을 나눠 먹는 동료에서 유래. companion(동료)과 동근",                              "회사, 동료"),
    ("calculate",  "라틴어 calculus (작은 돌)",        "로마인이 주판 대신 조약돌(calculus)로 계산했음",                                       "계산하다"),
    ("deadline",   "영어 dead + line",               "남북전쟁 포로수용소에서 그 선을 넘으면 사살한다는 경계선에서 유래",                           "마감 기한"),
    ("bankrupt",   "이탈리아어 banca rotta (깨진 탁자)", "중세 환전상이 파산하면 거래 탁자(banca)를 부수는 관습에서",                              "파산한"),
    ("quiz",       "18세기 아일랜드 속어",              "더블린 극장주 Daly가 무의미한 단어를 낙서하면 하루 만에 유행어로 만든 일화에서 유래",           "퀴즈, 시험"),
    ("panic",      "그리스어 Panikos (목신 판의)",      "목신 판(Pan)이 갑자기 나타나 공포를 일으킨다는 신화에서",                                 "공황, 극도의 공포"),
    ("strategy",   "그리스어 strategos (군대 지도자)", "stratos(군대) + agein(이끌다) → 장군의 기술",                                         "전략"),
    ("focus",      "라틴어 focus (화덕, 중심)",        "로마 가정의 화덕이 집의 중심이었던 데서 유래",                                           "초점, 집중"),
    ("invest",     "라틴어 investire (옷 입히다)",     "중세에 왕이 신하에게 땅을 수여할 때 옷(vestis)을 입혀 권한 부여",                          "투자하다"),
    ("risk",       "이탈리아어 risco (암초)",          "항해 중 암초 근처를 항행하는 위험에서 유래",                                             "위험, 위험을 감수하다"),
    ("budget",     "고프랑스어 bougette (작은 가방)",  "재무장관이 예산서를 담은 가죽 가방(bougette)을 들고 의회에 출석한 데서",                     "예산"),
    ("magazine",   "아랍어 makhazin (창고)",          "지식·정보를 저장해 두는 '창고'라는 의미로 출판물에 사용됨",                                 "잡지, 탄창"),
    ("candidate",  "라틴어 candidatus (흰옷 입은)",    "로마 선거 출마자는 순결을 상징하는 흰 토가를 입었음",                                     "후보자"),
    ("serendipity","페르시아 동화 Serendip(스리랑카)", "세 왕자가 우연히 훌륭한 발견을 하는 동화에서 Horace Walpole이 만든 단어",                   "뜻밖의 행운"),
    ("berserk",    "고대 노르드어 berserkr (곰 가죽)", "전투에서 곰 가죽을 입고 광분하던 바이킹 전사에서 유래",                                    "극도로 흥분한, 폭주하는"),
    ("boycott",    "아일랜드 지주 대리인 Charles Boycott", "1880년 소작인들이 Boycott을 집단 거부한 사건에서 단어화",                            "불매운동, 거부하다"),
    ("mentor",     "그리스 신화 멘토르(Mentor)",       "오디세우스가 트로이 전쟁 중 아들 텔레마코스 교육을 맡긴 현자의 이름에서",                     "멘토, 스승"),
    ("rival",      "라틴어 rivalis (강을 공유하는)",   "같은 강(rivus) 물을 사용하는 이웃 사이의 경쟁 관계에서",                                  "경쟁자"),
    ("travel",     "라틴어 tripalium (고문 도구)",     "중세 여행이 고문(tripalium)처럼 고달팠던 데서 travail(고통)과 동근",                     "여행하다"),
    ("enthusiasm", "그리스어 enthousiasmos (신이 깃든)", "en(안에) + theos(신) → 신에게 감화받은 열정 상태",                                    "열정, 열의"),
    ("lucid",      "라틴어 lucidus (빛나는)",         "lux(빛)과 동근 → 명확하고 투명한 사고",                                              "명확한, 이해하기 쉬운"),
    ("colleague",  "라틴어 collega (함께 선택된)",     "col(함께) + legare(선택하다/보내다) → 같이 선발된 동료",                                "동료"),
    ("quarantine", "이탈리아어 quarantina (40일)",    "14세기 흑사병 때 선박을 40일간 격리한 베네치아 방역 정책에서",                              "격리, 검역"),
    ("clue",       "고영어 clew (실뭉치)",            "그리스 신화에서 테세우스가 미로를 탈출할 때 아리아드네의 실(clew)에서 유래",                   "단서, 실마리"),
    ("salary",     "라틴어 salarium (소금)",          "로마 병사의 소금 급여에서. '소금값 못하는 사람'이라는 표현도 여기서 유래",                     "급여"),
]


# ── 메인 진입점 ───────────────────────────────────────────────────────────────

async def fetch_daily_content(today: date) -> dict:
    """날짜 기반 콘텐츠 수집.
    듣기: 단일 SHORT 클립 (dict, not list).
    문법: 24개 주제 일별 순환.
    어원: 30개 단어 일별 순환.
    """
    idx      = today.toordinal()
    day_idx  = idx % len(GRAMMAR_CURRICULUM)   # 일별 순환 (24주기)
    etym_idx = idx % len(ETYMOLOGY_CURRICULUM)  # 일별 순환 (30주기)

    # 단일 SHORT 듣기 클립
    listening = _pick_with_audio(LISTENING_SHORT, seed=idx)
    listening["tier"]          = "short"
    listening["duration_hint"] = "약 2-3분"

    reading  = _fetch_from_source(READING_SOURCES[idx % len(READING_SOURCES)])
    speaking = _fetch_from_source(SPEAKING_SOURCES[idx % len(SPEAKING_SOURCES)])

    topic, level, topic_kr = GRAMMAR_CURRICULUM[day_idx]
    etym  = ETYMOLOGY_CURRICULUM[etym_idx]
    pron_idx = idx % len(PRONUNCIATION_CURRICULUM)
    pron  = PRONUNCIATION_CURRICULUM[pron_idx]

    return {
        "listening": listening,      # 단일 dict (리스트 아님)
        "reading":   reading,
        "speaking":  speaking,
        "grammar": {
            "topic":  topic,
            "level":  level,
            "korean": topic_kr,
            "source": "British Council / Perfect English Grammar",
            "text":   "",
        },
        "etymology": {
            "word":    etym[0],
            "origin":  etym[1],
            "story":   etym[2],
            "meaning": etym[3],
        },
        "pronunciation": {
            "focus":    pron[0],
            "rule":     pron[1],
            "examples": pron[2],
        },
    }


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _pick_with_audio(sources: list, seed: int) -> dict:
    """날짜 시드로 소스 셔플 후 오디오 URL이 있는 첫 번째 결과 반환."""
    rng   = random.Random(seed)
    order = list(range(len(sources)))
    rng.shuffle(order)

    first         = None
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
    """RSS 항목에서 오디오 URL을 추출."""
    for enc in getattr(entry, "enclosures", []):
        href = enc.get("href", enc.get("url", ""))
        mime = enc.get("type", "")
        if href and ("audio" in mime or any(href.lower().endswith(ext) for ext in AUDIO_EXTS)):
            return href

    for lnk in getattr(entry, "links", []):
        href = lnk.get("href", "")
        mime = lnk.get("type", "")
        if href and ("audio" in mime or any(href.lower().endswith(ext) for ext in AUDIO_EXTS)):
            return href

    media = getattr(entry, "media_content", [])
    for m in (media if isinstance(media, list) else []):
        href = m.get("url", "")
        mime = m.get("type", "")
        if href and ("audio" in mime or any(href.lower().endswith(ext) for ext in AUDIO_EXTS)):
            return href

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
