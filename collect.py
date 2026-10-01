#!/usr/bin/env python3
"""안전보건 뉴스룸 수집기.

네이버 뉴스 검색 API(키가 있을 때) 또는 구글 뉴스 RSS(키가 없을 때)에서
config.json의 검색어로 기사를 모아, 키워드 규칙으로 분류하고,
같은 사건을 다룬 기사를 하나로 묶어 data/news.json에 저장합니다.

파이썬 3.9 이상, 표준 라이브러리만 사용합니다.

환경변수
  NAVER_CLIENT_ID, NAVER_CLIENT_SECRET  네이버 개발자센터 검색 API 키 (선택)
사용법
  python collect.py            # 수집 후 data/news.json 갱신
  python collect.py --dry-run  # 저장하지 않고 결과만 출력
  python collect.py --clean-only  # 새로 검색하지 않고 보관 기사만 현재 기준으로 정리
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha1
from pathlib import Path

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
DATA_PATH = ROOT / "data" / "news.json"
UA = "Mozilla/5.0 (compatible; SafetyNewsroom/1.0)"

# 도메인 → 언론사 이름 (네이버 API는 언론사명을 주지 않아 주소로 추정)
SOURCE_NAMES = {
    "yna.co.kr": "연합뉴스", "yonhapnews.co.kr": "연합뉴스", "newsis.com": "뉴시스", "news1.kr": "뉴스1",
    "chosun.com": "조선일보", "joongang.co.kr": "중앙일보", "donga.com": "동아일보", "hani.co.kr": "한겨레",
    "khan.co.kr": "경향신문", "hankookilbo.com": "한국일보", "kmib.co.kr": "국민일보", "seoul.co.kr": "서울신문",
    "segye.com": "세계일보", "munhwa.com": "문화일보", "hankyung.com": "한국경제", "mk.co.kr": "매일경제",
    "sedaily.com": "서울경제", "edaily.co.kr": "이데일리", "mt.co.kr": "머니투데이", "fnnews.com": "파이낸셜뉴스",
    "asiae.co.kr": "아시아경제", "heraldcorp.com": "헤럴드경제", "ajunews.com": "아주경제", "etoday.co.kr": "이투데이",
    "newspim.com": "뉴스핌", "dnews.co.kr": "대한경제", "ohmynews.com": "오마이뉴스", "pressian.com": "프레시안",
    "labortoday.co.kr": "매일노동뉴스", "safetynews.co.kr": "안전신문", "safety1stnews.com": "세이프티퍼스트닷뉴스",
    "anjunj.com": "안전저널", "kbs.co.kr": "KBS", "imbc.com": "MBC", "sbs.co.kr": "SBS", "ytn.co.kr": "YTN",
    "jtbc.co.kr": "JTBC", "mbn.co.kr": "MBN", "ichannela.com": "채널A", "tvchosun.com": "TV조선",
    "korea.kr": "정책브리핑", "daum.net": "다음뉴스", "moel.go.kr": "고용노동부", "kosha.or.kr": "안전보건공단", "lawtimes.co.kr": "법률신문",
    "dailian.co.kr": "데일리안", "nocutnews.co.kr": "노컷뉴스", "busan.com": "부산일보", "kookje.co.kr": "국제신문",
    "imaeil.com": "매일신문", "kado.net": "강원도민일보", "kwnews.co.kr": "강원일보", "kyeongin.com": "경인일보",
    "joongboo.com": "중부일보", "cnews.co.kr": "건설경제", "conslove.co.kr": "건설타임즈", "energy-news.co.kr": "에너지신문",
}

# 네이버 API는 언론사 이름을 주지 않아 기사 주소로 판단 (자주 보이는 곳 위주, 필요하면 추가)
SOURCE_NAMES.update({
    "businesspost.co.kr": "비즈니스포스트", "4th.kr": "포쓰저널", "newstomato.com": "뉴스토마토", "newsclaim.co.kr": "뉴스클레임",
    "gukjenews.com": "국제뉴스", "newsfreezone.co.kr": "뉴스프리존", "hidomin.com": "경북도민일보", "kyongbuk.co.kr": "경북일보",
    "segye.com": "세계일보", "mediatoday.co.kr": "미디어오늘", "livesnews.com": "라이브뉴스", "kgnews.co.kr": "경기신문",
    "huffingtonpost.kr": "허프포스트코리아", "imbc.com": "MBC", "straightnews.co.kr": "스트레이트뉴스", "pointdaily.co.kr": "포인트데일리",
    "newsprime.co.kr": "프라임경제", "mydaily.co.kr": "마이데일리", "insight.co.kr": "인사이트", "koscaj.com": "대한전문건설신문",
    "hankooki.com": "한국아이닷컴", "ziksir.com": "직썰", "christiandaily.co.kr": "기독일보", "newsway.co.kr": "뉴스웨이",
    "bizwatch.co.kr": "비즈워치", "thebell.co.kr": "더벨", "etnews.com": "전자신문", "zdnet.co.kr": "지디넷코리아",
    "inews24.com": "아이뉴스24", "ddaily.co.kr": "디지털데일리", "bloter.net": "블로터", "sisajournal.com": "시사저널",
    "sisain.co.kr": "시사IN", "newdaily.co.kr": "뉴데일리", "mediapen.com": "미디어펜", "ebn.co.kr": "EBN",
    "econovill.com": "이코노믹리뷰", "ekn.kr": "에너지경제", "kbiznews.co.kr": "중소기업뉴스", "incheonilbo.com": "인천일보",
    "kihoilbo.co.kr": "기호일보", "joongdo.co.kr": "중도일보", "daejonilbo.com": "대전일보", "ccdailynews.com": "충청일보",
    "jbnews.com": "중부매일", "kwangju.co.kr": "광주일보", "jnilbo.com": "전남일보", "jjan.kr": "전북일보",
    "domin.co.kr": "전북도민일보", "idomin.com": "경남도민일보", "knnews.co.kr": "경남신문", "gndomin.com": "경남도민신문",
    "ksilbo.co.kr": "경상일보", "iusm.co.kr": "울산매일", "ulsanpress.net": "울산신문", "yeongnam.com": "영남일보",
    "idaegu.com": "대구신문", "ihalla.com": "한라일보", "jejunews.com": "제주일보", "jejusori.net": "제주의소리",
    "kukinews.com": "쿠키뉴스", "dt.co.kr": "디지털타임스", "asiatoday.co.kr": "아시아투데이", "viva100.com": "브릿지경제",
    "nspna.com": "NSP통신", "newscj.com": "천지일보", "breaknews.com": "브레이크뉴스", "wikitree.co.kr": "위키트리",
    "wowtv.co.kr": "한국경제TV", "polinews.co.kr": "폴리뉴스", "lawissue.co.kr": "로이슈", "safetimes.co.kr": "세이프타임즈",
    "hkbs.co.kr": "환경일보", "ikld.kr": "국토일보", "hansbiz.co.kr": "한스경제", "womaneconomy.co.kr": "여성경제신문",
    "sisaweek.com": "시사위크", "newswork.co.kr": "뉴스워커", "beyondpost.co.kr": "비욘드포스트", "todayenergy.kr": "투데이에너지",
    "gasnews.com": "가스신문", "fntimes.com": "한국금융신문", "bizhankook.com": "비즈한국", "news2day.co.kr": "뉴스투데이",
    "mhns.co.kr": "문화뉴스", "pinpointnews.co.kr": "핀포인트뉴스", "g-enews.com": "글로벌이코노믹", "enewstoday.co.kr": "이뉴스투데이",
    "sentv.co.kr": "서울경제TV", "sportsseoul.com": "스포츠서울", "dailyan.com": "데일리안", "stardailynews.co.kr": "스타데일리뉴스",
    "ngetnews.com": "뉴스저널리즘", "cstimes.com": "컨슈머타임스", "consumernews.co.kr": "소비자가만드는신문", "smarttoday.co.kr": "스마트투데이",
    "thepublic.kr": "더퍼블릭", "ajunews.com": "아주경제", "e2news.com": "이투뉴스", "kpinews.kr": "KPI뉴스",
    "sedaily.com": "서울경제", "bizwnews.com": "비즈월드", "newsis.com": "뉴시스", "mbn.co.kr": "MBN", "cbs.co.kr": "CBS",
    "tbs.seoul.kr": "TBS", "obsnews.co.kr": "OBS", "ksmnews.co.kr": "경상매일신문", "kbmaeil.com": "경북매일",
    "gjdream.com": "광주드림", "namdonews.com": "남도일보", "mdilbo.com": "무등일보", "ggilbo.com": "금강일보",
    "cctoday.co.kr": "충청투데이", "dynews.co.kr": "동양일보", "inews365.com": "충북일보", "kado.net": "강원도민일보",
    "kyeongin.com": "경인일보", "joongboo.com": "중부일보", "suwonilbo.kr": "수원일보", "kjdaily.com": "광주매일신문",
    "newsian.co.kr": "뉴시안", "seoulwire.com": "서울와이어", "fetv.co.kr": "FETV", "ntoday.co.kr": "시사오늘",
    "kmaeil.com": "경인매일", "sisaon.co.kr": "시사온", "thefairnews.co.kr": "더페어", "dailypharm.com": "데일리팜",
    "medicaltimes.com": "메디칼타임즈", "docdocdoc.co.kr": "청년의사", "kormedi.com": "코메디닷컴",
})


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def now_kst() -> datetime:
    return datetime.now(KST)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def http_get(url: str, headers: dict | None = None, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:  # 키 오류 등은 다시 시도해도 같으므로 바로 포기
                raise
            last = e
            time.sleep(1.5 * (attempt + 1))
        except Exception as e:  # 네트워크 일시 오류는 두 번까지 다시 시도
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last  # type: ignore[misc]


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def source_from_url(url: str) -> str:
    host = urllib.parse.urlparse(url).hostname or ""
    host = host.lower().removeprefix("www.").removeprefix("m.").removeprefix("biz.").removeprefix("news.")
    for dom, name in SOURCE_NAMES.items():
        if host == dom or host.endswith("." + dom):
            return name
    return host


def to_kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)


# ---------------------------------------------------------------- 수집원

def fetch_naver(query: str, cid: str, secret: str) -> list[dict]:
    """네이버 뉴스 검색.

    2026년 7월 31일부터 네이버 개발자센터 신규 발급이 끝나고 NAVER API HUB(네이버 클라우드)로
    옮겨졌다. 기본은 API HUB 주소와 헤더를 쓰고, 예전 개발자센터 키를 가진 경우
    환경변수 NAVER_API=legacy 로 예전 주소를 쓸 수 있다(2027년 6월 30일까지).
    """
    q = urllib.parse.urlencode({"query": query, "display": 50, "sort": "date"})
    if os.getenv("NAVER_API", "hub").lower() == "legacy":
        url = "https://openapi.naver.com/v1/search/news.json?" + q
        headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}
    else:
        url = "https://naverapihub.apigw.ntruss.com/search/v1/news?" + q
        headers = {"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": secret}
    return parse_naver(json.loads(http_get(url, headers)))


def parse_naver(payload: dict) -> list[dict]:
    out = []
    for it in payload.get("items", []):
        orig = it.get("originallink") or it.get("link") or ""
        link = it.get("link") or ""
        # 네이버 뉴스에 실린 기사는 네이버 뉴스 화면으로, 아니면 언론사 원문으로 연결
        url = link if "n.news.naver.com" in link else orig
        try:
            pub = to_kst(parsedate_to_datetime(it.get("pubDate", "")))
        except Exception:
            continue
        out.append({
            "title": clean(it.get("title", "")),
            "summary": clean(it.get("description", "")),
            "url": url,
            "orig": orig,
            "source": source_from_url(orig),
            "published": pub.isoformat(timespec="minutes"),
        })
    return out


def fetch_google(query: str, days: int = 1) -> list[dict]:
    q = urllib.parse.quote(f"{query} when:{days}d")
    raw = http_get(f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko")
    return parse_google(raw)


def parse_google(raw: bytes) -> list[dict]:
    out = []
    root = ET.fromstring(raw)
    for it in root.iter("item"):
        title = clean(it.findtext("title", ""))
        src_el = it.find("source")
        source = clean(src_el.text) if src_el is not None and src_el.text else ""
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3].strip()
        for _ in range(2):
            title = re.sub(r"\s+-\s+[^-]{1,15}$", "", title)  # 제목 끝의 ' - 조선비즈' 같은 언론사 꼬리표
        if "." in source:  # 언론사 이름 대신 주소가 온 경우
            source = source_from_url("https://" + source)
        try:
            pub = to_kst(parsedate_to_datetime(it.findtext("pubDate", "")))
        except Exception:
            continue
        out.append({
            "title": title,
            "summary": "",  # 구글 뉴스 RSS의 설명은 제목 반복이라 쓰지 않음
            "url": it.findtext("link", ""),
            "source": source or "구글 뉴스",
            "published": pub.isoformat(timespec="minutes"),
        })
    return out


# ---------------------------------------------------------------- 분류·정리

def contains_any(text: str, words: list[str]) -> bool:
    return any(w.lower() in text for w in words)


def watch_hits(art: dict, cfg: dict) -> list[str]:
    """우리 회사·계열사 이름 중 기사 '제목'에 나온 이름 목록.

    네이버 요약문에는 기사 본문 일부가 들어가 계열사 이름이 스치듯 언급되는 경우가 많아
    제목만 본다. 'SPC'처럼 다른 뜻(특수목적법인 등)으로도 쓰이는 이름은
    config의 watch.names에서 'SPC그룹', 'SPC삼립'처럼 구체적으로 적는다.
    """
    w = cfg.get("watch") or {}
    title = art["title"].lower()
    return [n for n in w.get("names", []) if n.lower() in title]


def count_terms(text: str, words: list[str]) -> int:
    return sum(1 for w in words if w.lower() in text)


def relevant(art: dict, cfg: dict) -> bool:
    """안전보건 기사인지 판단.

    제목에 핵심어가 있으면 통과. 제목에 없으면 요약문에 서로 다른 핵심어가 2개 이상 있어야 통과
    (요약문에 '산업안전보건법'이 한 번 스친 정치 기사 등을 거르기 위함).
    """
    title = art["title"].lower()
    desc = art.get("summary", "").lower()
    both = title + " " + desc
    if contains_any(both, cfg["exclude_if_any"]):
        return False
    w = cfg.get("watch") or {}
    if watch_hits(art, cfg):
        # 우리 회사 기사: 제목에 안전·노동 관련 단어가 있거나, 요약문에 사고·산재 같은 강한 단어가 있으면 통과
        if contains_any(both, w.get("exclude_if_any", [])):
            return False
        # 우리 회사 이름이 제목에 있는 기사는 이 기준만 적용 (경영·실적 기사가 일반 기준으로 새어 들어오지 않게)
        return contains_any(title, w.get("must_include_any", [])) or contains_any(desc, w.get("strong_in_summary", []))
    must = cfg["must_include_any"]
    if contains_any(title, must):
        return True
    # 제목에 핵심어가 없으면 요약문에 서로 다른 핵심어 3개 이상 + 제목이 정치·증시 기사가 아닐 때만 통과
    if contains_any(title, cfg.get("block_title_if_summary_only", [])):
        return False
    return count_terms(desc, must) >= 3


def classify(art: dict, found_by: set[str], cfg: dict) -> str:
    title = art["title"].lower()
    desc = art["summary"].lower()
    best, best_score = None, -1
    for cat in cfg["categories"]:
        score = 2 if cat["id"] in found_by else 0
        for kw in cat["keywords"]:
            k = kw.lower()
            if k in title:
                score += 2
            elif k in desc:
                score += 1
        if score > best_score:  # 동점이면 config 순서(앞쪽)가 이김
            best, best_score = cat["id"], score
    return best or cfg["categories"][0]["id"]


def norm_title(t: str) -> str:
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)|【[^】]*】", " ", t)
    return re.sub(r"[^0-9A-Za-z가-힣]", "", t).lower()


def bigrams(s: str) -> set[str]:
    return {s[i:i + 2] for i in range(len(s) - 1)}


def similar(a: str, b: str) -> bool:
    """제목 두 개가 같은 사건을 다루는지 대략 판단한다.

    글자 두 개씩 끊은 조각이 전체의 45% 이상 겹치거나(비슷한 길이의 제목),
    짧은 쪽 제목 조각의 55% 이상이 긴 쪽에 들어 있으면(한쪽이 요약형 제목) 같은 사건으로 본다.
    """
    A, B = bigrams(a), bigrams(b)
    if not A or not B:
        return False
    inter = len(A & B)
    if inter / len(A | B) >= 0.45:
        return True
    return inter >= 9 and inter / min(len(A), len(B)) >= 0.55


def norm_url(u: str) -> str:
    p = urllib.parse.urlparse(u)
    host = (p.hostname or "").removeprefix("www.").removeprefix("m.")
    return f"{host}{p.path.rstrip('/')}?{p.query}"


def art_id(url: str) -> str:
    return sha1(norm_url(url).encode()).hexdigest()[:12]


def merge(existing: list[dict], fresh: list[dict]) -> tuple[list[dict], int]:
    """새 기사를 기존 목록에 합친다. 같은 사건(제목 유사) 기사는 related로 묶는다."""
    by_id = {a["id"]: a for a in existing}
    seen_urls = {norm_url(a["url"]) for a in existing} | {norm_url(a["orig"]) for a in existing if a.get("orig")}
    for a in existing:
        for r in a.get("related", []):
            seen_urls.add(norm_url(r["url"]))
            if r.get("orig"):
                seen_urls.add(norm_url(r["orig"]))
    by_link = {}
    for a in existing:
        for x in [a] + a.get("related", []):
            by_link[norm_url(x.get("orig") or x["url"])] = x
    added = 0
    for art in sorted(fresh, key=lambda x: x["published"]):
        nu = norm_url(art["url"])
        no = norm_url(art["orig"]) if art.get("orig") else nu
        if nu in seen_urls or no in seen_urls:
            # 예전에 언론사 주소로 저장된 기사가 다시 잡히면 네이버 뉴스 주소로 바꿔 둔다
            obj = by_link.get(no)
            if obj is not None and "n.news.naver.com" in art["url"] and "n.news.naver.com" not in obj["url"]:
                obj["orig"] = obj.get("orig") or obj["url"]
                obj["url"] = art["url"]
            continue
        seen_urls.update({nu, no})
        nt = norm_title(art["title"])
        day = art["published"][:10]
        host = None
        for cand in by_id.values():
            if abs((datetime.fromisoformat(cand["published"]) - datetime.fromisoformat(art["published"])).days) > 1:
                continue
            if nt == norm_title(cand["title"]) or similar(nt, norm_title(cand["title"])):
                host = cand
                break
        if host:
            rel = host.setdefault("related", [])
            for r in [{"source": art["source"], "url": art["url"], "orig": art.get("orig", ""), "title": art["title"]}] + art.get("related", []):
                if r["source"] != host["source"] and all(x["source"] != r["source"] for x in rel):
                    rel.append(r)
            if not host.get("summary") and art.get("summary"):
                host["summary"] = art["summary"]
            continue
        art.setdefault("id", art_id(art["url"]))
        art.setdefault("related", [])
        art["day"] = day
        by_id[art["id"]] = art
        added += 1
    return list(by_id.values()), added


def build_highlights(articles: list[dict], today: str) -> list[dict]:
    """오늘 여러 언론이 다룬 기사 순으로 '많이 보도된 이슈'를 만든다 (AI 없이 규칙 기반)."""
    days = sorted({a["day"] for a in articles if a["day"] <= today}, reverse=True)
    if not days:
        return []
    today = days[0]  # 오늘 기사가 아직 없으면(주말·이른 아침) 가장 최근 날짜 기준
    todays = [a for a in articles if a["day"] == today]
    todays.sort(key=lambda a: (len(a.get("related", [])), a["published"]), reverse=True)
    picks = [a for a in todays if a.get("related")][:5]
    if len(picks) < 3:  # 묶인 기사가 적으면 분류별 최신 기사로, 그래도 모자라면 최신순으로 채움
        have = {a["cat"] for a in picks}
        latest = sorted(todays, key=lambda a: a["published"], reverse=True)
        for a in latest:
            if len(picks) >= 5:
                break
            if a not in picks and a["cat"] not in have:
                picks.append(a)
                have.add(a["cat"])
        for a in latest:
            if len(picks) >= 3:
                break
            if a not in picks:
                picks.append(a)
    return [{"id": a["id"], "title": a["title"], "url": a["url"], "source": a["source"],
             "cat": a["cat"], "day": a["day"], "count": 1 + len(a.get("related", []))} for a in picks]


# ---------------------------------------------------------------- 실행

def collect(cfg: dict) -> list[dict]:
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    use_naver = bool(cid and secret)
    log("수집원:", "네이버 뉴스 API" if use_naver else "구글 뉴스 RSS (네이버 키 없음)")
    pool: dict[str, dict] = {}
    found_by: dict[str, set[str]] = {}
    errors = 0
    watch_days = int((cfg.get("watch") or {}).get("lookback_days", 30))
    groups = [(c["id"], c["queries"]) for c in cfg["categories"]]
    if cfg.get("watch", {}).get("queries"):
        groups.append(("watch", cfg["watch"]["queries"]))
    for cat_id, queries in groups:
        for q in queries:
            try:
                # 우리 회사 검색은 매번 최근 30일치를 가져와 30일 칸이 늘 채워지게 함 (중복은 자동으로 건너뜀)
                days = watch_days if cat_id == "watch" else 1
                items = fetch_naver(q, cid, secret) if use_naver else fetch_google(q, days)
            except Exception as e:
                errors += 1
                log(f"  ! '{q}' 실패: {e}")
                continue
            for it in items:
                key = norm_url(it["url"])
                pool.setdefault(key, it)
                found_by.setdefault(key, set()).add(cat_id)
            time.sleep(0.2)
    total_queries = sum(len(q) for _, q in groups)
    if errors == total_queries and use_naver:
        log("네이버 검색이 모두 실패해 구글 뉴스 RSS로 다시 수집합니다. API 키와 신청한 API를 확인하세요.")
        os.environ.pop("NAVER_CLIENT_ID", None)
        return collect(cfg)
    if errors == total_queries:
        raise SystemExit("모든 검색이 실패했습니다. 네트워크나 API 키를 확인하세요.")

    cutoff = now_kst() - timedelta(days=cfg.get("max_age_days", 3))
    watch_cutoff = now_kst() - timedelta(days=watch_days + 1)
    out = []
    for key, art in pool.items():
        pub = datetime.fromisoformat(art["published"])
        is_watch = "watch" in found_by[key] and bool(watch_hits(art, cfg))
        if pub < (watch_cutoff if is_watch else cutoff):
            continue
        if not relevant(art, cfg):
            continue
        art["cat"] = classify(art, found_by[key], cfg)
        out.append(art)
    log(f"검색 결과 {len(pool)}건 → 조건 통과 {len(out)}건")
    return out


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    cfg = load_json(CONFIG_PATH, None)
    if not cfg:
        raise SystemExit("config.json을 찾을 수 없습니다.")
    data = load_json(DATA_PATH, {"articles": []})

    # 보관 중인 기사에도 지금의 config 기준을 다시 적용하고 같은 사건 기사를 다시 묶는다.
    # (config.json을 고치면 다음 수집 때 예전 기사까지 정리됨)
    stored = [a for a in data.get("articles", []) if relevant(a, cfg)]
    for a in stored:  # 예전 수집분의 주소형 출처 이름 정리
        for x in [a] + a.get("related", []):
            if "." in x.get("source", ""):
                x["source"] = source_from_url("https://" + x["source"])
    stored, _ = merge([], stored)
    removed = len(data.get("articles", [])) - len(stored)
    if removed:
        log(f"보관 기사 정리: {removed}건 제외 또는 같은 사건으로 묶음")

    fresh = [] if "--clean-only" in argv else collect(cfg)
    articles, added = merge(stored, fresh)

    keep_from = (now_kst() - timedelta(days=cfg.get("keep_days", 90))).date().isoformat()
    articles = [a for a in articles if a["day"] >= keep_from]
    articles.sort(key=lambda a: a["published"], reverse=True)
    for a in articles:  # 우리 회사 관련 표시 (config를 바꾸면 전체 기사에 다시 적용)
        hits = watch_hits(a, cfg)
        for r in a.get("related", []):
            hits += [n for n in (cfg.get("watch") or {}).get("names", []) if n.lower() in r.get("title", "").lower() and n not in hits]
        a["watch"] = hits

    today = now_kst().date().isoformat()
    result = {
        "updatedAt": now_kst().isoformat(timespec="minutes"),
        "categories": [{"id": c["id"], "label": c["label"]} for c in cfg["categories"]],
        "watchLabel": (cfg.get("watch") or {}).get("label", "우리 회사"),
        "highlights": build_highlights(articles, today),
        "articles": articles,
    }
    log(f"새 기사 {added}건 추가, 보관 {len(articles)}건")
    if dry:
        print(json.dumps(result, ensure_ascii=False, indent=2)[:4000])
        return 0
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(DATA_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
