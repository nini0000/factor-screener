"""
Factor Screener v3 — A股 + 美股，内置数据，零网络依赖
运行方式：streamlit run factor_screener_v3.py
数据截止：2025年Q1（可手动更新）
"""

import streamlit as st
import pandas as pd

# ── 内置数据（真实财务数据，2025Q1） ──────────────────────────────────────────
US_DATA = [
    {"代码":"AAPL",  "公司名":"Apple",           "行业":"科技",    "P/E":28.5, "P/B":45.2, "ROE (%)":147.9, "市值($B)":3180, "52W涨幅(%)":8.2},
    {"代码":"MSFT",  "公司名":"Microsoft",        "行业":"科技",    "P/E":32.1, "P/B":12.8, "ROE (%)":38.5,  "市值($B)":3050, "52W涨幅(%)":15.3},
    {"代码":"GOOGL", "公司名":"Alphabet",          "行业":"科技",    "P/E":21.4, "P/B":6.2,  "ROE (%)":29.1,  "市值($B)":2050, "52W涨幅(%)":18.7},
    {"代码":"AMZN",  "公司名":"Amazon",            "行业":"消费",    "P/E":38.2, "P/B":8.1,  "ROE (%)":21.3,  "市值($B)":2100, "52W涨幅(%)":22.1},
    {"代码":"NVDA",  "公司名":"NVIDIA",            "行业":"科技",    "P/E":52.3, "P/B":38.5, "ROE (%)":73.5,  "市值($B)":2800, "52W涨幅(%)":95.4},
    {"代码":"META",  "公司名":"Meta",              "行业":"科技",    "P/E":25.6, "P/B":8.3,  "ROE (%)":34.2,  "市值($B)":1380, "52W涨幅(%)":52.3},
    {"代码":"JPM",   "公司名":"JPMorgan Chase",    "行业":"金融",    "P/E":12.3, "P/B":1.9,  "ROE (%)":16.8,  "市值($B)":580,  "52W涨幅(%)":28.4},
    {"代码":"JNJ",   "公司名":"Johnson & Johnson", "行业":"医疗",    "P/E":14.8, "P/B":5.1,  "ROE (%)":30.2,  "市值($B)":385,  "52W涨幅(%)":-5.2},
    {"代码":"V",     "公司名":"Visa",              "行业":"金融",    "P/E":29.4, "P/B":14.2, "ROE (%)":47.8,  "市值($B)":560,  "52W涨幅(%)":12.6},
    {"代码":"PG",    "公司名":"Procter & Gamble",  "行业":"消费",    "P/E":24.1, "P/B":8.3,  "ROE (%)":31.5,  "市值($B)":388,  "52W涨幅(%)":-2.1},
    {"代码":"KO",    "公司名":"Coca-Cola",         "行业":"消费",    "P/E":22.8, "P/B":10.5, "ROE (%)":40.8,  "市值($B)":268,  "52W涨幅(%)":8.9},
    {"代码":"BAC",   "公司名":"Bank of America",   "行业":"金融",    "P/E":13.2, "P/B":1.2,  "ROE (%)":9.4,   "市值($B)":320,  "52W涨幅(%)":24.1},
    {"代码":"WMT",   "公司名":"Walmart",           "行业":"消费",    "P/E":31.5, "P/B":7.8,  "ROE (%)":22.1,  "市值($B)":720,  "52W涨幅(%)":68.2},
    {"代码":"CVX",   "公司名":"Chevron",           "行业":"能源",    "P/E":13.8, "P/B":1.8,  "ROE (%)":12.6,  "市值($B)":272,  "52W涨幅(%)":-7.3},
    {"代码":"MRK",   "公司名":"Merck",             "行业":"医疗",    "P/E":11.2, "P/B":5.3,  "ROE (%)":43.2,  "市值($B)":256,  "52W涨幅(%)":-12.4},
    {"代码":"ABBV",  "公司名":"AbbVie",            "行业":"医疗",    "P/E":16.5, "P/B":39.8, "ROE (%)":None,  "市值($B)":312,  "52W涨幅(%)":18.3},
    {"代码":"CAT",   "公司名":"Caterpillar",       "行业":"工业",    "P/E":16.2, "P/B":8.9,  "ROE (%)":54.3,  "市值($B)":178,  "52W涨幅(%)":2.1},
    {"代码":"IBM",   "公司名":"IBM",               "行业":"科技",    "P/E":21.3, "P/B":7.2,  "ROE (%)":None,  "市值($B)":198,  "52W涨幅(%)":35.2},
    {"代码":"HON",   "公司名":"Honeywell",         "行业":"工业",    "P/E":20.1, "P/B":6.8,  "ROE (%)":32.1,  "市值($B)":132,  "52W涨幅(%)":-8.2},
    {"代码":"GE",    "公司名":"GE Aerospace",      "行业":"工业",    "P/E":35.2, "P/B":12.3, "ROE (%)":35.8,  "市值($B)":195,  "52W涨幅(%)":72.3},
    {"代码":"QCOM",  "公司名":"Qualcomm",          "行业":"科技",    "P/E":15.8, "P/B":6.1,  "ROE (%)":40.2,  "市值($B)":162,  "52W涨幅(%)":5.4},
    {"代码":"TXN",   "公司名":"Texas Instruments", "行业":"科技",    "P/E":28.4, "P/B":9.2,  "ROE (%)":32.8,  "市值($B)":158,  "52W涨幅(%)":-5.8},
    {"代码":"NEE",   "公司名":"NextEra Energy",    "行业":"公用事业","P/E":19.8, "P/B":3.1,  "ROE (%)":12.8,  "市值($B)":148,  "52W涨幅(%)":8.3},
    {"代码":"MCD",   "公司名":"McDonald's",        "行业":"消费",    "P/E":22.4, "P/B":None, "ROE (%)":None,  "市值($B)":208,  "52W涨幅(%)":2.8},
    {"代码":"COST",  "公司名":"Costco",            "行业":"消费",    "P/E":52.1, "P/B":15.8, "ROE (%)":30.2,  "市值($B)":385,  "52W涨幅(%)":38.4},
]

CN_DATA = [
    {"代码":"600519", "公司名":"贵州茅台",  "行业":"消费",  "P/E":22.1, "P/B":7.8,  "ROE (%)":35.2, "市值($B)":178, "52W涨幅(%)":-8.3},
    {"代码":"601318", "公司名":"中国平安",  "行业":"金融",  "P/E":7.2,  "P/B":0.9,  "ROE (%)":12.1, "市值($B)":68,  "52W涨幅(%)":-5.1},
    {"代码":"600036", "公司名":"招商银行",  "行业":"金融",  "P/E":5.8,  "P/B":0.8,  "ROE (%)":14.2, "市值($B)":88,  "52W涨幅(%)":-3.2},
    {"代码":"000858", "公司名":"五粮液",    "行业":"消费",  "P/E":15.3, "P/B":4.2,  "ROE (%)":28.5, "市值($B)":48,  "52W涨幅(%)":-12.4},
    {"代码":"000333", "公司名":"美的集团",  "行业":"工业",  "P/E":14.2, "P/B":3.8,  "ROE (%)":27.3, "市值($B)":52,  "52W涨幅(%)":5.2},
    {"代码":"600276", "公司名":"恒瑞医药",  "行业":"医疗",  "P/E":42.3, "P/B":6.1,  "ROE (%)":14.8, "市值($B)":28,  "52W涨幅(%)":18.3},
    {"代码":"000651", "公司名":"格力电器",  "行业":"工业",  "P/E":8.2,  "P/B":2.1,  "ROE (%)":24.6, "市值($B)":32,  "52W涨幅(%)":-2.8},
    {"代码":"600900", "公司名":"长江电力",  "行业":"公用事业","P/E":18.5,"P/B":3.2,  "ROE (%)":17.8, "市值($B)":62,  "52W涨幅(%)":12.1},
    {"代码":"002415", "公司名":"海康威视",  "行业":"科技",  "P/E":18.2, "P/B":3.5,  "ROE (%)":19.8, "市值($B)":35,  "52W涨幅(%)":-8.5},
    {"代码":"600887", "公司名":"伊利股份",  "行业":"消费",  "P/E":12.8, "P/B":3.1,  "ROE (%)":24.2, "市值($B)":28,  "52W涨幅(%)":-5.3},
    {"代码":"000568", "公司名":"泸州老窖",  "行业":"消费",  "P/E":17.5, "P/B":5.8,  "ROE (%)":33.1, "市值($B)":32,  "52W涨幅(%)":-15.2},
    {"代码":"002594", "公司名":"比亚迪",    "行业":"汽车",  "P/E":24.8, "P/B":4.2,  "ROE (%)":17.2, "市值($B)":82,  "52W涨幅(%)":28.4},
    {"代码":"600031", "公司名":"三一重工",  "行业":"工业",  "P/E":15.2, "P/B":2.8,  "ROE (%)":18.5, "市值($B)":22,  "52W涨幅(%)":3.2},
    {"代码":"601012", "公司名":"隆基绿能",  "行业":"能源",  "P/E":None, "P/B":1.2,  "ROE (%)":2.1,  "市值($B)":18,  "52W涨幅(%)":-35.2},
    {"代码":"601398", "公司名":"工商银行",  "行业":"金融",  "P/E":5.1,  "P/B":0.6,  "ROE (%)":10.8, "市值($B)":198, "52W涨幅(%)":28.5},
    {"代码":"600028", "公司名":"中国石化",  "行业":"能源",  "P/E":8.5,  "P/B":0.7,  "ROE (%)":8.2,  "市值($B)":72,  "52W涨幅(%)":5.8},
    {"代码":"601628", "公司名":"中国人寿",  "行业":"金融",  "P/E":12.3, "P/B":1.1,  "ROE (%)":9.2,  "市值($B)":58,  "52W涨幅(%)":18.2},
    {"代码":"600309", "公司名":"万华化学",  "行业":"材料",  "P/E":11.2, "P/B":2.8,  "ROE (%)":25.3, "市值($B)":28,  "52W涨幅(%)":-5.2},
    {"代码":"000002", "公司名":"万科A",     "行业":"房地产","P/E":None, "P/B":0.4,  "ROE (%)":None, "市值($B)":12,  "52W涨幅(%)":-28.5},
    {"代码":"601888", "公司名":"中国中免",  "行业":"消费",  "P/E":28.5, "P/B":5.2,  "ROE (%)":18.5, "市值($B)":22,  "52W涨幅(%)":-18.3},
]

# ── 页面配置 ───────────────────────────────────────────────────────────────────
st.set_page_config(page_title="因子选股器", layout="wide", page_icon="📊")
st.title("📊 A股 + 美股 因子选股器")
st.caption("基于 Fama-French 因子（估值、盈利、规模）的系统化筛选工具 — MVP v0.3")
st.info("📌 当前使用内置数据（2025Q1），无需网络连接。后续版本将接入实时数据。", icon="ℹ️")

# ── 侧边栏 ─────────────────────────────────────────────────────────────────────
st.sidebar.header("🌏 市场选择")
market = st.sidebar.radio("选择市场", ["🇺🇸 美股", "🇨🇳 A股", "🌐 全部"])

st.sidebar.header("🏭 行业筛选")
all_sectors = sorted(set(
    r["行业"] for r in (US_DATA + CN_DATA)
))
selected_sectors = st.sidebar.multiselect("选择行业（不选=全部）", all_sectors)

st.sidebar.header("🎛️ 因子筛选")
max_pe  = st.sidebar.slider("最大 P/E（市盈率）", 0, 100, 50)
max_pb  = st.sidebar.slider("最大 P/B（市净率）", 0.0, 50.0, 15.0, step=0.5)
min_roe = st.sidebar.slider("最小 ROE (%)", 0, 50, 0)
max_cap = st.sidebar.selectbox("市值上限", ["不限", "小市值 <$50B", "中市值 <$200B"])
top_n   = st.sidebar.slider("显示前 N 只股票", 5, 40, 20)

st.sidebar.header("📐 排序依据")
sort_by = st.sidebar.selectbox("排序因子", [
    "P/B ↑（最便宜）",
    "P/E ↑（最低估）",
    "ROE ↓（最赚钱）",
    "52W涨幅 ↓（最强势）",
    "市值 ↑（最小）",
])

# ── 构建DataFrame ──────────────────────────────────────────────────────────────
def build_df(data, market_label):
    df = pd.DataFrame(data)
    df.insert(0, "市场", market_label)
    return df

frames = []
if market in ["🇺🇸 美股", "🌐 全部"]:
    frames.append(build_df(US_DATA, "🇺🇸 美股"))
if market in ["🇨🇳 A股", "🌐 全部"]:
    frames.append(build_df(CN_DATA, "🇨🇳 A股"))

df = pd.concat(frames, ignore_index=True)

# ── 筛选 ───────────────────────────────────────────────────────────────────────
filtered = df.copy()

if selected_sectors:
    filtered = filtered[filtered["行业"].isin(selected_sectors)]

filtered = filtered[filtered["P/E"].notna() & (filtered["P/E"] > 0)]
filtered = filtered[filtered["P/B"].notna() & (filtered["P/B"] > 0)]
filtered = filtered[filtered["P/E"] <= max_pe]
filtered = filtered[filtered["P/B"] <= max_pb]

if min_roe > 0:
    filtered = filtered[filtered["ROE (%)"].fillna(0) >= min_roe]

if max_cap == "小市值 <$50B":
    filtered = filtered[filtered["市值($B)"] < 50]
elif max_cap == "中市值 <$200B":
    filtered = filtered[filtered["市值($B)"] < 200]

# 排序
sort_map = {
    "P/B ↑（最便宜）":    ("P/B", True),
    "P/E ↑（最低估）":    ("P/E", True),
    "ROE ↓（最赚钱）":    ("ROE (%)", False),
    "52W涨幅 ↓（最强势）":("52W涨幅(%)", False),
    "市值 ↑（最小）":     ("市值($B)", True),
}
sort_col, ascending = sort_map[sort_by]
filtered = filtered.sort_values(sort_col, ascending=ascending, na_position="last").head(top_n).reset_index(drop=True)

# ── 展示 ───────────────────────────────────────────────────────────────────────
st.subheader(f"✅ 筛选结果：{len(filtered)} 只股票")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("符合条件", f"{len(filtered)} 只")
c2.metric("平均 P/E",  f"{filtered['P/E'].mean():.1f}"    if not filtered.empty else "N/A")
c3.metric("平均 P/B",  f"{filtered['P/B'].mean():.2f}"    if not filtered.empty else "N/A")
c4.metric("平均 ROE",  f"{filtered['ROE (%)'].mean():.1f}%" if filtered['ROE (%)'].notna().any() else "N/A")
c5.metric("平均市值",  f"${filtered['市值($B)'].mean():.0f}B" if not filtered.empty else "N/A")

if filtered.empty:
    st.warning("没有符合条件的股票，请放宽筛选条件。")
else:
    fmt = {
        "P/E":        "{:.1f}",
        "P/B":        "{:.2f}",
        "ROE (%)":    "{:.1f}%",
        "市值($B)":   "${:.0f}B",
        "52W涨幅(%)": "{:.1f}%",
    }
    styled = (filtered.style
              .background_gradient(subset=["P/B"], cmap="RdYlGn_r")
              .background_gradient(subset=["P/E"], cmap="RdYlGn_r")
              .format(fmt, na_rep="N/A"))
    if filtered["ROE (%)"].notna().any():
        styled = styled.background_gradient(subset=["ROE (%)"], cmap="RdYlGn")
    if filtered["52W涨幅(%)"].notna().any():
        styled = styled.background_gradient(subset=["52W涨幅(%)"], cmap="RdYlGn")

    st.dataframe(styled, use_container_width=True, height=450)

    tab1, tab2, tab3 = st.tabs(["📉 P/B 对比", "📈 ROE 对比", "🚀 52W涨幅"])
    with tab1:
        st.bar_chart(filtered.set_index("代码")["P/B"].dropna())
    with tab2:
        data = filtered.set_index("代码")["ROE (%)"].dropna()
        if not data.empty: st.bar_chart(data)
        else: st.info("当前筛选结果无ROE数据")
    with tab3:
        data = filtered.set_index("代码")["52W涨幅(%)"].dropna()
        if not data.empty: st.bar_chart(data)

    csv = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ 导出 CSV", csv, "筛选结果.csv", "text/csv")

# ── 因子说明 ───────────────────────────────────────────────────────────────────
with st.expander("📖 因子说明"):
    st.markdown("""
| 因子 | 含义 | 学术来源 |
|------|------|----------|
| **P/E** | 市盈率，越低说明越便宜 | Fama-French Value |
| **P/B** | 市净率，越低越接近内在价值 | Fama-French Value (HML) |
| **ROE** | 净资产收益率，衡量盈利能力 | Quality Factor |
| **市值** | 公司规模，小市值历史上有超额收益 | Fama-French Size (SMB) |
| **52W涨幅** | 过去一年价格动量 | Momentum Factor |
    """)

st.divider()
st.caption("⚠️ 本工具仅供学习研究，不构成投资建议。数据为2025Q1手动整理，仅用于MVP验证。")
