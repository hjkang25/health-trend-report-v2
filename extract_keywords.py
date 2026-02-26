# =============================================================
# extract_keywords.py  –  Kiwi 형태소 분석 기반 키워드 추출
# =============================================================

import logging
from collections import Counter
from typing import List, Dict, Tuple

from kiwipiepy import Kiwi

from stopwords import STOPWORDS
from config import TOP_N, MIN_FREQ, MIN_KEYWORD_LEN

logger = logging.getLogger(__name__)

# Kiwi 인스턴스 (모듈 로드 시 1회 초기화)
_kiwi = Kiwi()

# 추출 대상 품사 태그
# NNG: 일반명사  NNP: 고유명사
_TARGET_TAGS = {"NNG", "NNP"}


# ─────────────────────────────────────────────────────────────
# 핵심 함수
# ─────────────────────────────────────────────────────────────

def _is_valid_token(form: str, tag: str) -> bool:
    """토큰이 키워드로 유효한지 검사."""
    if tag not in _TARGET_TAGS:
        return False
    if len(form) < MIN_KEYWORD_LEN:
        return False
    if form in STOPWORDS:
        return False
    # 숫자만으로 이뤄진 토큰 제거
    if form.isdigit():
        return False
    # 영문 단일 문자 제거 (A, B, C …)
    if len(form) == 1 and form.isalpha():
        return False
    return True


def extract_nouns(text: str) -> List[str]:
    """텍스트에서 유효 명사 리스트 반환."""
    if not text or not isinstance(text, str):
        return []
    try:
        tokens = _kiwi.tokenize(text)
        return [t.form for t in tokens if _is_valid_token(t.form, t.tag)]
    except Exception as e:
        logger.warning("Kiwi 분석 오류: %s", e)
        return []


def extract_top_keywords(
    articles: List[Dict],
    top_n: int = TOP_N,
    min_freq: int = MIN_FREQ,
) -> List[Tuple[str, int]]:
    """
    기사 목록에서 키워드 TOP N 추출.

    Parameters
    ----------
    articles : 각 기사가 dict (title, description 필드 포함)
    top_n    : 반환할 키워드 수
    min_freq : 최소 등장 빈도

    Returns
    -------
    [(키워드, 빈도), ...]  — 빈도 내림차순
    """
    all_nouns: List[str] = []

    for article in articles:
        # 제목 + 본문 요약 합산 분석
        combined = " ".join([
            article.get("title", ""),
            article.get("description", ""),
        ])
        all_nouns.extend(extract_nouns(combined))

    counter = Counter(all_nouns)

    # 최소 빈도 필터
    filtered = [(kw, freq) for kw, freq in counter.most_common() if freq >= min_freq]

    logger.info(
        "키워드 추출 완료: 전체 %d개 → 빈도 필터 후 %d개 → TOP %d 반환",
        len(counter), len(filtered), min(top_n, len(filtered)),
    )

    return filtered[:top_n]
