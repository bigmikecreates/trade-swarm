"""Streamlit dashboard for the Trade-Swarm Agent Laboratory."""

from __future__ import annotations

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Trade-Swarm Lab", layout="wide")
st.title("Trade-Swarm Agent Laboratory")

st.sidebar.header("Navigation")
page = st.sidebar.selectbox(
    "Go to",
    ["Overview", "Experiments", "Signals", "Trades", "Agents"],
)

if page == "Overview":
    st.header("System Overview")
    st.info("Connect the lab by running: streamlit run lab/dashboard/app.py")

elif page == "Experiments":
    st.header("Experiments")
    st.info("Connect the data store to view experiments.")
    
elif page == "Signals":
    st.header("Agent Signals")
    st.info("Connect the data store to view signals.")

elif page == "Trades":
    st.header("Trade Log")
    st.info("Connect the data store to view trade history.")

elif page == "Agents":
    st.header("Agent Registry")
    st.info("Connect the data store to view registered agents.")
