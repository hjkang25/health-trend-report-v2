#!/usr/bin/env python3
# =============================================================
# main.py  –  헬스 트렌드 수집 시스템 v2  실행 진입점
# =============================================================
# 실행 흐름:
#   1. 네이버 + 구글 뉴스 수집
#   2. Kiwi로 명사 키워드 자동 추출 → TOP 10
#   3. 뉴스 원문  →  data/news_YYYYMMDD.csv
#   4. TOP 10 키워드  →  data/keywords_YYYYMMDD.csv
#   5. 누적 트렌드  →  data/keyword_trend.csv (append)
# =============================================================

import csv
import io
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

import pandas as pd

from config import DATA_DIR, HEALTH_QUERIES, TOP_N
from collect_news import collect_all_news
from extract_keywords import extract_top_keywords

# ─────────────────────────────────────────────────────────────
# Windows UTF-8 콘솔 출력 설정
# ─────────────────────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─────────────────────────────────────────────────────────────
# 로깅 설정
# ─────────────────────────────────────────────────────────────
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    handlers=[_handler],
)
logger = logging.getLogger("main")


# ─────────────────────────────────────────────────────────────
# 저장 함수
# ─────────────────────────────────────────────────────────────

def save_news(articles: List[Dict], date_str: str, out_dir: Path) -> Path:
    """뉴스 원문 CSV 저장."""
    path = out_dir / f"news_{date_str}.csv"
    fieldnames = ["date", "source", "query", "title", "description", "link", "published"]

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(articles)

    logger.info("뉴스 저장 완료: %s (%d건)", path, len(articles))
    return path


def save_keywords(
    keywords: List[Tuple[str, int]],
    date_str: str,
    out_dir: Path,
) -> Path:
    """날짜별 TOP N 키워드 CSV 저장."""
    path = out_dir / f"keywords_{date_str}.csv"
    rows = [
        {"date": date_str, "rank": i + 1, "keyword": kw, "frequency": freq}
        for i, (kw, freq) in enumerate(keywords)
    ]

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "rank", "keyword", "frequency"])
        writer.writeheader()
        writer.writerows(rows)

    logger.info("키워드 저장 완료: %s (%d건)", path, len(rows))
    return path


def append_trend(
    keywords: List[Tuple[str, int]],
    date_str: str,
    out_dir: Path,
) -> Path:
    """누적 트렌드 CSV에 오늘 데이터 추가."""
    trend_path = out_dir / "keyword_trend.csv"
    new_rows = pd.DataFrame(
        [
            {"date": date_str, "rank": i + 1, "keyword": kw, "frequency": freq}
            for i, (kw, freq) in enumerate(keywords)
        ]
    )

    if trend_path.exists():
        existing = pd.read_csv(trend_path, encoding="utf-8-sig")
        # 같은 날짜가 이미 있으면 덮어쓰기 (재실행 방지)
        existing = existing[existing["date"] != date_str]
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        combined = new_rows

    combined.sort_values(["date", "rank"], inplace=True)
    combined.to_csv(trend_path, index=False, encoding="utf-8-sig")

    logger.info("트렌드 누적 저장 완료: %s (총 %d행)", trend_path, len(combined))
    return trend_path


# ─────────────────────────────────────────────────────────────
# 출력 요약
# ─────────────────────────────────────────────────────────────

def print_summary(keywords: List[Tuple[str, int]], date_str: str) -> None:
    """콘솔에 TOP 10 키워드 요약 출력."""
    print()
    print("=" * 45)
    print(f"  헬스 트렌드 TOP {TOP_N}  ({date_str})")
    print("=" * 45)
    for rank, (kw, freq) in enumerate(keywords, start=1):
        bar = "█" * min(freq, 40)
        print(f"  {rank:>2}위  {kw:<12}  {freq:>4}회  {bar}")
    print("=" * 45)
    print()


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

def main() -> None:
    date_str = datetime.now().strftime("%Y%m%d")
    out_dir  = Path(DATA_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[ 헬스 트렌드 수집 시스템 v2 시작 ] %s", date_str)

    # 1. 뉴스 수집
    articles = collect_all_news(HEALTH_QUERIES)
    if not articles:
        logger.error("수집된 기사가 없습니다. 프로세스를 종료합니다.")
        sys.exit(1)

    # 2. 키워드 추출
    keywords = extract_top_keywords(articles, top_n=TOP_N)
    if not keywords:
        logger.warning("추출된 키워드가 없습니다.")

    # 3–5. 저장
    save_news(articles, date_str, out_dir)
    save_keywords(keywords, date_str, out_dir)
    append_trend(keywords, date_str, out_dir)

    # 6. 콘솔 요약
    print_summary(keywords, date_str)

    logger.info("[ 완료 ]")


if __name__ == "__main__":
    main()
