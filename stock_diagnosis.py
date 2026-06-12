"""
被套股票诊断工具 v3
运行方式：streamlit run stock_diagnosis.py
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import urllib.request
import plotly.graph_objects as go
import xml.etree.ElementTree as ET
import anthropic
import os
from datetime import datetime, date, timedelta

# ── 页面配置 ───────────────────────────────────────────────────────────────────
st.set_page_config(page_title="股票诊断", layout="centered", page_icon="🩺")
st.title("🩺 股票诊断：要不要动？")
st.caption("输入你的持仓信息，从估值、市场情绪、基本面三个维度给出客观分析")

# ── 初始化 session_state ───────────────────────────────────────────────────────
for key in ["diag_result", "news", "ai_summary", "ticker_used",
            "buy_price_used", "buy_date_used", "prompt_answer", "selected_prompt"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ── 输入区 ─────────────────────────────────────────────────────────────────────
st.divider()
col1, col2 = st.columns(2)
with col1:
    ticker_input = st.text_input("股票代码", placeholder="如 AAPL / 600519.SS").strip().upper()
with col2:
    buy_price = st.number_input("买入价格", min_value=0.01, value=100.0, step=0.01)

col3, col4 = st.columns(2)
with col3:
    buy_date = st.date_input(
        "买入日期（今天之后不可选）",
        value=date.today() - timedelta(days=365),
        min_value=date(2000, 1, 1),
        max_value=date.today(),
        format="YYYY/MM/DD",
    )
with col4:
    currency = st.selectbox("货币", ["USD（美股）", "CNY（A股）"])

diagnose_btn = st.button("🔍 开始诊断", type="primary", use_container_width=True)

# ── 数据函数 ───────────────────────────────────────────────────────────────────
def get_stock_data(ticker, buy_date):
    t = yf.Ticker(ticker)
    # Always pull max history for full range chart options
    hist_full = t.history(period="max")
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

def ai_summarize_news(ticker, news_list, current_price, pnl_pct, is_profit):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not news_list:
        return None
    try:
        news_text = "\n".join([f"- {n['title']} ({n['date']})" for n in news_list])
        status = f"盈利{pnl_pct:.1f}%" if is_profit else f"亏损{abs(pnl_pct):.1f}%"
        prompt = f"""你是一个专业但友善的股票分析师，正在帮助一个普通散户理解他持有的股票。

股票代码：{ticker}
当前状态：{status}，当前价格 {current_price:.2f}

最近相关新闻：
{news_text}

请用简单易懂的中文回答，格式如下：

**{ticker} 最近怎么了？** [emoji]

**为啥在跌/涨？** [一两句话解释主要原因]

**是大环境还是公司自身？** [判断原因类型]

---
💬 **AI说一句：** [一句情绪安慰或提醒，语气像朋友]

语气要像朋友在跟你解释，不要太正式。最后不要给出买卖建议。"""

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except Exception:
        return None

def ask_ai(prompt_text):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "请设置API Key以启用此功能"
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt_text}]
        )
        # 提取文字回答（忽略tool_use块）
        answer = " ".join(
            block.text for block in response.content
            if hasattr(block, "text")
        )
        return answer.strip() or "暂时无法获取回答，请稍后再试"
    except Exception as e:
        return f"暂时无法获取回答：{str(e)}"

def compute_diagnosis(hist_full, hist_1y, fast, fin, bs, buy_price, buy_date):
    result = {}
    current_price = fast.get("lastPrice", None)
    if current_price is None or len(hist_full) == 0:
        return None

    pnl_pct   = (current_price - buy_price) / buy_price * 100
    is_profit = pnl_pct >= 0
    hold_days = (date.today() - buy_date).days

    result["current_price"] = current_price
    result["pnl_pct"]       = pnl_pct
    result["is_profit"]     = is_profit
    result["hold_days"]     = hold_days

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

    try:
        start_str = buy_date.strftime("%Y-%m-%d")
        hist_since = hist_full[hist_full.index.date >= buy_date] if len(hist_full) > 0 else pd.DataFrame()
        stock_since = (current_price - hist_since["Close"].iloc[0]) / hist_since["Close"].iloc[0] if len(hist_since) > 0 else pnl_pct / 100
        spy_hist = yf.Ticker("SPY").history(start=start_str)
        spy_since = (spy_hist["Close"].iloc[-1] - spy_hist["Close"].iloc[0]) / spy_hist["Close"].iloc[0] if len(spy_hist) > 0 else None
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

    try:
        if not fin.empty and "Total Revenue" in fin.index:
            revenues = fin.loc["Total Revenue"].dropna().sort_index()
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

    total = val_score + mkt_score + fun_score

    if is_profit:
        if total >= 5:
            verdict = ("🟢 可以继续持有", f"盈利{pnl_pct:.1f}%，三个维度均正面，基本面支撑，暂无止盈必要。")
        elif total >= 3:
            verdict = ("🟡 注意保护利润", f"盈利{pnl_pct:.1f}%，部分指标出现隐忧，可考虑设止盈位锁定部分收益。")
        else:
            verdict = ("🔴 考虑止盈离场", f"盈利{pnl_pct:.1f}%，多个维度走弱，估值偏高，建议落袋为安。")
    else:
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

    try:
        atr_df = hist_1y.tail(14).copy()
        atr_df["H-L"]  = atr_df["High"] - atr_df["Low"]
        atr_df["H-PC"] = abs(atr_df["High"]  - atr_df["Close"].shift(1))
        atr_df["L-PC"] = abs(atr_df["Low"]   - atr_df["Close"].shift(1))
        atr_df["TR"]   = atr_df[["H-L","H-PC","L-PC"]].max(axis=1)
        atr = atr_df["TR"].mean()
        stop_loss  = round(current_price - 2 * atr, 2)
        target     = round(current_price + 3 * atr, 2)
        result["atr"] = {
            "atr":             round(atr, 2),
            "stop_loss":       stop_loss,
            "target":          target,
            "stop_pct":        (stop_loss  - current_price) / current_price * 100,
            "target_pct":      (target     - current_price) / current_price * 100,
            "stop_from_buy":   (stop_loss  - buy_price) / buy_price * 100,
            "target_from_buy": (target     - buy_price) / buy_price * 100,
        }
    except Exception:
        result["atr"] = None

    return result

# ── 诊断逻辑（只在点诊断按钮时运行） ─────────────────────────────────────────
if diagnose_btn and ticker_input:
    with st.spinner(f"正在分析 {ticker_input}..."):
        try:
            hist_full, hist_1y, fast, fin, bs = get_stock_data(ticker_input, buy_date)
            diag = compute_diagnosis(hist_full, hist_1y, fast, fin, bs, buy_price, buy_date)
            if diag is None:
                st.error("无法获取股票数据，请检查代码格式")
            else:
                news = get_news(ticker_input)
                ai_sum = ai_summarize_news(ticker_input, news,
                                           diag["current_price"], diag["pnl_pct"], diag["is_profit"])
                # 存入session_state
                st.session_state.diag_result    = diag
                st.session_state.news           = news
                st.session_state.ai_summary     = ai_sum
                st.session_state.ticker_used    = ticker_input
                st.session_state.buy_price_used = buy_price
                st.session_state.buy_date_used  = buy_date
                st.session_state.prompt_answer  = None
                st.session_state.selected_prompt = None
        except Exception as e:
            st.error(f"分析失败：{str(e)}")

# ── 展示（从session_state读取，不受按钮影响） ──────────────────────────────────
if st.session_state.diag_result:
    diag      = st.session_state.diag_result
    news      = st.session_state.news
    ticker    = st.session_state.ticker_used
    buy_price = st.session_state.buy_price_used
    buy_date  = st.session_state.buy_date_used
    pnl       = diag["pnl_pct"]
    current   = diag["current_price"]
    is_profit = diag["is_profit"]
    hold_days = diag["hold_days"]

    # 顶部指标
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("当前价格", f"{current:.2f}")
    c2.metric("买入价格", f"{buy_price:.2f}")
    c3.metric("浮动盈亏", f"{pnl:+.1f}%", delta=f"{pnl:+.1f}%")
    c4.metric("持有天数", f"{hold_days} 天")

    st.divider()

    # 综合结论
    verdict_label, verdict_msg = diag["verdict"]
    st.subheader(f"综合诊断：{verdict_label}")
    if is_profit:
        st.success(verdict_msg)
    elif diag["total_score"] >= 3:
        st.warning(verdict_msg)
    else:
        st.error(verdict_msg)

    # 三维度
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

    # ATR
    st.divider()
    st.subheader("🎯 止损位 & 目标价（基于ATR波动率）")
    st.caption("根据过去14天平均真实波动幅度计算，超出正常波动范围的参考价位")
    if diag["atr"]:
        atr_data = diag["atr"]
        ca, cb, cc = st.columns(3)
        ca.metric("🛑 止损位", f"{atr_data['stop_loss']:.2f}",
                  f"{atr_data['stop_pct']:+.1f}% 当前  /  {atr_data['stop_from_buy']:+.1f}% 买入",
                  delta_color="inverse")
        cb.metric("📍 当前价", f"{current:.2f}", f"ATR = {atr_data['atr']:.2f}")
        cc.metric("🎯 目标价", f"{atr_data['target']:.2f}",
                  f"{atr_data['target_pct']:+.1f}% 当前  /  {atr_data['target_from_buy']:+.1f}% 买入")
        st.caption("风险回报比 1 : 1.5 ｜ 止损 = 当前价 − 2×ATR，目标 = 当前价 + 3×ATR")

    # K线图
    st.divider()
    st.subheader(f"📈 价格走势")
    hist_all = diag["hist_full"].copy()

    if not hist_all.empty:
        # 计算Fibonacci（基于全部历史）
        hi   = hist_all["High"].max()
        lo   = hist_all["Low"].min()
        diff = hi - lo
        fib_levels = {
            "0%":   lo,
            "23.6%": lo + 0.236 * diff,
            "38.2%": lo + 0.382 * diff,
            "50.0%": lo + 0.500 * diff,
            "61.8%": lo + 0.618 * diff,
            "100%":  hi,
        }

        fig = go.Figure()

        # K线
        fig.add_trace(go.Candlestick(
            x=hist_all.index,
            open=hist_all["Open"], high=hist_all["High"],
            low=hist_all["Low"],   close=hist_all["Close"],
            name="K线",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
            showlegend=True,
        ))

        # 买入日标记（竖线 + 点）
        buy_dt = pd.Timestamp(buy_date)
        nearest = hist_all.index[hist_all.index.date >= buy_date]
        if len(nearest) > 0:
            buy_dt = nearest[0]
            buy_close = hist_all.loc[buy_dt, "Close"]
            fig.add_trace(go.Scatter(
                x=[buy_dt], y=[buy_price],
                mode="markers+text",
                marker=dict(size=12, color="#2196F3", symbol="diamond",
                            line=dict(color="white", width=2)),
                text=["买入"],
                textposition="top center",
                textfont=dict(color="#2196F3", size=12),
                name=f"买入价 {buy_price:.2f}",
                showlegend=True,
            ))
            # 买入价水平线（只从买入日到今天）
            fig.add_shape(type="line",
                x0=buy_dt, x1=hist_all.index[-1],
                y0=buy_price, y1=buy_price,
                line=dict(color="#2196F3", width=1.5, dash="dot"),
            )

        # 止损区间（红色填充带）
        if diag["atr"]:
            sl = diag["atr"]["stop_loss"]
            tp = diag["atr"]["target"]

            # 止损区（当前价到止损位，红色半透明）
            fig.add_hrect(y0=sl, y1=current,
                          fillcolor="rgba(244,67,54,0.08)",
                          line_width=0, layer="below")
            # 盈利区（当前价到目标价，绿色半透明）
            fig.add_hrect(y0=current, y1=tp,
                          fillcolor="rgba(76,175,80,0.08)",
                          line_width=0, layer="below")

            # 止损线
            fig.add_hline(y=sl,
                          line=dict(color="#f44336", width=2, dash="dash"),
                          annotation_text=f"🛑 止损位  {sl:.2f}  ({diag['atr']['stop_pct']:+.1f}%)",
                          annotation_position="bottom right",
                          annotation_font=dict(color="#f44336", size=12))
            # 目标线
            fig.add_hline(y=tp,
                          line=dict(color="#4caf50", width=2, dash="dash"),
                          annotation_text=f"🎯 目标价  {tp:.2f}  ({diag['atr']['target_pct']:+.1f}%)",
                          annotation_position="top right",
                          annotation_font=dict(color="#4caf50", size=12))
            # 当前价线
            fig.add_hline(y=current,
                          line=dict(color="#FFD700", width=1.5, dash="dot"),
                          annotation_text=f"当前  {current:.2f}",
                          annotation_position="right",
                          annotation_font=dict(color="#FFD700", size=11))

        # Fibonacci线
        fib_colors = {
            "0%":"#555","23.6%":"#7986cb","38.2%":"#4fc3f7",
            "50.0%":"#ce93d8","61.8%":"#4fc3f7","100%":"#555"
        }
        for label, level in fib_levels.items():
            fig.add_hline(y=level,
                          line=dict(color=fib_colors[label], width=0.8, dash="dot"),
                          annotation_text=f"Fib {label}",
                          annotation_position="left",
                          annotation_font=dict(color=fib_colors[label], size=10))

        # 全局range锁定
        x_min_all = str(hist_all.index[0].date())
        x_max_all = str(hist_all.index[-1].date())

        fig.update_layout(
            xaxis=dict(
                fixedrange=False,
                rangeslider=dict(visible=False),
                minallowed=x_min_all,
                maxallowed=x_max_all,
                rangeselector=dict(
                    bgcolor="#1e1e2e",
                    activecolor="#3a3a5c",
                    bordercolor="#444",
                    buttons=[
                        dict(count=1,  label="1D",  step="day",   stepmode="backward"),
                        dict(count=5,  label="5D",  step="day",   stepmode="backward"),
                        dict(count=1,  label="1M",  step="month", stepmode="backward"),
                        dict(count=3,  label="3M",  step="month", stepmode="backward"),
                        dict(count=1,  label="1Y",  step="year",  stepmode="backward"),
                        dict(count=3,  label="3Y",  step="year",  stepmode="backward"),
                        dict(step="all", label="全部"),
                    ]
                ),
            ),
            yaxis=dict(fixedrange=False, side="right",
                       showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            height=560,
            plot_bgcolor="#0d0d1a",
            paper_bgcolor="#0f0f23",
            font_color="#cccccc",
            showlegend=True,
            legend=dict(orientation="h", y=-0.12, x=0,
                        bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
            margin=dict(l=10, r=100, t=40, b=40),
            dragmode="zoom",
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("暂时无法获取价格数据")

    # 新闻
    st.divider()
    st.subheader("📰 近期相关新闻")
    st.caption("判断下跌是市场情绪还是实质利空的关键")
    if news:
        for item in news:
            st.markdown(f"- [{item['title']}]({item['link']}) `{item['date']}`")
    else:
        st.info("暂时无法获取新闻，请手动搜索相关资讯")

    # AI新闻总结
    st.divider()
    st.subheader("🤖 AI 解读：最近为什么涨跌？")
    if st.session_state.ai_summary:
        with st.container(height=250):
            st.markdown(st.session_state.ai_summary)
    else:
        st.info("暂时无法生成AI分析")

    # 快速提问按钮
    st.divider()
    st.subheader("💬 还想了解什么？")
    st.caption("点击下方问题，AI直接为你解答")

    prompts = {
        "📊 这只股票的主要风险是什么？": f"请搜索{ticker}股票最新的主要投资风险，用简单中文100字以内总结，语气像朋友解释，不要给买卖建议。",
        "📈 分析师对这只股票怎么看？":   f"请搜索{ticker}股票最新的分析师评级和观点，用简单中文100字以内总结，语气像朋友解释。",
        "🧠 用简单语言解释它的商业模式": f"请搜索{ticker}这家公司的商业模式，用简单中文100字以内解释它怎么赚钱，面向完全不懂的散户。",
        "💡 同行业还有哪些值得关注的股票？": f"请搜索和{ticker}同行业的美股，列出3只值得关注的，每只一句话说明原因，用简单中文，不要给投资建议。",
    }

    cols = st.columns(2)
    for i, (label, prompt_text) in enumerate(prompts.items()):
        with cols[i % 2]:
            if st.button(label, key=f"prompt_{i}", use_container_width=True):
                st.session_state.selected_prompt = label
                with st.spinner("AI思考中..."):
                    st.session_state.prompt_answer = ask_ai(prompt_text)

    if st.session_state.selected_prompt and st.session_state.prompt_answer:
        st.markdown(f"**{st.session_state.selected_prompt}**")
        with st.container(height=300):
            st.markdown(st.session_state.prompt_answer)

    st.divider()
    st.caption("⚠️ 本工具仅供学习研究，不构成投资建议。投资有风险，决策需谨慎。")

elif diagnose_btn and not ticker_input:
    st.warning("请输入股票代码")
