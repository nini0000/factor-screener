"""
被套股票诊断工具 v2
运行方式：streamlit run stock_diagnosis.py
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta

# ── 页面配置 ───────────────────────────────────────────────────────────────────
st.set_page_config(page_title="股票诊断", layout="centered", page_icon="🩺")
st.title("🩺 股票诊断：要不要动？")
st.caption("输入你的持仓信息，从估值、市场情绪、基本面三个维度给出客观分析")

# ── 输入区 ─────────────────────────────────────────────────────────────────────
st.divider()
col1, col2 = st.columns(2)
with col1:
    ticker_input = st.text_input("股票代码", placeholder="如 AAPL / 600519.SS").strip().upper()
with col2:
    buy_price = st.number_input("买入价格", min_value=0.01, value=100.0, step=0.01)

col3, col4 = st.columns(2)
with col3:
    buy_date = st.date_input("买入日期", value=date.today() - timedelta(days=180),
                              max_value=date.today())
with col4:
    currency = st.selectbox("货币", ["USD（美股）", "CNY（A股）"])

diagnose_btn = st.button("🔍 开始诊断", type="primary", use_container_width=True)

# ── 数据函数 ───────────────────────────────────────────────────────────────────
def get_stock_data(ticker, buy_date):
    t = yf.Ticker(ticker)
    # 从买入日期往前多拉30天，确保图表有完整数据
    start = (buy_date - timedelta(days=30)).strftime("%Y-%m-%d")
    hist_full = t.history(start=start)
    hist_1y   = t.history(period="1y")
    fast = dict(t.fast_info)
    fin  = t.financials
    bs   = t.balance_sheet
    return hist_full, hist_1y, fast, fin, bs

def get_news(ticker):
    url = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
    try:
        req  = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=8)
        tree = ET.parse(resp)
        root = tree.getroot()
        items = root.findall(".//item")
        news = []
        for item in items[:6]:
            title = item.findtext("title", "")
            pub   = item.findtext("pubDate", "")
            link  = item.findtext("link", "")
            news.append({"title": title, "date": pub[:16], "link": link})
        return news
    except Exception:
        return []

def compute_diagnosis(hist_full, hist_1y, fast, fin, bs, buy_price, buy_date):
    result = {}
    current_price = fast.get("lastPrice", None)
    if current_price is None or len(hist_full) == 0:
        return None

    # ── 1. 盈亏计算 ────────────────────────────────────────────────────────────
    pnl_pct   = (current_price - buy_price) / buy_price * 100
    is_profit = pnl_pct >= 0
    hold_days = (date.today() - buy_date).days

    result["current_price"] = current_price
    result["pnl_pct"]       = pnl_pct
    result["is_profit"]     = is_profit
    result["hold_days"]     = hold_days

    # ── 2. 估值维度 ────────────────────────────────────────────────────────────
    year_high  = fast.get("yearHigh", current_price)
    year_low   = fast.get("yearLow",  current_price)
    year_range = year_high - year_low
    position   = (current_price - year_low) / year_range if year_range > 0 else 0.5

    if position < 0.35:
        val_score, val_label, val_msg = 2, "🟢 偏低估", f"当前价处于52周区间底部{position*100:.0f}%，相对便宜"
    elif position < 0.65:
        val_score, val_label, val_msg = 1, "🟡 合理区间", f"当前价处于52周区间中段{position*100:.0f}%，估值适中"
    else:
        val_score, val_label, val_msg = 0, "🔴 偏高估", f"当前价处于52周区间高位{position*100:.0f}%，估值偏高"

    result["valuation"] = {"score": val_score, "label": val_label, "msg": val_msg}

    # ── 3. 市场情绪维度：从买入日期起对比大盘 ────────────────────────────────
    try:
        start_str = buy_date.strftime("%Y-%m-%d")
        # 个股从买入日起的涨幅
        hist_since = hist_full[hist_full.index.date >= buy_date] if len(hist_full) > 0 else pd.DataFrame()
        if len(hist_since) > 0:
            stock_since = (current_price - hist_since["Close"].iloc[0]) / hist_since["Close"].iloc[0]
        else:
            stock_since = pnl_pct / 100

        # 大盘同期涨幅
        spy      = yf.Ticker("SPY")
        spy_hist = spy.history(start=start_str)
        if len(spy_hist) > 0:
            spy_since = (spy_hist["Close"].iloc[-1] - spy_hist["Close"].iloc[0]) / spy_hist["Close"].iloc[0]
        else:
            spy_since = None
    except Exception:
        spy_since = None
        stock_since = pnl_pct / 100

    if spy_since is not None:
        diff = stock_since - spy_since
        if diff > 0.05:
            mkt_score, mkt_label, mkt_msg = 2, "🟢 强于大盘", f"买入以来个股{stock_since*100:+.1f}%，大盘{spy_since*100:+.1f}%，跑赢{diff*100:.1f}%"
        elif diff > -0.1:
            mkt_score, mkt_label, mkt_msg = 1, "🟡 跟随大盘", f"买入以来个股{stock_since*100:+.1f}%，大盘{spy_since*100:+.1f}%，基本同步"
        else:
            mkt_score, mkt_label, mkt_msg = 0, "🔴 弱于大盘", f"买入以来个股{stock_since*100:+.1f}%，大盘{spy_since*100:+.1f}%，显著跑输"
    else:
        mkt_score, mkt_label, mkt_msg = 1, "🟡 数据不足", "无法获取大盘对比数据"

    result["market"] = {"score": mkt_score, "label": mkt_label, "msg": mkt_msg}

    # ── 4. 基本面维度 ──────────────────────────────────────────────────────────
    try:
        if not fin.empty and "Total Revenue" in fin.index:
            revenues  = fin.loc["Total Revenue"].dropna().sort_index()
            if len(revenues) >= 2:
                rev_change = (revenues.iloc[-1] - revenues.iloc[-2]) / abs(revenues.iloc[-2])
                if rev_change > 0.05:
                    fun_score, fun_label, fun_msg = 2, "🟢 收入增长", f"最新年收入同比+{rev_change*100:.1f}%，基本面向好"
                elif rev_change > -0.05:
                    fun_score, fun_label, fun_msg = 1, "🟡 收入平稳", f"最新年收入同比{rev_change*100:+.1f}%，基本面稳定"
                else:
                    fun_score, fun_label, fun_msg = 0, "🔴 收入下滑", f"最新年收入同比{rev_change*100:.1f}%，需要警惕"
            else:
                fun_score, fun_label, fun_msg = 1, "🟡 数据不足", "历史收入数据不足"
        else:
            fun_score, fun_label, fun_msg = 1, "🟡 数据不足", "无法获取财务数据"
    except Exception:
        fun_score, fun_label, fun_msg = 1, "🟡 数据不足", "财务数据获取失败"

    result["fundamental"] = {"score": fun_score, "label": fun_label, "msg": fun_msg}

    # ── 5. 综合结论（盈亏分开话术） ───────────────────────────────────────────
    total = val_score + mkt_score + fun_score

    if is_profit:
        # 盈利状态 → 判断要不要止盈
        if total >= 5:
            verdict = ("🟢 可以继续持有", f"盈利{pnl_pct:.1f}%，三个维度均正面，基本面支撑，暂无止盈必要。")
        elif total >= 3:
            verdict = ("🟡 注意保护利润", f"盈利{pnl_pct:.1f}%，部分指标出现隐忧，可考虑设止盈位锁定部分收益。")
        else:
            verdict = ("🔴 考虑止盈离场", f"盈利{pnl_pct:.1f}%，多个维度走弱，估值偏高，建议落袋为安。")
    else:
        # 亏损状态 → 根据持有时间和指标判断
        if hold_days < 90:
            time_note = "持有时间较短，可能只是短期波动。"
        elif hold_days < 365:
            time_note = "持有约半年以上，需关注是否是趋势性下跌。"
        else:
            time_note = "持有超过一年，需重新审视当初买入逻辑是否仍然成立。"

        if total >= 5:
            verdict = ("🟢 建议继续持有", f"亏损{abs(pnl_pct):.1f}%，但基本面和估值均正面。{time_note}下跌可能是市场情绪，可考虑持有或加仓。")
        elif total >= 3:
            verdict = ("🟡 观望，暂不加仓", f"亏损{abs(pnl_pct):.1f}%，部分指标存在隐忧。{time_note}建议密切关注后续财报和新闻。")
        else:
            verdict = ("🔴 建议考虑止损", f"亏损{abs(pnl_pct):.1f}%，多个维度负面。{time_note}建议重新评估持仓逻辑，控制风险。")

    result["verdict"]     = verdict
    result["total_score"] = total
    result["hist_full"]   = hist_full

    return result

# ── 主逻辑 ─────────────────────────────────────────────────────────────────────
if diagnose_btn and ticker_input:
    with st.spinner(f"正在分析 {ticker_input}..."):
        try:
            hist_full, hist_1y, fast, fin, bs = get_stock_data(ticker_input, buy_date)
            diag = compute_diagnosis(hist_full, hist_1y, fast, fin, bs, buy_price, buy_date)

            if diag is None:
                st.error("无法获取股票数据，请检查代码是否正确（A股格式：600519.SS 或 000858.SZ）")
            else:
                pnl     = diag["pnl_pct"]
                current = diag["current_price"]
                is_profit = diag["is_profit"]
                hold_days = diag["hold_days"]

                # ── 顶部指标 ──────────────────────────────────────────────────
                st.divider()
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("当前价格", f"{current:.2f}")
                c2.metric("买入价格", f"{buy_price:.2f}")
                c3.metric("浮动盈亏", f"{pnl:+.1f}%", delta=f"{pnl:+.1f}%")
                c4.metric("持有天数", f"{hold_days} 天")

                st.divider()

                # ── 综合结论 ──────────────────────────────────────────────────
                verdict_label, verdict_msg = diag["verdict"]
                st.subheader(f"综合诊断：{verdict_label}")
                if is_profit:
                    st.success(verdict_msg)
                elif diag["total_score"] >= 3:
                    st.warning(verdict_msg)
                else:
                    st.error(verdict_msg)

                # ── 三维度 ────────────────────────────────────────────────────
                st.subheader("📊 三维度分析")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**估值位置**")
                    st.markdown(diag["valuation"]["label"])
                    st.caption(diag["valuation"]["msg"])
                with c2:
                    st.markdown("**市场情绪**")
                    st.markdown(diag["market"]["label"])
                    st.caption(diag["market"]["msg"])
                with c3:
                    st.markdown("**基本面**")
                    st.markdown(diag["fundamental"]["label"])
                    st.caption(diag["fundamental"]["msg"])

                # ── 价格走势图（从买入日期开始） ──────────────────────────────
                st.divider()
                st.subheader(f"📈 价格走势（从买入日 {buy_date} 起）")
                hist_plot = diag["hist_full"][["Close"]].copy()
                hist_plot = hist_plot[hist_plot.index.date >= buy_date]
                hist_plot["买入价"] = buy_price
                if not hist_plot.empty:
                    st.line_chart(hist_plot)
                else:
                    st.info("无法获取买入日期后的价格数据")

                # ── 近期新闻 ──────────────────────────────────────────────────
                st.divider()
                st.subheader("📰 近期相关新闻")
                st.caption("判断下跌是市场情绪还是实质利空的关键")
                news = get_news(ticker_input)
                if news:
                    for item in news:
                        st.markdown(f"- [{item['title']}]({item['link']}) `{item['date']}`")
                else:
                    st.info("暂时无法获取新闻，请手动搜索相关资讯")

                st.divider()
                st.caption("⚠️ 本工具仅供学习研究，不构成投资建议。投资有风险，决策需谨慎。")

        except Exception as e:
            st.error(f"分析失败：{str(e)}\n请检查股票代码格式是否正确")

elif diagnose_btn and not ticker_input:
    st.warning("请输入股票代码")
