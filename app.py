from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots


st.set_page_config(page_title="台股研究室", page_icon="📈", layout="wide")
st.title("📈 台股研究室")
st.caption("台股盤後觀察・大盤比較・技術與基本面整理｜資料僅供研究參考")

DEFAULT_WATCHLIST = "2330.TW, 2317.TW, 2454.TW, 2308.TW, 2881.TW, 2603.TW"
INDEXES = {"加權指數": "^TWII", "櫃買指數": "^TWOII"}


@st.cache_data(ttl=1800, show_spinner=False)
def history(symbol: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=True,
                     progress=False, threads=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Close"])


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    close = d["Close"]
    change = close.diff()
    gain = change.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    loss = -change.clip(upper=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    d["RSI14"] = 100 - 100 / (1 + rs)
    e12, e26 = close.ewm(span=12, adjust=False).mean(), close.ewm(span=26, adjust=False).mean()
    d["MACD"] = e12 - e26
    d["Signal"] = d["MACD"].ewm(span=9, adjust=False).mean()
    d["Hist"] = d["MACD"] - d["Signal"]
    low, high = d["Low"].rolling(9).min(), d["High"].rolling(9).max()
    rsv = (close - low) / (high - low).replace(0, np.nan) * 100
    d["K"] = rsv.ewm(com=2, adjust=False).mean()
    d["D"] = d["K"].ewm(com=2, adjust=False).mean()
    for n in (5, 20, 60, 120):
        d[f"MA{n}"] = close.rolling(n).mean()
    d["VolMA20"] = d["Volume"].rolling(20).mean()
    return d


def pct_return(series: pd.Series, days: int) -> float:
    s = series.dropna()
    if len(s) <= days:
        return float("nan")
    return float((s.iloc[-1] / s.iloc[-days-1] - 1) * 100)


@st.cache_data(ttl=1800, show_spinner=False)
def company_info(symbol: str) -> dict:
    try:
        return yf.Ticker(symbol).info or {}
    except Exception:
        return {}


@st.cache_data(ttl=1800, show_spinner=False)
def headlines(symbol: str) -> list[dict]:
    try:
        news = yf.Ticker(symbol).news or []
        items = []
        for item in news[:8]:
            content = item.get("content", item)
            title = content.get("title", "")
            link = content.get("clickThroughUrl", {}) or content.get("canonicalUrl", {})
            url = link.get("url", "") if isinstance(link, dict) else ""
            provider = content.get("provider", {})
            publisher = provider.get("displayName", "新聞來源") if isinstance(provider, dict) else "新聞來源"
            if title:
                items.append({"title": title, "url": url, "publisher": publisher})
        return items
    except Exception:
        return []


def fmt(value, digits=2, suffix=""):
    try:
        if pd.isna(value):
            return "—"
        return f"{float(value):,.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "—"


with st.sidebar:
    st.header("分析設定")
    symbol = st.text_input("股票代號", "2330.TW", help="上市使用 .TW，上櫃使用 .TWO，例如 6488.TWO").strip().upper()
    period_label = st.selectbox("歷史區間", ["6 個月", "1 年", "2 年", "5 年"], index=2)
    period = {"6 個月": "6mo", "1 年": "1y", "2 年": "2y", "5 年": "5y"}[period_label]
    interval_label = st.selectbox("K 線週期", ["日線", "週線", "月線"])
    interval = {"日線": "1d", "週線": "1wk", "月線": "1mo"}[interval_label]
    st.caption("價格使用 Yahoo Finance 調整後歷史資料；非即時報價。")

if not symbol:
    st.info("請輸入股票代號開始分析。")
    st.stop()

with st.spinner(f"載入 {symbol} 與大盤資料…"):
    raw = history(symbol, period, interval)
    market = {name: history(code, period, interval) for name, code in INDEXES.items()}

if raw.empty:
    st.error(f"無法取得 {symbol} 的歷史資料。請確認代號格式，或稍後重試。")
    st.stop()

df = indicators(raw)
last = df.iloc[-1]
prior = df.iloc[-2] if len(df) > 1 else last
info = company_info(symbol)
name = info.get("longName") or info.get("shortName") or symbol
date = df.index[-1].strftime("%Y-%m-%d")
change_pct = (float(last.Close) / float(prior.Close) - 1) * 100 if prior.Close else np.nan

st.subheader(f"{name}　{symbol}")
st.caption(f"最後資料日期：{date}｜資料來源：Yahoo Finance｜畫面時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("收盤價", fmt(last.Close), f"{change_pct:+.2f}%" if pd.notna(change_pct) else None)
c2.metric("成交量", f"{float(last.Volume)/1000:,.0f} 張" if pd.notna(last.Volume) else "—")
c3.metric("RSI (14)", fmt(last.RSI14))
c4.metric("MACD 柱", fmt(last.Hist))
c5.metric("20 日均量", f"{float(last.VolMA20)/1000:,.0f} 張" if pd.notna(last.VolMA20) else "—")

tabs = st.tabs(["個股圖表", "大盤比較", "基本面與消息", "觀察清單掃描"])
with tabs[0]:
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=.035,
                        row_heights=[.52, .16, .16, .16], subplot_titles=("股價與均線", "成交量", "MACD", "RSI / KD"))
    fig.add_trace(go.Candlestick(x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close, name="K 線"), row=1, col=1)
    candle_data = np.column_stack((df.Open, df.High, df.Low, df.Close, df.Volume / 1000))
    fig.add_trace(go.Scatter(
        x=df.index, y=df.Close, mode="markers", name="每日行情",
        marker={"size": 14, "opacity": .01, "color": "#111827"},
        customdata=candle_data, showlegend=False,
        hovertemplate=(
            "日期：%{x|%Y-%m-%d}<br>開盤：%{customdata[0]:.2f}"
            "<br>最高：%{customdata[1]:.2f}<br>最低：%{customdata[2]:.2f}"
            "<br>收盤：%{customdata[3]:.2f}<br>成交量：%{customdata[4]:,.0f} 張"
            "<extra></extra>"
        ),
    ), row=1, col=1)
    for n, color in ((20, "orange"), (60, "royalblue"), (120, "purple")):
        fig.add_trace(go.Scatter(x=df.index, y=df[f"MA{n}"], name=f"MA{n}", line={"color": color, "width": 1}), row=1, col=1)
    colors = np.where(df.Close >= df.Open, "#d94a4a", "#159570")
    fig.add_trace(go.Bar(x=df.index, y=df.Volume, name="成交量", marker_color=colors), row=2, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df.Hist, name="MACD 柱"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df.MACD, name="MACD"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df.Signal, name="Signal"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df.RSI14, name="RSI14"), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df.K, name="K"), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df.D, name="D"), row=4, col=1)
    fig.update_layout(height=850, xaxis_rangeslider_visible=False, margin={"l": 10, "r": 10, "t": 50, "b": 10}, legend={"orientation": "h"})
    chart_event = st.plotly_chart(
        fig, use_container_width=True, key=f"price_chart_{symbol}_{interval}",
        on_select="rerun", selection_mode="points",
    )
    selected_points = chart_event.selection.points
    candle_point = next((p for p in reversed(selected_points) if p.get("curve_number") == 1), None)
    if candle_point is not None:
        point_index = candle_point.get("point_index", candle_point.get("point_number"))
        if point_index is not None and 0 <= point_index < len(df):
            selected_bar = df.iloc[point_index]
            st.markdown(f"#### 選取日期：{df.index[point_index].strftime('%Y-%m-%d')}")
            detail_cols = st.columns(5)
            detail_cols[0].metric("開盤", fmt(selected_bar.Open))
            detail_cols[1].metric("最高", fmt(selected_bar.High))
            detail_cols[2].metric("最低", fmt(selected_bar.Low))
            detail_cols[3].metric("收盤", fmt(selected_bar.Close))
            detail_cols[4].metric("成交量", f"{float(selected_bar.Volume)/1000:,.0f} 張")
    else:
        st.caption("將滑鼠移到 K 線可查看該日價格與成交量；點選 K 線可固定顯示該日資料。")
    st.markdown("**技術觀察**")
    notes = []
    if pd.notna(last.MA20):
        notes.append("收盤價在 20 日均線之上" if last.Close > last.MA20 else "收盤價在 20 日均線之下")
    if pd.notna(last.MA60):
        notes.append("收盤價在 60 日均線之上" if last.Close > last.MA60 else "收盤價在 60 日均線之下")
    if pd.notna(last.RSI14):
        notes.append("RSI 偏高（>70）" if last.RSI14 > 70 else "RSI 偏低（<30）" if last.RSI14 < 30 else "RSI 未進入常用極端區")
    st.write("；".join(notes) if notes else "資料不足以計算指標。")
    st.caption("指標是歷史價格的數學整理，不代表未來方向或買賣建議。")

with tabs[1]:
    st.markdown("以相同起始日 = 100 比較個股與指數；市場指數資料可能不完整或延遲。")
    base = df.Close.dropna()
    rel = pd.DataFrame({name: base / base.iloc[0] * 100})
    for market_name, mdf in market.items():
        if not mdf.empty:
            aligned = mdf.Close.reindex(rel.index).ffill().dropna()
            if len(aligned):
                rel[market_name] = aligned / aligned.iloc[0] * 100
    st.line_chart(rel, height=400)
    rows = []
    for label, series in [(name, df.Close)] + [(n, d.Close) for n, d in market.items() if not d.empty]:
        rows.append({"標的": label, "近 1 個月": fmt(pct_return(series, 21), suffix="%"), "近 3 個月": fmt(pct_return(series, 63), suffix="%"), "近 1 年": fmt(pct_return(series, 252), suffix="%")})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

with tabs[2]:
    st.subheader("公司資料與估值概況")
    fundamentals = [
        ("產業", info.get("industry")), ("市值", info.get("marketCap")),
        ("本益比（TTM）", info.get("trailingPE")), ("股價淨值比", info.get("priceToBook")),
        ("股利殖利率", info.get("dividendYield")), ("每股盈餘（TTM）", info.get("trailingEps")),
        ("營收成長率", info.get("revenueGrowth")), ("毛利率", info.get("grossMargins")),
    ]
    fcols = st.columns(4)
    for i, (label, value) in enumerate(fundamentals):
        if isinstance(value, (int, float)) and label in ("股利殖利率", "營收成長率", "毛利率"):
            shown = fmt(value * 100, suffix="%")
        elif isinstance(value, (int, float)) and label == "市值":
            shown = f"{value/1e8:,.1f} 億"
        else:
            shown = fmt(value) if isinstance(value, (int, float)) else (str(value) if value else "無資料")
        fcols[i % 4].metric(label, shown)
    st.caption("基本面欄位由 Yahoo Finance 提供，涵蓋與更新情況依標的而異；無資料會顯示『無資料』。")
    st.subheader("近期新聞")
    news = headlines(symbol)
    if news:
        for item in news:
            title = item["title"]
            st.markdown(f"- [{title}]({item['url']}) · {item['publisher']}" if item["url"] else f"- {title} · {item['publisher']}")
    else:
        st.info("目前沒有可用新聞資料。")

with tabs[3]:
    st.markdown("輸入逗號分隔的代號，快速比較均線、動能與區間報酬。大量掃描建議分批執行，避免資料來源限流。")
    watch = st.text_area("觀察清單", DEFAULT_WATCHLIST, height=90)
    if st.button("掃描觀察清單", type="primary"):
        symbols = list(dict.fromkeys(x.strip().upper() for x in watch.replace("\n", ",").split(",") if x.strip()))
        results = []
        bar = st.progress(0)
        for i, item in enumerate(symbols):
            try:
                data = history(item, "1y", "1d")
                if len(data) >= 60:
                    calc = indicators(data)
                    cur = calc.iloc[-1]
                    results.append({"代號": item, "資料日期": calc.index[-1].strftime("%Y-%m-%d"), "收盤": round(float(cur.Close), 2), "日變動%": round(pct_return(calc.Close, 1), 2), "月報酬%": round(pct_return(calc.Close, 21), 2), "RSI14": round(float(cur.RSI14), 1) if pd.notna(cur.RSI14) else np.nan, "MA20上方": bool(cur.Close > cur.MA20) if pd.notna(cur.MA20) else False, "MA60上方": bool(cur.Close > cur.MA60) if pd.notna(cur.MA60) else False})
            except Exception:
                pass
            bar.progress((i + 1) / len(symbols))
        if results:
            st.dataframe(pd.DataFrame(results).sort_values("月報酬%", ascending=False), hide_index=True, use_container_width=True)
        else:
            st.warning("沒有取得可用資料，請確認代號或稍後再試。")

st.divider()
st.caption("研究工具，不構成投資建議。行情、公司欄位及新聞依資料供應商狀態可能延遲、缺漏或修正。")

