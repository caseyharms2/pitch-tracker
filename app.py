import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

Setup
st.set_page_config(layout="wide", page_title="Indians Dugout Command")
st_autorefresh(interval=30 * 1000, key="datarefresh")

st.title("⚾ Indianapolis Indians Strategy Tracker")

--- STEP 1: SELECT TEAM AND DATE ---
col1, col2 = st.columns(2)
with col1:
org_teams = {
"Indianapolis Indians (AAA)": {"id": 484, "sport": 11},
"Pittsburgh Pirates (MLB)": {"id": 134, "sport": 1},
"Altoona Curve (AA)": {"id": 452, "sport": 12},
"Greensboro Grasshoppers (A+)": {"id": 477, "sport": 13},
"Bradenton Marauders (A)": {"id": 522, "sport": 14}
}
team_choice = st.selectbox("Select Team", list(org_teams.keys()), index=0)
t_id = org_teams[team_choice]["id"]
s_id = org_teams[team_choice]["sport"]

with col2:
selected_date = st.date_input("Select Date", datetime.today())

--- STEP 2: FETCH GAME ---
date_str = selected_date.strftime('%Y-%m-%d')
sched_url = f"{s_id}&teamId={t_id}&date={date_str}"

game_pk = None
try:
sched_data = requests.get(sched_url).json()
dates = sched_data.get('dates', [])
if dates:
games = dates[0].get('games', [])
game_options = {f"{g['teams']['away']['team']['name']} @ {g['teams']['home']['team']['name']}": g['gamePk'] for g in games}
selected_game_label = st.selectbox("Select Matchup", list(game_options.keys()))
game_pk = game_options[selected_game_label]
except:
st.error("Schedule error. Check connection.")

--- STEP 3: DATA ENGINE ---
if game_pk:
api_url = f"{game_pk}/feed/live"
data = requests.get(api_url).json()
all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])
