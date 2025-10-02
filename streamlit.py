# streamlit_app.py
import os
import pandas as pd
import streamlit as st
from supabase import create_client
from dotenv import load_dotenv

# load .env variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
TABLE = "wvb_individual_assists"

@st.cache_resource
def get_client():
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

@st.cache_data(ttl=60)
def fetch_data():
    client = get_client()
    res = client.table(TABLE).select("*").execute()
    df = pd.DataFrame(res.data or [])
    # order by rank if available
    if "rank" in df.columns:
        df = df.sort_values("rank", na_position="last")
    return df

st.title("🏐 NCAA D1 Women’s Volleyball — Assists Leaders")

df = fetch_data()

if df.empty:
    st.warning("No data found in Supabase. Run your loader first.")
else:
    # Filter by team
    teams = ["(All)"] + sorted(df["team"].dropna().unique().tolist())
    team_choice = st.selectbox("Filter by Team", teams)
    if team_choice != "(All)":
        df = df[df["team"] == team_choice]

    st.subheader("Player Stats Table")
    st.dataframe(df, use_container_width=True)


    # Plot 1: Total Assists by Height
    st.subheader("Total Assists by Height")
    by_height = df.groupby("height")["assists"].sum().reset_index()
    st.bar_chart(by_height.set_index("height"))

    # Plot 2: Avg Assists per Set by Class Year
    st.subheader("Avg Assists per Set by Class Year (cl)")
    by_cl = df.groupby("cl")["per_set"].mean().reset_index()
    st.bar_chart(by_cl.set_index("cl"))

    # Plot 3: Top 10 Players by Total Assists
    st.subheader("Top 10 Players by Total Assists")
    top10 = df.sort_values("assists", ascending=False).head(10)
    st.bar_chart(top10.set_index("name")["assists"])

    st.caption("Source: NCAA | Stored in Supabase table: wvb_individual_assists")

