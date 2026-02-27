# =============================================================
# dashboard.py  –  헬스 트렌드 대시보드 v2
# =============================================================
# 실행: streamlit run dashboard.py
# =============================================================

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ─────────────────────────────────────────────────────────────
# 페이지 설정 (가장 먼저 호출)
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Health Trend Dashboard V2",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path(__file__).parent / "data"

# ─────────────────────────────────────────────────────────────
# 데이터 로드 유틸
# ─────────────────────────────────────────────────────────────

@st.cache_data
def load_trend(mtime: float = 0.0) -> pd.DataFrame:
    """keyword_trend.csv 전체 로드. mtime이 바뀌면 캐시 자동 무효화."""
    path = DATA_DIR / "keyword_trend.csv"
    if not path.exists():
        return pd.DataFrame(columns=["date", "rank", "keyword", "frequency"])
    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"date": str})
    return df


@st.cache_data
def load_news(date_str: str) -> pd.DataFrame:
    """news_YYYYMMDD.csv 로드."""
    path = DATA_DIR / f"news_{date_str}.csv"
    if not path.exists():
        return pd.DataFrame(columns=["date", "source", "query", "title", "description", "link", "published"])
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    return df.fillna("")


def get_available_dates() -> list[str]:
    """data/ 폴더의 news_*.csv 기준으로 날짜 목록(최신순) 반환."""
    return sorted(
        [p.stem.replace("news_", "") for p in DATA_DIR.glob("news_*.csv")],
        reverse=True,
    )


def fmt_date(d: str) -> str:
    """'20260226' → '2026-02-26'"""
    return f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else d


# ─────────────────────────────────────────────────────────────
# 날짜 유효성 검사
# ─────────────────────────────────────────────────────────────
available_dates = get_available_dates()

if not available_dates:
    st.error("❌ data/ 폴더에 CSV 파일이 없습니다. `main.py`를 먼저 실행해 데이터를 수집하세요.")
    st.stop()

# ─────────────────────────────────────────────────────────────
# 사이드바 — 날짜 선택
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏥 Health Trend")
    st.caption("Health Trend Dashboard v2")
    st.divider()

    selected_date = st.selectbox(
        "📅 날짜 선택",
        options=available_dates,
        format_func=fmt_date,
    )

    st.divider()
    st.caption("**데이터 경로**")
    st.code(str(DATA_DIR), language=None)

# ─────────────────────────────────────────────────────────────
# 데이터 로드
# ─────────────────────────────────────────────────────────────
_trend_path = DATA_DIR / "keyword_trend.csv"
_trend_mtime = _trend_path.stat().st_mtime if _trend_path.exists() else 0.0

trend_df = load_trend(_trend_mtime)
news_df  = load_news(selected_date)

today_kw = (
    trend_df[trend_df["date"] == selected_date]
    .sort_values(["rank", "frequency"], ascending=[True, False])
    .drop_duplicates(subset="rank", keep="first")
    .head(10)
    .reset_index(drop=True)
)

# ─────────────────────────────────────────────────────────────
# 헤더 + 요약 지표
# ─────────────────────────────────────────────────────────────
st.title("🏥 Health Trend Dashboard v2")
st.caption(f"기준일: **{fmt_date(selected_date)}**  |  데이터 수집: 네이버 뉴스 + 구글 뉴스")

m1, m2, m3, m4 = st.columns(4)
m1.metric("📰 수집 기사", f"{len(news_df):,} 건")
m2.metric("🔑 TOP 키워드", today_kw.iloc[0]["keyword"] if not today_kw.empty else "-")
m3.metric("📊 TOP 언급수", f"{int(today_kw.iloc[0]['frequency']):,} 회" if not today_kw.empty else "-")
m4.metric("🗓️ 누적 분석일", f"{trend_df['date'].nunique()} 일")

st.divider()

# ─────────────────────────────────────────────────────────────
# 탭
# ─────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 TOP 10 키워드", "📈 순위 변화 추이", "📰 뉴스 목록"])


# ── Tab 1 : TOP 10 막대 차트 ─────────────────────────────────
with tab1:
    st.subheader(f"헬스 키워드 TOP 10 — {fmt_date(selected_date)}")

    if today_kw.empty:
        st.info("선택한 날짜의 키워드 데이터가 없습니다.")
    else:
        df_bar = today_kw.sort_values("frequency", ascending=True).copy()
        df_bar["rank_label"] = df_bar["rank"].astype(str) + "위"

        fig_bar = px.bar(
            df_bar,
            x="frequency",
            y="keyword",
            orientation="h",
            text="frequency",
            color="frequency",
            color_continuous_scale=["#93c5fd", "#1d4ed8"],
            custom_data=["rank_label"],
            labels={"frequency": "언급 횟수", "keyword": "키워드"},
        )
        fig_bar.update_traces(
            textposition="outside",
            textfont_size=13,
            hovertemplate="<b>%{y}</b>  %{customdata[0]}<br>언급 횟수: %{x:,} 회<extra></extra>",
        )
        fig_bar.update_layout(
            height=460,
            margin=dict(l=10, r=70, t=10, b=10),
            coloraxis_showscale=False,
            yaxis_title=None,
            xaxis_title="언급 횟수",
            yaxis=dict(tickfont=dict(size=14)),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        with st.expander("📋 표로 보기"):
            tbl = today_kw[["rank", "keyword", "frequency"]].rename(
                columns={"rank": "순위", "keyword": "키워드", "frequency": "언급 횟수"}
            )
            st.dataframe(tbl, use_container_width=True, hide_index=True)


# ── Tab 2 : 순위 변화 라인 차트 ──────────────────────────────
with tab2:
    st.subheader("날짜별 키워드 순위 변화")

    if trend_df["date"].nunique() < 2:
        st.info("순위 변화 추이를 보려면 **최소 2일** 이상의 데이터가 필요합니다.\n\n`main.py`를 다른 날짜에도 실행하면 자동으로 누적됩니다.")
    else:
        # 빈도 합산 기준으로 키워드 정렬
        all_kws = (
            trend_df.groupby("keyword")["frequency"].sum()
            .sort_values(ascending=False)
            .index.tolist()
        )

        col_sel, col_opt = st.columns([3, 1])
        with col_sel:
            selected_kws = st.multiselect(
                "키워드 선택 (최대 10개)",
                options=all_kws,
                default=all_kws[:min(10, len(all_kws))],
                max_selections=10,
            )
        with col_opt:
            show_freq = st.checkbox("언급 횟수도 보기", value=False)

        if not selected_kws:
            st.warning("키워드를 1개 이상 선택하세요.")
        else:
            df_line = trend_df[trend_df["keyword"].isin(selected_kws)].copy()
            df_line["date_label"] = df_line["date"].apply(fmt_date)
            df_line = df_line.sort_values("date_label")

            # 순위 차트 (Y축 반전: 1위가 위)
            fig_rank = px.line(
                df_line,
                x="date_label",
                y="rank",
                color="keyword",
                markers=True,
                text="rank",
                labels={"date_label": "날짜", "rank": "순위", "keyword": "키워드"},
            )
            fig_rank.update_traces(
                textposition="top center",
                textfont_size=11,
                line=dict(width=2.5),
                marker=dict(size=8),
            )
            fig_rank.update_yaxes(
                autorange="reversed",
                dtick=1,
                title="순위 (1위 = 상단)",
                range=[today_kw["rank"].max() + 0.5, 0.5],
            )
            fig_rank.update_xaxes(title=None)
            fig_rank.update_layout(
                height=460,
                margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                ),
            )
            st.plotly_chart(fig_rank, use_container_width=True)

            # 언급 횟수 추이 (옵션)
            if show_freq:
                st.subheader("언급 횟수 변화")
                fig_freq = px.line(
                    df_line,
                    x="date_label",
                    y="frequency",
                    color="keyword",
                    markers=True,
                    text="frequency",
                    labels={"date_label": "날짜", "frequency": "언급 횟수", "keyword": "키워드"},
                )
                fig_freq.update_traces(
                    textposition="top center",
                    textfont_size=11,
                    line=dict(width=2.5),
                    marker=dict(size=8),
                )
                fig_freq.update_layout(
                    height=400,
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_freq, use_container_width=True)


# ── Tab 3 : 뉴스 목록 ────────────────────────────────────────
with tab3:
    st.subheader(f"수집 뉴스 — {fmt_date(selected_date)}")

    if news_df.empty:
        st.info("선택한 날짜의 뉴스 데이터가 없습니다.")
    else:
        # 필터 행
        col_src, col_q, col_qry = st.columns([1, 2, 1])

        sources = ["전체"] + sorted(news_df["source"].unique().tolist())
        sel_src = col_src.selectbox("출처", sources, key="src_filter")

        queries = ["전체"] + sorted(news_df["query"].unique().tolist())
        sel_qry = col_qry.selectbox("쿼리", queries, key="qry_filter")

        search_q = col_q.text_input("🔍 제목 검색", placeholder="키워드 입력…")

        # 필터 적용
        filtered = news_df.copy()
        if sel_src != "전체":
            filtered = filtered[filtered["source"] == sel_src]
        if sel_qry != "전체":
            filtered = filtered[filtered["query"] == sel_qry]
        if search_q:
            filtered = filtered[
                filtered["title"].str.contains(search_q, case=False, na=False)
            ]

        st.caption(f"전체 {len(news_df):,}건 중 **{len(filtered):,}건** 표시")

        # 소스 한글 변환 + 표시용 데이터프레임
        source_map = {"naver": "🟢 네이버", "google": "🔵 구글"}
        display = filtered[["source", "title", "link", "query", "published", "description"]].copy()
        display["source"] = display["source"].map(source_map).fillna(display["source"])
        display = display.rename(columns={
            "source":      "출처",
            "title":       "제목",
            "link":        "링크",
            "query":       "검색어",
            "published":   "발행",
            "description": "요약",
        })

        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            height=600,
            column_config={
                "제목": st.column_config.TextColumn("제목", width="large"),
                "링크": st.column_config.LinkColumn("링크", display_text="열기", width="small"),
                "출처": st.column_config.TextColumn("출처", width="small"),
                "검색어": st.column_config.TextColumn("검색어", width="small"),
                "발행": st.column_config.TextColumn("발행", width="small"),
                "요약": st.column_config.TextColumn("요약", width="medium"),
            },
            column_order=["출처", "제목", "링크", "검색어", "발행", "요약"],
        )
