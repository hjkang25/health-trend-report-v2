# =============================================================
# collect_news.py  –  네이버 뉴스 + 구글 뉴스 수집 모듈
# =============================================================

import time
import random
import logging
from datetime import datetime
from typing import List, Dict

import requests
import feedparser
from bs4 import BeautifulSoup

from config import (
    USER_AGENT,
    REQUEST_TIMEOUT,
    REQUEST_DELAY,
    MAX_RETRIES,
    MAX_ARTICLES_PER_QUERY,
    MAX_PAGES_PER_QUERY,
    NAVER_NEWS_URL,
    GOOGLE_NEWS_RSS_URL,
)

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


# ─────────────────────────────────────────────────────────────
# 내부 유틸
# ─────────────────────────────────────────────────────────────

def _sleep():
    """요청 간 랜덤 딜레이."""
    time.sleep(random.uniform(*REQUEST_DELAY))


def _get(url: str) -> requests.Response | None:
    """재시도 포함 GET 요청."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            logger.warning("GET 실패 (%d/%d) %s – %s", attempt, MAX_RETRIES, url, e)
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)   # 지수 백오프
    return None


# ─────────────────────────────────────────────────────────────
# 구글 뉴스 RSS 수집
# ─────────────────────────────────────────────────────────────

def collect_google_news(queries: List[str]) -> List[Dict]:
    """Google News RSS 피드에서 기사 수집."""
    articles: List[Dict] = []
    today = datetime.now().strftime("%Y-%m-%d")

    for query in queries:
        url = GOOGLE_NEWS_RSS_URL.format(query=requests.utils.quote(query))
        logger.info("[Google] 쿼리: %s", query)

        try:
            feed = feedparser.parse(url)
        except Exception as e:
            logger.error("[Google] feedparser 오류 (%s): %s", query, e)
            _sleep()
            continue

        count = 0
        for entry in feed.entries:
            if count >= MAX_ARTICLES_PER_QUERY:
                break

            # 구글 뉴스 제목에서 언론사 접미사 제거 (" - OO뉴스")
            raw_title = entry.get("title", "").strip()
            title = raw_title.rsplit(" - ", 1)[0] if " - " in raw_title else raw_title

            # description 태그에 HTML이 섞여 있으므로 파싱
            raw_desc = entry.get("summary", "")
            desc = BeautifulSoup(raw_desc, "lxml").get_text(" ", strip=True)

            published = entry.get("published", today)

            articles.append({
                "date":        today,
                "source":      "google",
                "query":       query,
                "title":       title,
                "description": desc,
                "link":        entry.get("link", ""),
                "published":   published,
            })
            count += 1

        logger.info("[Google] %s → %d건 수집", query, count)
        _sleep()

    return articles


# ─────────────────────────────────────────────────────────────
# 네이버 뉴스 수집
# ─────────────────────────────────────────────────────────────

def _parse_naver_page(html: str, query: str, today: str) -> List[Dict]:
    """네이버 뉴스 검색 결과 HTML 파싱 (2025-2026 신 UI 대응)."""
    soup = BeautifulSoup(html, "lxml")
    items: List[Dict] = []

    # ── 신 UI (2025~ sds-comps 기반) ────────────────────────────
    # 개별 기사 컨테이너: div.YWTMk0ahJUsxq4uCx9gX
    news_list = soup.select("div.YWTMk0ahJUsxq4uCx9gX")

    if news_list:
        for card in news_list:
            # articleView 링크 목록 (제목·설명 모두 같은 href 사용)
            article_links = [
                a for a in card.find_all("a", href=True)
                if "articleView" in a.get("href", "") or
                   ("n.news.naver.com" in a.get("href", ""))
            ]
            if len(article_links) < 1:
                continue

            title_tag = article_links[0]
            title     = title_tag.get_text(strip=True)
            link      = title_tag.get("href", "")

            desc = ""
            if len(article_links) >= 2:
                desc = article_links[1].get_text(strip=True)

            # 발행 시간: span.sds-comps-profile-info-subtext 중 시간 패턴 선택
            published = today
            _time_keywords = ("분 전", "시간 전", "일 전", "어제", "방금")
            for span in card.select("span.sds-comps-profile-info-subtext"):
                txt = span.get_text(strip=True)
                if any(k in txt for k in _time_keywords):
                    published = txt
                    break

            # UI 요소 제목 필터 (5자 미만 또는 알려진 UI 텍스트 제외)
            _UI_TITLES = {"네이버뉴스", "Keep에 저장", "뉴스", ""}
            if len(title) < 5 or title in _UI_TITLES:
                continue

            if title:
                items.append({
                    "date":        today,
                    "source":      "naver",
                    "query":       query,
                    "title":       title,
                    "description": desc,
                    "link":        link,
                    "published":   published,
                })
        return items

    # ── 구 UI fallback (li.bx + a.news_tit) ─────────────────────
    news_list_old = soup.select("ul.list_news > li.bx") or \
                    soup.select("div.news_wrap")
    for li in news_list_old:
        title_tag = li.select_one("a.news_tit")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        link  = title_tag.get("href", "")

        desc_tag = li.select_one("a.api_txt_lines.dsc_txt_wrap") or \
                   li.select_one(".dsc_txt_wrap") or \
                   li.select_one(".dsc_txt")
        desc = desc_tag.get_text(strip=True) if desc_tag else ""

        date_tag = li.select_one("span.info") or \
                   li.select_one(".info_group span.info")
        published = date_tag.get_text(strip=True) if date_tag else today

        items.append({
            "date":        today,
            "source":      "naver",
            "query":       query,
            "title":       title,
            "description": desc,
            "link":        link,
            "published":   published,
        })

    return items


def collect_naver_news(queries: List[str]) -> List[Dict]:
    """네이버 뉴스 검색에서 기사 수집 (페이지네이션 포함)."""
    articles: List[Dict] = []
    today = datetime.now().strftime("%Y-%m-%d")

    for query in queries:
        count = 0
        logger.info("[Naver] 쿼리: %s", query)

        for page in range(MAX_PAGES_PER_QUERY):
            start = page * 10 + 1
            url = NAVER_NEWS_URL.format(
                query=requests.utils.quote(query),
                start=start,
            )
            resp = _get(url)
            if resp is None:
                logger.warning("[Naver] 응답 없음 – 쿼리=%s, 페이지=%d", query, page + 1)
                break

            items = _parse_naver_page(resp.text, query, today)
            if not items:
                logger.debug("[Naver] 결과 없음 – 쿼리=%s, 페이지=%d", query, page + 1)
                break

            articles.extend(items)
            count += len(items)

            if count >= MAX_ARTICLES_PER_QUERY:
                break

            _sleep()

        logger.info("[Naver] %s → %d건 수집", query, count)
        _sleep()

    return articles


# ─────────────────────────────────────────────────────────────
# 공개 인터페이스
# ─────────────────────────────────────────────────────────────

def collect_all_news(queries: List[str]) -> List[Dict]:
    """네이버 + 구글 뉴스를 모두 수집하고 중복 제거 후 반환."""
    logger.info("=== 뉴스 수집 시작 ===")

    naver   = collect_naver_news(queries)
    google  = collect_google_news(queries)
    all_raw = naver + google

    # 제목 기준 중복 제거 (대소문자·공백 정규화)
    seen: set = set()
    deduped: List[Dict] = []
    for article in all_raw:
        key = article["title"].strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(article)

    logger.info(
        "=== 수집 완료: 네이버 %d건 + 구글 %d건 → 중복 제거 후 %d건 ===",
        len(naver), len(google), len(deduped),
    )
    return deduped
