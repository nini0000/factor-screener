"""
被套股票诊断工具
用户输入股票代码 + 买入价，系统给出持有/观望/止损建议
运行方式：streamlit run stock_diagnosis.py
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

# ── 页面配置 ───────────────────────────────────────────────────────────────────
st.set_page_config(page_title="股票诊断", layout="centered", page_icon="🩺")
st.title("🩺 被套了？帮你诊断要不要割")
st.caption("输入你的股票信息，从基本面、估值、市场情绪三个维度给出客观分析")

# ── 输入区 ─────────────────────────────────────────────────────────────────────
st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    ticker_input = st.text_input("股票代码", placeholder="如 AAPL / 600519.SS").strip().upper()
with col2:
    buy_price = st.number_input("买入价格", min_value=0.01, value=100.0, step=0.01)
with col3:
    currency = st.selectbox("货币", ["USD（美股）", "CNY（A股）"])

diagnose_btn = st.button("🔍 开始诊断", type="primary", use_container_width=True)

# ── 数据函数 ───────────────────────────────────────────────────────────────────
def get_stock_data(ticker):
    t = yf.Ticker(ticker)
    hist = t.history(period="1y")
    fast = dict(t.fast_info)
    fin  = t.financials
    bs   = t.balance_sheet
    return hist, fast, fin, bs

def get_news(ticker, company_name=""):
    query = f"{ticker} stock" if not company_name else f"{company_name} stock"
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
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

def compute_diagnosis(hist, fast, fin, bs, buy_price):
    """
    三维度诊断逻辑，返回各维度得分和综合结论
    得分：2=正面，1=中性，0=负面
    """
    result = {}
    current_price = fast.get("lastPrice", None)

    if current_price is None or len(hist) == 0:
        return None

    # ── 1. 收益计算 ────────────────────────────────────────────────────────────
    pnl_pct = (current_price - buy_price) / buy_price * 100
    result["current_price"] = current_price
    result["pnl_pct"]       = pnl_pct

    # ── 2. 估值维度：当前价 vs 52周区间 ───────────────────────────────────────
    year_high = fast.get("yearHigh", current_price)
    year_low  = fast.get("yearLow",  current_price)
    year_range = year_high - year_low
    if year_range > 0:
        position = (current_price - year_low) / year_range  # 0=最低，1=最高
    else:
        position = 0.5

    if position < 0.35:
        val_score, val_label, val_msg = 2, "🟢 偏低估", f"当前价格处于52周区间底部{position*100:.0f}%，相对便宜"
    elif position < 0.65:
        val_score, val_label, val_msg = 1, "🟡 合理区间", f"当前价格处于52周区间中段{position*100:.0f}%，估值适中"
    else:
        val_score, val_label, val_msg = 0, "🔴 偏高估", f"当前价格处于52周区间高位{position*100:.0f}%，估值偏高"

    result["valuation"] = {"score": val_score, "label": val_label, "msg": val_msg,
                            "year_high": year_high, "year_low": year_low, "position": position}

    # ── 3. 市场情绪维度：个股 vs 大盘 ─────────────────────────────────────────
    year_change = fast.get("yearChange", None)
    try:
        spy = yf.Ticker("SPY")
        spy_hist = spy.history(period="1y")
        if len(spy_hist) > 0:
            spy_change = (spy_hist["Close"].iloc[-1] - spy_hist["Close"].iloc[0]) / spy_hist["Close"].iloc[0]
        else:
            spy_change = None
    except Exception:
        spy_change = None

    if year_change is not None and spy_change is not None:
        diff = year_change - spy_change
        if diff > 0.05:
            mkt_score, mkt_label, mkt_msg = 2, "🟢 强于大盘", f"个股年涨幅{year_change*100:.1f}%，大盘{spy_change*100:.1f}%，跑赢大盘{diff*100:.1f}%"
        elif diff > -0.1:
            mkt_score, mkt_label, mkt_msg = 1, "🟡 跟随大盘", f"个股年涨幅{year_change*100:.1f}%，大盘{spy_change*100:.1f}%，基本同步"
        else:
            mkt_score, mkt_label, mkt_msg = 0, "🔴 弱于大盘", f"个股年涨幅{year_change*100:.1f}%，大盘{spy_change*100:.1f}%，显著跑输"
    else:
        mkt_score, mkt_label, mkt_msg = 1, "🟡 数据不足", "无法获取大盘对比数据"

    result["market"] = {"score": mkt_score, "label": mkt_label, "msg": mkt_msg}

    # ── 4. 基本面维度：收入趋势 ────────────────────────────────────────────────
    try:
        if not fin.empty and "Total Revenue" in fin.index:
            revenues = fin.loc["Total Revenue"].dropna().sort_index()
            if len(revenues) >= 2:
                rev_change = (revenues.iloc[-1] - revenues.iloc[-2]) / abs(revenues.iloc[-2])
                if rev_change > 0.05:
                    fun_score, fun_label, fun_msg = 2, "🟢 收入增长", f"最新年收入同比增长{rev_change*100:.1f}%，基本面向好"
                elif rev_change > -0.05:
                    fun_score, fun_label, fun_msg = 1, "🟡 收入平稳", f"最新年收入同比变化{rev_change*100:.1f}%，基本面稳定"
                else:
                    fun_score, fun_label, fun_msg = 0, "🔴 收入下滑", f"最新年收入同比下滑{rev_change*100:.1f}%，需要警惕"
            else:
                fun_score, fun_label, fun_msg = 1, "🟡 数据不足", "历史收入数据不足，无法判断趋势"
        else:
            fun_score, fun_label, fun_msg = 1, "🟡 数据不足", "无法获取财务数据"
    except Exception:
        fun_score, fun_label, fun_msg = 1, "🟡 数据不足", "财务数据获取失败"

    result["fundamental"] = {"score": fun_score, "label": fun_label, "msg": fun_msg}

    # ── 5. 综合结论 ────────────────────────────────────────────────────────────
    total = val_score + mkt_score + fun_score
    if total >= 5:
        verdict = ("🟢 建议持有", "三个维度均表现良好，下跌可能是短期波动，基本面支撑持有。")
    elif total >= 3:
        verdict = ("🟡 观望为主", "部分指标存在隐忧，建议密切关注后续财报和新闻，暂不加仓。")
    else:
        verdict = ("🔴 考虑止损", "多个维度出现负面信号，建议重新评估持仓逻辑，控制风险。")

    result["verdict"]    = verdict
    result["total_score"] = total

    # ── 6. 价格走势数据 ────────────────────────────────────────────────────────
    result["hist"] = hist

    return result

# ── 主逻辑 ─────────────────────────────────────────────────────────────────────
if diagnose_btn and ticker_input:
    with st.spinner(f"正在分析 {ticker_input}..."):
        try:
            hist, fast, fin, bs = get_stock_data(ticker_input)
            diag = compute_diagnosis(hist, fast, fin, bs, buy_price)

            if diag is None:
                st.error("无法获取股票数据，请检查代码是否正确（A股格式：600519.SS 或 000858.SZ）")
            else:
                # ── 顶部结论 ──────────────────────────────────────────────────
                st.divider()
                pnl = diag["pnl_pct"]
                pnl_color = "🟢" if pnl >= 0 else "🔴"
                current = diag["current_price"]

                col1, col2, col3 = st.columns(3)
                col1.metric("当前价格", f"{current:.2f}")
                col2.metric("买入价格", f"{buy_price:.2f}")
                col3.metric("浮动盈亏", f"{pnl:+.1f}%", delta=f"{pnl:+.1f}%")

                st.divider()

                # 综合结论大卡片
                verdict_label, verdict_msg = diag["verdict"]
                st.subheader(f"综合诊断：{verdict_label}")
                st.info(verdict_msg)

                # ── 三维度详情 ────────────────────────────────────────────────
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

                # ── 价格走势图 ────────────────────────────────────────────────
                st.divider()
                st.subheader("📈 近一年价格走势")
                hist_close = diag["hist"][["Close"]].copy()
                hist_close["买入价"] = buy_price
                st.line_chart(hist_close)

                # ── 近期新闻 ──────────────────────────────────────────────────
                st.divider()
                st.subheader("📰 近期相关新闻")
                st.caption("新闻是判断下跌原因的关键——是市场情绪还是实质利空？")

                news = get_news(ticker_input)
                if news:
                    for item in news:
                        st.markdown(f"- [{item['title']}]({item['link']}) `{item['date']}`")
                else:
                    st.info("暂时无法获取新闻，请手动搜索相关资讯")

                # ── 免责声明 ──────────────────────────────────────────────────
                st.divider()
                st.caption("⚠️ 本工具仅供学习研究，不构成投资建议。投资有风险，决策需谨慎。")

        except Exception as e:
            st.error(f"分析失败：{str(e)}\n请检查股票代码格式是否正确")

elif diagnose_btn and not ticker_input:
    st.warning("请输入股票代码")
