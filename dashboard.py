#!/usr/bin/env python3
"""
Streamlit dashboard for visualizing the DOGE trading bot's database.

Run with:  streamlit run dashboard.py
"""
import os
import subprocess
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import sqlite3
import streamlit as st
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env")
try:
    INITIAL_CAPITAL_USD = float(os.getenv("INITIAL_CAPITAL_USD", "1000") or 1000)
except ValueError:
    INITIAL_CAPITAL_USD = 1000.0

# Fixed categorical palette (dataviz skill reference palette, reused unchanged —
# see references/palette.md; slot order is the CVD-safety mechanism, don't reorder).
BLUE = "#2a78d6"    # slot 1 — BUY / USD / "good" side of diverging scales
ORANGE = "#eb6834"  # slot 2 — DOGE allocation
RED = "#e34948"     # slot 8 — SELL / "poor" side of diverging scales
GRAY = "#898781"    # muted ink — neutral reference lines / HOLD

st.set_page_config(page_title="DOGE Trading Bot Dashboard", page_icon="🐕", layout="wide")


def _available_dbs():
    candidates = {
        "CI (synced, current)": APP_DIR / ".ci_trading_data.db",
        "Local (older)": APP_DIR / "trading_data.db",
    }
    return {label: path for label, path in candidates.items() if path.exists()}


dbs = _available_dbs()
if not dbs:
    st.error(
        "No trading database found in this folder. Run "
        "`python mvp.py --trades 1 --sync-github` first to download one."
    )
    st.stop()

with st.sidebar:
    st.header("Data source")
    label = st.radio("Database", list(dbs.keys()), index=0)
    db_path = dbs[label]
    st.caption(str(db_path))
    if st.button("🔄 Sync latest from GitHub Actions"):
        with st.spinner("Downloading latest CI database..."):
            result = subprocess.run(
                [sys.executable, "mvp.py", "--trades", "1", "--sync-github"],
                cwd=str(APP_DIR),
                capture_output=True,
                text=True,
                timeout=120,
            )
        st.code((result.stdout or "") + (result.stderr or ""), language=None)
        st.cache_data.clear()
        st.rerun()


@st.cache_data(ttl=60)
def load_tables(path_str: str, mtime: float):
    """mtime is part of the cache key purely so a re-sync (which changes the file's
    mtime) busts the cache automatically on next rerun, without needing a TTL wait."""
    conn = sqlite3.connect(path_str)
    try:
        market = pd.read_sql_query("SELECT * FROM market_data ORDER BY timestamp", conn)
        trades = pd.read_sql_query("SELECT * FROM trade_executions ORDER BY timestamp", conn)
        analysis = pd.read_sql_query("SELECT * FROM analysis_results ORDER BY timestamp", conn)
    finally:
        conn.close()
    for df in (market, trades, analysis):
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return market, trades, analysis


market_df, trades_df, analysis_df = load_tables(str(db_path), db_path.stat().st_mtime)

st.title("🐕 DOGE Trading Bot Dashboard")
st.caption(f"Data source: {label} · {len(trades_df)} trades · {len(market_df)} market snapshots")

# ───────────────────────── Overview stat tiles ─────────────────────────
col1, col2, col3, col4 = st.columns(4)

pv_series = market_df["portfolio_value"].dropna() if "portfolio_value" in market_df else pd.Series(dtype=float)
if not pv_series.empty:
    latest_portfolio = pv_series.iloc[-1]
    gain_pct = (latest_portfolio - INITIAL_CAPITAL_USD) / INITIAL_CAPITAL_USD * 100
    col1.metric("Portfolio value", f"${latest_portfolio:,.2f}", f"{gain_pct:+.2f}% vs initial")
else:
    col1.metric("Portfolio value", "—")

if "success" in trades_df:
    executed_ct = int((trades_df["success"] == 1).sum())
    skipped_ct = len(trades_df) - executed_ct
    col2.metric("Trades executed", f"{executed_ct}", f"{skipped_ct} skipped/failed")
else:
    col2.metric("Trades executed", f"{len(trades_df)}")

if "decision_correct" in trades_df:
    labeled = trades_df.dropna(subset=["decision_correct"])
    if len(labeled):
        win_rate = (labeled["decision_correct"] == 1).mean() * 100
        col3.metric("Win rate (labeled)", f"{win_rate:.0f}%", f"n={len(labeled)}")
    else:
        col3.metric("Win rate (labeled)", "—")
else:
    col3.metric("Win rate (labeled)", "—")

price_series = market_df["current_price"].dropna() if "current_price" in market_df else pd.Series(dtype=float)
col4.metric("Latest DOGE price", f"${price_series.iloc[-1]:.5f}" if not price_series.empty else "—")

st.divider()

tab_price, tab_portfolio, tab_perf, tab_trades, tab_quality, tab_journal = st.tabs(
    ["Price & Trades", "Portfolio Over Time", "Performance", "Trade Log", "Decision Quality", "Self-Reflection Journal"]
)

# ───────────────────────── Price & Trades ─────────────────────────
with tab_price:
    st.subheader("DOGE price with trade markers")
    price_df = market_df.dropna(subset=["current_price", "timestamp"]) if "current_price" in market_df else pd.DataFrame()
    if price_df.empty:
        st.info("No market data yet.")
    else:
        line = alt.Chart(price_df).mark_line(color=GRAY, strokeWidth=2).encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y("current_price:Q", title="DOGE price (USD)"),
            tooltip=[
                alt.Tooltip("timestamp:T", title="Time"),
                alt.Tooltip("current_price:Q", title="Price", format="$.5f"),
            ],
        )
        chart = line.properties(height=420)
        trade_pts = trades_df.dropna(subset=["current_price", "timestamp"]) if {"current_price", "timestamp"} <= set(trades_df.columns) else pd.DataFrame()
        trade_pts = trade_pts[trade_pts["action"].isin(["BUY", "SELL"])] if not trade_pts.empty else trade_pts
        if not trade_pts.empty:
            markers = alt.Chart(trade_pts).mark_point(filled=True, size=110).encode(
                x="timestamp:T",
                y="current_price:Q",
                color=alt.Color(
                    "action:N",
                    scale=alt.Scale(domain=["BUY", "SELL"], range=[BLUE, RED]),
                    legend=alt.Legend(title="Action"),
                ),
                shape=alt.Shape(
                    "action:N",
                    scale=alt.Scale(domain=["BUY", "SELL"], range=["triangle-up", "triangle-down"]),
                    legend=None,
                ),
                opacity=alt.condition(alt.datum.success == 1, alt.value(1.0), alt.value(0.3)),
                tooltip=[
                    alt.Tooltip("timestamp:T", title="Time"),
                    alt.Tooltip("action:N", title="Action"),
                    alt.Tooltip("percentage:Q", title="% of balance"),
                    alt.Tooltip("current_price:Q", title="Price", format="$.5f"),
                    alt.Tooltip("success:N", title="Executed (1=yes)"),
                ],
            )
            chart = chart + markers
            st.caption("Faded markers = trade was skipped or failed (e.g. below minimum order size).")
        st.altair_chart(chart.interactive(), use_container_width=True)

# ───────────────────────── Portfolio Over Time ─────────────────────────
with tab_portfolio:
    st.subheader("Portfolio value")
    pv_df = market_df.dropna(subset=["portfolio_value", "timestamp"]) if "portfolio_value" in market_df else pd.DataFrame()
    if pv_df.empty:
        st.info("No portfolio value history yet.")
    else:
        value_line = alt.Chart(pv_df).mark_line(color=BLUE, strokeWidth=2).encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y("portfolio_value:Q", title="Portfolio value (USD)"),
            tooltip=[
                alt.Tooltip("timestamp:T", title="Time"),
                alt.Tooltip("portfolio_value:Q", title="Value", format="$.2f"),
            ],
        )
        baseline = alt.Chart(pd.DataFrame({"y": [INITIAL_CAPITAL_USD]})).mark_rule(
            color=GRAY, strokeDash=[4, 4]
        ).encode(y="y:Q")
        st.altair_chart((value_line + baseline).properties(height=320).interactive(), use_container_width=True)
        st.caption(f"Dashed line = initial capital (${INITIAL_CAPITAL_USD:,.0f})")

    st.subheader("Allocation: USD vs DOGE")
    alloc_cols = {"usd_percentage", "doge_percentage", "timestamp"}
    alloc_df = market_df.dropna(subset=list(alloc_cols)) if alloc_cols <= set(market_df.columns) else pd.DataFrame()
    if alloc_df.empty:
        st.info("No allocation history yet.")
    else:
        long_df = alloc_df.melt(
            id_vars=["timestamp"],
            value_vars=["usd_percentage", "doge_percentage"],
            var_name="asset",
            value_name="pct",
        )
        long_df["asset"] = long_df["asset"].map({"usd_percentage": "USD (cash)", "doge_percentage": "DOGE"})
        area = alt.Chart(long_df).mark_area().encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y("pct:Q", title="% of portfolio", stack="zero"),
            color=alt.Color(
                "asset:N",
                scale=alt.Scale(domain=["USD (cash)", "DOGE"], range=[BLUE, ORANGE]),
                legend=alt.Legend(title=None),
            ),
            tooltip=["timestamp:T", "asset:N", alt.Tooltip("pct:Q", format=".1f")],
        ).properties(height=280)
        st.altair_chart(area.interactive(), use_container_width=True)

# ───────────────────────── Performance ─────────────────────────
with tab_perf:
    pv_df = (
        market_df.dropna(subset=["portfolio_value", "timestamp"]).sort_values("timestamp")
        if "portfolio_value" in market_df.columns else pd.DataFrame()
    )

    st.subheader("Returns by period")
    if pv_df.empty:
        st.info("No portfolio value history yet.")
    else:
        now_ts = pv_df["timestamp"].iloc[-1]
        end_val = pv_df["portfolio_value"].iloc[-1]

        def _period_return(days):
            """% change in portfolio_value from `days` ago to the latest snapshot.
            Uses the closest snapshot at/before the cutoff; if the lookback predates
            all data, falls back to the earliest snapshot (marked with *)."""
            if days is None:
                start_val = pv_df["portfolio_value"].iloc[0]
                return (end_val - start_val) / start_val * 100, False
            cutoff = now_ts - pd.Timedelta(days=days)
            before = pv_df[pv_df["timestamp"] <= cutoff]
            if before.empty:
                start_val = pv_df["portfolio_value"].iloc[0]
                predates = True
            else:
                start_val = before["portfolio_value"].iloc[-1]
                predates = False
            if not start_val:
                return None, predates
            return (end_val - start_val) / start_val * 100, predates

        periods = [("1 day", 1), ("7 days", 7), ("30 days", 30), ("90 days", 90), ("All-time", None)]
        cols = st.columns(len(periods))
        for col, (label_p, days) in zip(cols, periods):
            pct, predates = _period_return(days)
            col.metric(label_p + (" *" if predates else ""), f"{pct:+.2f}%" if pct is not None else "—")
        if any(_period_return(d)[1] for _, d in periods if d is not None):
            st.caption("* lookback predates the earliest recorded snapshot — using the earliest available instead. "
                       "Returns are naive (vs. stored portfolio_value snapshots) and don't net out external deposits.")

    st.subheader("Bot vs. buy-and-hold DOGE")
    cmp_df = (
        market_df.dropna(subset=["portfolio_value", "current_price", "timestamp"]).sort_values("timestamp").copy()
        if {"portfolio_value", "current_price", "timestamp"} <= set(market_df.columns) else pd.DataFrame()
    )
    if cmp_df.empty:
        st.info("No market data yet.")
    else:
        base_portfolio = cmp_df["portfolio_value"].iloc[0]
        base_price = cmp_df["current_price"].iloc[0]
        cmp_df["Bot"] = cmp_df["portfolio_value"] / base_portfolio * 100
        cmp_df["Buy & Hold DOGE"] = cmp_df["current_price"] / base_price * 100
        long_cmp = cmp_df.melt(
            id_vars=["timestamp"], value_vars=["Bot", "Buy & Hold DOGE"],
            var_name="strategy", value_name="index",
        )
        cmp_chart = alt.Chart(long_cmp).mark_line(strokeWidth=2).encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y("index:Q", title="Indexed value (first snapshot = 100)"),
            color=alt.Color(
                "strategy:N",
                scale=alt.Scale(domain=["Bot", "Buy & Hold DOGE"], range=[BLUE, GRAY]),
                legend=alt.Legend(title=None),
            ),
            tooltip=["timestamp:T", "strategy:N", alt.Tooltip("index:Q", format=".1f")],
        ).properties(height=320)
        baseline100 = alt.Chart(pd.DataFrame({"y": [100]})).mark_rule(color=GRAY, strokeDash=[2, 2]).encode(y="y:Q")
        st.altair_chart((cmp_chart + baseline100).interactive(), use_container_width=True)
        final_bot = cmp_df["Bot"].iloc[-1]
        final_bh = cmp_df["Buy & Hold DOGE"].iloc[-1]
        st.metric(
            "Bot return vs. just holding DOGE (since first recorded snapshot)",
            f"{final_bot - 100:+.1f}% (bot)",
            f"{final_bot - final_bh:+.1f} pts vs. buy-and-hold",
        )

    st.subheader("Drawdown")
    if pv_df.empty:
        st.info("No portfolio value history yet.")
    else:
        dd_df = pv_df.copy()
        dd_df["peak"] = dd_df["portfolio_value"].cummax()
        dd_df["drawdown_pct"] = (dd_df["portfolio_value"] - dd_df["peak"]) / dd_df["peak"] * 100
        max_dd = dd_df["drawdown_pct"].min()
        st.metric("Max drawdown from a prior peak", f"{max_dd:.2f}%")
        dd_chart = alt.Chart(dd_df).mark_area(color=RED, opacity=0.6).encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y("drawdown_pct:Q", title="Drawdown from peak (%)"),
            tooltip=["timestamp:T", alt.Tooltip("drawdown_pct:Q", title="Drawdown", format=".2f")],
        ).properties(height=220)
        st.altair_chart(dd_chart.interactive(), use_container_width=True)

    st.subheader("Trade activity")
    if trades_df.empty:
        st.info("No trades recorded yet.")
    else:
        buys = trades_df[trades_df["action"] == "BUY"]
        sells = trades_df[trades_df["action"] == "SELL"]
        usd_bought = buys["amount_usd"].dropna().sum() if "amount_usd" in buys else 0.0
        usd_sold = sells["amount_usd"].dropna().sum() if "amount_usd" in sells else 0.0
        avg_trade = trades_df["amount_usd"].dropna().mean() if "amount_usd" in trades_df else None

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total BUY volume", f"${usd_bought:,.2f}")
        c2.metric("Total SELL volume", f"${usd_sold:,.2f}")
        c3.metric("Net USD generated", f"${usd_sold - usd_bought:,.2f}")
        c4.metric("Avg trade size", f"${avg_trade:,.2f}" if avg_trade is not None else "—")

# ───────────────────────── Trade Log ─────────────────────────
with tab_trades:
    st.subheader("Trade history")
    if trades_df.empty:
        st.info("No trades recorded yet.")
    else:
        c1, c2 = st.columns([2, 1])
        actions = sorted(trades_df["action"].dropna().unique().tolist())
        chosen = c1.multiselect("Action", actions, default=actions)
        only_ok = c2.checkbox("Executed only", value=False)

        view = trades_df[trades_df["action"].isin(chosen)]
        if only_ok and "success" in view.columns:
            view = view[view["success"] == 1]

        display_cols = [
            "timestamp", "action", "percentage", "amount_usd", "amount_doge",
            "current_price", "success", "decision_quality_label",
            "decision_quality_score", "reflection",
        ]
        display_cols = [c for c in display_cols if c in view.columns]
        st.dataframe(
            view[display_cols].sort_values("timestamp", ascending=False),
            use_container_width=True,
            height=500,
        )
        st.caption(f"{len(view)} of {len(trades_df)} rows shown")

# ───────────────────────── Decision Quality ─────────────────────────
with tab_quality:
    st.subheader("Decision quality over time")
    needed = {"decision_quality_score", "timestamp"}
    q_df = trades_df.dropna(subset=list(needed)).copy() if needed <= set(trades_df.columns) else pd.DataFrame()
    if q_df.empty:
        st.info("No labeled decisions yet.")
    else:
        q_df["side"] = q_df["decision_quality_score"].apply(lambda v: "Good" if v >= 0 else "Poor")
        bars = alt.Chart(q_df).mark_bar().encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y("decision_quality_score:Q", title="Quality score (-4 to +4)"),
            color=alt.Color(
                "side:N",
                scale=alt.Scale(domain=["Good", "Poor"], range=[BLUE, RED]),
                legend=alt.Legend(title=None),
            ),
            tooltip=["timestamp:T", "action:N", "decision_quality_label:N", "decision_quality_score:Q"],
        ).properties(height=320)
        zero_rule = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=GRAY).encode(y="y:Q")
        st.altair_chart((bars + zero_rule).interactive(), use_container_width=True)

    st.subheader("Quality label distribution")
    order = [
        "extremely_bad", "very_bad", "moderately_bad", "slightly_bad",
        "slightly_good", "moderately_good", "very_good", "extremely_good",
    ]
    if "decision_quality_label" in trades_df.columns:
        counts = trades_df["decision_quality_label"].value_counts().reindex(order).dropna().reset_index()
        counts.columns = ["label", "count"]
    else:
        counts = pd.DataFrame()
    if counts.empty:
        st.info("No quality labels yet.")
    else:
        counts["side"] = counts["label"].apply(lambda l: "Poor" if "bad" in l else "Good")
        dist_chart = alt.Chart(counts).mark_bar().encode(
            x=alt.X("label:N", sort=order, title=None),
            y=alt.Y("count:Q", title="Trades"),
            color=alt.Color(
                "side:N",
                scale=alt.Scale(domain=["Good", "Poor"], range=[BLUE, RED]),
                legend=None,
            ),
            tooltip=["label:N", "count:Q"],
        ).properties(height=280)
        st.altair_chart(dist_chart, use_container_width=True)

# ───────────────────────── Self-Reflection Journal ─────────────────────────
with tab_journal:
    st.subheader("Self-reflection journal")
    st.caption("Written automatically by the bot each cycle — combines recent "
               "trade performance, the market snapshot at that moment, and its own past entries.")
    if "self_reflection" not in analysis_df.columns:
        st.info("This database predates the self-reflection journal feature.")
    else:
        j_df = analysis_df.dropna(subset=["self_reflection"])
        j_df = j_df[j_df["self_reflection"].str.strip() != ""]
        if j_df.empty:
            st.info("No journal entries yet — one is written automatically on the bot's next scheduled run.")
        else:
            for _, row in j_df.sort_values("timestamp", ascending=False).iterrows():
                ts = row["timestamp"]
                rec = row.get("recommendation") or "?"
                pct = row.get("percentage")
                pct_s = f"{pct:.0f}%" if pd.notna(pct) else "—"
                ts_s = ts.strftime("%Y-%m-%d %H:%M") if pd.notna(ts) else "?"
                with st.expander(f"{ts_s} — decided {rec} {pct_s}"):
                    st.write(row["self_reflection"])
