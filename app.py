from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
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


@st.cache_data(ttl=900, show_spinner=False)
def intraday_history(symbol: str) -> pd.DataFrame:
    df = yf.download(symbol, period="5d", interval="5m", auto_adjust=True,
                     progress=False, threads=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])


def estimate_intraday_pressure(df: pd.DataFrame) -> pd.DataFrame:
    """Classify each 5-minute bar by price direction; this is a proxy, not tick-side data."""
    if df.empty:
        return pd.DataFrame()
    bars = df.copy()
    direction = np.sign(bars["Close"] - bars["Open"])
    direction = direction.replace(0, np.nan).ffill().fillna(0)
    bars["date"] = pd.to_datetime(bars.index).date
    bars["buy_est"] = bars["Volume"].where(direction > 0, 0)
    bars["sell_est"] = bars["Volume"].where(direction < 0, 0)
    bars["neutral"] = bars["Volume"].where(direction == 0, 0)
    daily = bars.groupby("date")[["buy_est", "sell_est", "neutral", "Volume"]].sum()
    daily.columns = ["估算偏買量(股)", "估算偏賣量(股)", "中性量(股)", "總成交量(股)"]
    return daily.sort_index(ascending=False)


def _to_float(value) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


@st.cache_data(ttl=3600, show_spinner=False)
def latest_institutional_flow(symbol: str) -> dict | None:
    code = symbol.split(".")[0]
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        if symbol.endswith(".TWO"):
            url = "https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading"
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            rows = response.json()
            row = next((x for x in rows if str(x.get("SecuritiesCompanyCode", "")).strip() == code), None)
            if not row:
                return None
            foreign = _to_float(row.get("Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Difference"))
            trust = _to_float(row.get("SecuritiesInvestmentTrustCompanies-Difference"))
            dealer = _to_float(row.get("Dealers-Difference"))
            date = str(row.get("Date", ""))
        else:
            today = pd.Timestamp.now(tz="Asia/Taipei").date()
            row = None
            date = ""
            for offset in range(8):
                target = today - pd.Timedelta(days=offset)
                params = {"date": target.strftime("%Y%m%d"), "selectType": "ALLBUT0999", "response": "json"}
                response = requests.get("https://www.twse.com.tw/rwd/zh/fund/T86", params=params,
                                        headers=headers, timeout=12)
                response.raise_for_status()
                payload = response.json()
                fields = payload.get("fields", [])
                rows = payload.get("data", [])
                code_index = next((i for i, name in enumerate(fields) if "證券代號" in name), 0)
                row = next((x for x in rows if str(x[code_index]).strip() == code), None)
                if row:
                    date = target.strftime("%Y-%m-%d")
                    break
            if not row:
                return None
            def field_value(text):
                index = next((i for i, name in enumerate(fields) if text in name), None)
                return _to_float(row[index]) if index is not None and index < len(row) else 0.0
            foreign = field_value("外陸資買賣超股數(不含外資自營商)")
            trust = field_value("投信買賣超股數")
            dealer = field_value("自營商買賣超股數(自行買賣)") + field_value("自營商買賣超股數(避險)")
        return {
            "date": date,
            "foreign_lots": foreign / 1000,
            "trust_lots": trust / 1000,
            "dealer_lots": dealer / 1000,
            "source": "櫃買中心 OpenAPI" if symbol.endswith(".TWO") else "證交所 T86",
        }
    except Exception:
        return None


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
    for n in (5, 10, 20, 60, 120):
        d[f"MA{n}"] = close.rolling(n).mean()
    middle = close.rolling(20).mean()
    deviation = close.rolling(20).std(ddof=0)
    d["BB_Mid"] = middle
    d["BB_Upper"] = middle + 2 * deviation
    d["BB_Lower"] = middle - 2 * deviation
    d["VolMA20"] = d["Volume"].rolling(20).mean()
    d = add_candlestick_patterns(d)
    return d


def add_candlestick_patterns(d: pd.DataFrame) -> pd.DataFrame:
    """Rule-based daily candlestick patterns; signals are descriptive, not forecasts."""
    d = d.copy()
    o, h, l, c = (d[k].astype(float) for k in ("Open", "High", "Low", "Close"))
    body = (c - o).abs()
    span = (h - l).replace(0, np.nan)
    upper = h - pd.concat([o, c], axis=1).max(axis=1)
    lower = pd.concat([o, c], axis=1).min(axis=1) - l
    small = body <= span * .30
    doji = body <= span * .10
    prev_o, prev_c = o.shift(1), c.shift(1)
    prev_body = (prev_c - prev_o).abs()
    downtrend = c < c.rolling(10, min_periods=5).mean()
    uptrend = c > c.rolling(10, min_periods=5).mean()
    signals = {
        "鎚子線": downtrend & small & (lower >= body * 2) & (upper <= body),
        "倒鎚子線": downtrend & small & (upper >= body * 2) & (lower <= body),
        "流星線": uptrend & small & (upper >= body * 2) & (lower <= body),
        "十字線": doji,
        "多頭吞噬": (prev_c < prev_o) & (c > o) & (o <= prev_c) & (c >= prev_o),
        "空頭吞噬": (prev_c > prev_o) & (c < o) & (o >= prev_c) & (c <= prev_o),
        "多頭母子": (prev_c < prev_o) & (c > o) & (o >= prev_c) & (c <= prev_o),
        "空頭母子": (prev_c > prev_o) & (c < o) & (o <= prev_c) & (c >= prev_o),
        "貫穿線": (prev_c < prev_o) & (c > o) & (o < prev_c) & (c > (prev_o + prev_c) / 2) & (c < prev_o),
        "烏雲罩頂": (prev_c > prev_o) & (c < o) & (o > prev_c) & (c < (prev_o + prev_c) / 2) & (c > prev_o),
    }
    o2, c2, o3, c3 = o.shift(2), c.shift(2), o.shift(0), c.shift(0)
    middle_small = (c.shift(1) - o.shift(1)).abs() <= (h.shift(1) - l.shift(1)) * .35
    signals["晨星"] = (c2 < o2) & (prev_body > (h.shift(2) - l.shift(2)) * .5) & middle_small & (c > o) & (body > span * .5) & (c > (o2 + c2) / 2)
    signals["夜星"] = (c2 > o2) & (prev_body > (h.shift(2) - l.shift(2)) * .5) & middle_small & (c < o) & (body > span * .5) & (c < (o2 + c2) / 2)
    for name, condition in signals.items():
        d[f"PAT_{name}"] = condition.fillna(False)
    return d


PATTERN_COLUMNS = ["鎚子線", "倒鎚子線", "流星線", "十字線", "多頭吞噬", "空頭吞噬", "多頭母子", "空頭母子", "貫穿線", "烏雲罩頂", "晨星", "夜星"]


def active_patterns(row: pd.Series) -> list[str]:
    return [name for name in PATTERN_COLUMNS if bool(row.get(f"PAT_{name}", False))]


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

tabs = st.tabs(["個股圖表", "大盤比較", "基本面與消息", "籌碼觀察", "觀察清單掃描"])
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
    fig.add_trace(go.Scatter(x=df.index, y=df.BB_Upper, name="布林上軌", line={"color": "#94a3b8", "width": 1, "dash": "dot"}), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df.BB_Lower, name="布林下軌", line={"color": "#94a3b8", "width": 1, "dash": "dot"}, fill="tonexty", fillcolor="rgba(148,163,184,0.10)"), row=1, col=1)
    bullish_cols = [f"PAT_{x}" for x in ("鎚子線", "倒鎚子線", "多頭吞噬", "多頭母子", "貫穿線", "晨星")]
    bearish_cols = [f"PAT_{x}" for x in ("流星線", "空頭吞噬", "空頭母子", "烏雲罩頂", "夜星")]
    bullish_hits = df[bullish_cols].any(axis=1)
    bearish_hits = df[bearish_cols].any(axis=1)
    if bullish_hits.any():
        fig.add_trace(go.Scatter(x=df.index[bullish_hits], y=df.Low[bullish_hits] * .99, mode="markers", name="偏多 K 線型態", marker={"symbol": "triangle-up", "size": 10, "color": "#16a34a"}, hovertemplate="%{x|%Y-%m-%d}<br>偏多 K 線型態<extra></extra>"), row=1, col=1)
    if bearish_hits.any():
        fig.add_trace(go.Scatter(x=df.index[bearish_hits], y=df.High[bearish_hits] * 1.01, mode="markers", name="偏空 K 線型態", marker={"symbol": "triangle-down", "size": 10, "color": "#dc2626"}, hovertemplate="%{x|%Y-%m-%d}<br>偏空 K 線型態<extra></extra>"), row=1, col=1)
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
    daily_trace_index = next((i for i, trace in enumerate(fig.data) if trace.name == "每日行情"), -1)
    candle_point = next((p for p in reversed(selected_points) if p.get("curve_number") == daily_trace_index), None)
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
    recent_patterns = [(idx.strftime("%Y-%m-%d"), active_patterns(row)) for idx, row in df.tail(20).iterrows() if active_patterns(row)]
    st.markdown("**近 20 個交易日 K 線型態**")
    if recent_patterns:
        pattern_rows = [{"日期": day, "型態": "、".join(names)} for day, names in recent_patterns]
        st.dataframe(pd.DataFrame(pattern_rows), hide_index=True, use_container_width=True)
    else:
        st.caption("近 20 個交易日沒有符合目前型態規則的訊號。")
    st.caption("型態依 OHLC 規則辨識，部分型態需結合趨勢背景；缺口型態未納入（台股除權息與漲跌幅限制會影響判讀）。型態只描述歷史形狀，不代表後續走勢。")
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
    st.subheader("三大法人買賣超")
    flow = latest_institutional_flow(symbol)
    if flow:
        f1, f2, f3 = st.columns(3)
        f1.metric("外資買賣超", f"{flow['foreign_lots']:+,.0f} 張")
        f2.metric("投信買賣超", f"{flow['trust_lots']:+,.0f} 張")
        f3.metric("自營商買賣超", f"{flow['dealer_lots']:+,.0f} 張")
        st.caption(f"資料日期：{flow['date']}｜來源：{flow['source']}｜股數換算張數")
    else:
        st.info("目前無法取得這檔股票的法人資料；資料來源沒有回傳時不以估算值替代。")

    st.divider()
    st.subheader("5 分鐘 K 線估算買賣壓力")
    st.caption("用每根 5 分鐘 K 線的漲跌方向分配該根成交量。這是價格方向代理值，並非逐筆成交的實際外盤／內盤分類。")
    pressure_key = f"pressure_{symbol}"
    if st.button("載入近 5 個交易日估算", key=f"load_pressure_{symbol}"):
        intraday = intraday_history(symbol)
        st.session_state[pressure_key] = estimate_intraday_pressure(intraday)
    pressure = st.session_state.get(pressure_key)
    if isinstance(pressure, pd.DataFrame) and not pressure.empty:
        pressure_lots = pressure / 1000
        pressure_lots.index = pressure_lots.index.map(str)
        pressure_lots = pressure_lots.rename(columns={
            "估算偏買量(股)": "估算偏買量(張)",
            "估算偏賣量(股)": "估算偏賣量(張)",
            "中性量(股)": "中性量(張)",
            "總成交量(股)": "總成交量(張)",
        })
        st.bar_chart(pressure_lots[["估算偏買量(張)", "估算偏賣量(張)"]], use_container_width=True)
        st.dataframe(pressure_lots.round(1), use_container_width=True)
        st.caption("資料來源：Yahoo Finance 5 分鐘 K 線；實際成交方向可能與此估算不同。")
    elif pressure is not None:
        st.info("資料來源目前沒有提供可用的 5 分鐘行情。")
    else:
        st.info("按上方按鈕載入估算資料。資料受 Yahoo Finance 可用區間與更新狀態限制。")

with tabs[4]:
    st.subheader("盤後選股雷達")
    st.markdown("輸入一組股票代號，依技術訊號和最新三大法人買賣超篩選。所選條件採全部符合（AND）；資料以收盤後可取得的最新日資料為準。")
    watch = st.text_area("掃描清單（上市 .TW、上櫃 .TWO，以逗號或換行分隔）", DEFAULT_WATCHLIST, height=90)
    technical_options = [
        "收盤站上 MA20", "MA5 高於 MA20", "MACD 柱為正", "MACD 柱較前日增加",
        "RSI 介於 50–70", "KD 黃金交叉", "收盤站上布林中軌", "成交量大於 20 日均量 1.5 倍",
        "突破前 20 日高點",
    ]
    pattern_options = [f"K線：{name}" for name in PATTERN_COLUMNS]
    technical_options += pattern_options
    selected_technical = st.multiselect("技術條件", technical_options, default=["收盤站上 MA20", "MACD 柱為正"])
    chip_options = ["外資買超", "投信買超", "自營商買超", "三大法人合計買超"]
    selected_chips = st.multiselect("籌碼條件（最新交易日）", chip_options)
    min_avg_volume = st.number_input("最低 20 日均量（張）", min_value=0, max_value=100000, value=100, step=100)
    if st.button("執行盤後選股", type="primary"):
        symbols = list(dict.fromkeys(x.strip().upper() for x in watch.replace("\n", ",").split(",") if x.strip()))
        results = []
        bar = st.progress(0)
        for i, item in enumerate(symbols):
            try:
                data = history(item, "1y", "1d")
                if len(data) >= 61:
                    calc = indicators(data)
                    cur, prev = calc.iloc[-1], calc.iloc[-2]
                    avg_volume_lots = float(cur.VolMA20) / 1000 if pd.notna(cur.VolMA20) else 0
                    if avg_volume_lots < min_avg_volume:
                        bar.progress((i + 1) / len(symbols))
                        continue
                    prior_20_high = calc.High.shift(1).rolling(20).max().iloc[-1]
                    tech_check = {
                        "收盤站上 MA20": cur.Close > cur.MA20,
                        "MA5 高於 MA20": cur.MA5 > cur.MA20,
                        "MACD 柱為正": cur.Hist > 0,
                        "MACD 柱較前日增加": cur.Hist > prev.Hist,
                        "RSI 介於 50–70": 50 <= cur.RSI14 <= 70,
                        "KD 黃金交叉": cur.K > cur.D and prev.K <= prev.D,
                        "收盤站上布林中軌": cur.Close > cur.BB_Mid,
                        "成交量大於 20 日均量 1.5 倍": cur.Volume > cur.VolMA20 * 1.5,
                        "突破前 20 日高點": cur.Close > prior_20_high,
                    }
                    tech_check.update({f"K線：{name}": bool(cur.get(f"PAT_{name}", False)) for name in PATTERN_COLUMNS})
                    flow = latest_institutional_flow(item) if selected_chips else None
                    chip_check = {
                        "外資買超": bool(flow and flow["foreign_lots"] > 0),
                        "投信買超": bool(flow and flow["trust_lots"] > 0),
                        "自營商買超": bool(flow and flow["dealer_lots"] > 0),
                        "三大法人合計買超": bool(flow and (flow["foreign_lots"] + flow["trust_lots"] + flow["dealer_lots"]) > 0),
                    }
                    chosen = selected_technical + selected_chips
                    checks = {**tech_check, **chip_check}
                    if all(checks[name] for name in chosen):
                        hit_reasons = [name for name in chosen if checks[name]]
                        total_flow = (flow["foreign_lots"] + flow["trust_lots"] + flow["dealer_lots"]) if flow else np.nan
                        results.append({
                            "代號": item, "資料日期": calc.index[-1].strftime("%Y-%m-%d"),
                            "收盤": round(float(cur.Close), 2), "日變動%": round(pct_return(calc.Close, 1), 2),
                            "20日均量(張)": round(avg_volume_lots), "RSI14": round(float(cur.RSI14), 1),
                            "外資買超(張)": round(flow["foreign_lots"]) if flow else np.nan,
                            "投信買超(張)": round(flow["trust_lots"]) if flow else np.nan,
                            "自營商買超(張)": round(flow["dealer_lots"]) if flow else np.nan,
                            "法人合計(張)": round(total_flow) if pd.notna(total_flow) else np.nan,
                            "符合條件": "、".join(hit_reasons), "訊號數": len(hit_reasons),
                        })
            except Exception:
                pass
            bar.progress((i + 1) / len(symbols))
        if results:
            result_df = pd.DataFrame(results).sort_values(["訊號數", "法人合計(張)", "日變動%"], ascending=[False, False, False], na_position="last")
            st.success(f"找到 {len(result_df)} 檔符合所選條件的候選股。點選代號可帶入上方個股分析。")
            st.dataframe(result_df, hide_index=True, use_container_width=True)
        else:
            st.warning("沒有候選股符合條件，或行情／法人資料暫時無法取得。可調整條件後重新掃描。")

st.divider()
st.caption("研究工具，不構成投資建議。行情、公司欄位及新聞依資料供應商狀態可能延遲、缺漏或修正。")

