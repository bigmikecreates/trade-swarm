"""Streamlit P&L dashboard for paper trading."""

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "trades.db"

st.set_page_config(page_title="Trade-Swarm Paper Trading", layout="wide")
st.title("Paper Trading Dashboard")

if not DB_PATH.exists():
    st.info("No trades yet. Run the paper trading loop to start logging.")
    st.stop()

conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT * FROM trades ORDER BY timestamp DESC", conn)
conn.close()

if df.empty:
    st.info("No trades yet.")
else:
    total_pnl = df["pnl"].sum() if "pnl" in df.columns else 0
    df_with_pnl = df[df["pnl"].notna()] if "pnl" in df.columns else df
    win_rate = (df_with_pnl["pnl"] > 0).mean() * 100 if len(df_with_pnl) > 0 else 0
    total_trades = len(df)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total P&L", f"${total_pnl:,.2f}")
    col2.metric("Win Rate", f"{win_rate:.1f}%")
    col3.metric("Total Trades", total_trades)

    st.subheader("Trade History")
    display_cols = ["timestamp", "asset", "direction", "action", "size", "entry_price", "exit_price", "pnl", "status"]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols])

    st.subheader("Cumulative P&L")
    if "pnl" in df.columns:
        df_sorted = df.sort_values("timestamp").copy()
        df_sorted["cumulative_pnl"] = df_sorted["pnl"].fillna(0).cumsum()
        st.line_chart(df_sorted.set_index("timestamp")["cumulative_pnl"])
    else:
        st.caption("P&L data not yet available.")
