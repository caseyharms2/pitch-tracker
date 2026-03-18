import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# Set page to wide for dugout tablet viewing
st.set_page_config(layout="wide", page_title="Pirates Org Dugout Command")

# Auto-refresh every 30 seconds
st_autorefresh(interval=30 * 1000, key="datarefresh")

st.title("⚾ Pirates Organizational Strategy Tracker")

# --- STEP 1: SELECT TEAM AND DATE ---
col1, col2 = st.columns(2)
with col1:
    org_teams = {
        "Pittsburgh Pirates (MLB)": {"id": 134, "sport": 1},
        "Indianapolis Indians (AAA)": {"id": 484, "sport": 11},
        "Altoona Curve (AA)": {"id": 452, "sport": 12},
        "Greensboro Grasshoppers (A+)": {"id": 477, "sport": 13},
        "Bradenton Marauders (A)": {"id": 522, "sport": 14}
    }
    team_choice = st.selectbox("Select Team", list(org_teams.keys()))
    t_id = org_teams[team_choice]["id"]
    s_id = org_teams[team_choice]["sport"]

with col2:
    selected_date = st.date_input("Select Date", datetime.today())

# --- STEP 2: FETCH GAME PK ---
date_str = selected_date.strftime('%Y-%m-%d')
sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId={s_id}&teamId={t_id}&date={date_str}"

game_pk = None
try:
    sched_data = requests.get(sched_url).json()
    dates = sched_data.get('dates', [])
    if not dates:
        st.warning(f"No games found for {team_choice} on {date_str}.")
    else:
        games = dates[0].get('games', [])
        game_options = {f"{g['teams']['away']['team']['name']} @ {g['teams']['home']['team']['name']} (ID: {g['gamePk']})": g['gamePk'] for g in games}
        selected_game_label = st.selectbox("Select Matchup", list(game_options.keys()))
        game_pk = game_options[selected_game_label]
except Exception:
    st.error("Connection error. Check stadium Wi-Fi.")

# --- STEP 3: PULL LIVE DATA ---
if game_pk:
    api_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    try:
        data = requests.get(api_url).json()
        all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])
    except:
        all_plays = []
    
    pitch_data = []
    batter_count_in_game = 0
    valid_counts = ["0-0", "1-0", "2-0", "3-0", "0-1", "1-1", "2-1", "3-1", "0-2", "1-2", "2-2", "3-2"]
    
    for play in all_plays:
        batter_count_in_game += 1
        prev_p = "None"
        side = play['matchup'].get('batSide', {}).get('code', 'U')
        
        for event in play.get('playEvents', []):
            if event.get('isPitch'):
                p_data = event.get('pitchData', {})
                count = f"{event.get('count', {}).get('balls')}-{event.get('count', {}).get('strikes')}"
                
                if count in valid_counts:
                    pitch_data.append({
                        "Pitcher": play['matchup']['pitcher']['fullName'],
                        "Side": "Left" if side == 'L' else "Right",
                        "Type": event.get('details', {}).get('type', {}).get('description', 'Unknown'),
                        "Prev": prev_p, 
                        "Velo": p_data.get('startSpeed', 0), 
                        "Count": count,
                        "Strikes": event.get('count', {}).get('strikes'),
                        "X": p_data.get('coordinates', {}).get('pX'), 
                        "Z": p_data.get('coordinates', {}).get('pZ'),
                        "Batter_Num": batter_count_in_game
                    })
                prev_p = event.get('details', {}).get('type', {}).get('description', 'Unknown')

    df = pd.DataFrame(pitch_data)

    if not df.empty:
        # --- FILTERS (SIDEBAR) ---
        st.sidebar.header("Dugout Controls")
        
        # 1. Pitcher Select
        pitcher_list = sorted(df['Pitcher'].unique())
        pitcher = st.sidebar.selectbox("Select Pitcher", pitcher_list)
        
        # 2. Split Select
        split = st.sidebar.radio("Batter Side", ["All", "Left", "Right"])
        
        # 3. NEW: COUNT FILTER BUTTONS
        count_filter = st.sidebar.radio(
            "Filter by Strikes",
            ["All Counts", "Less Than 2K", "2K"],
            index=0,
            horizontal=True
        )
        
        # Apply Filters
        df_filtered = df[df['Pitcher'] == pitcher].copy()
        if split != "All":
            df_filtered = df_filtered[df_filtered['Side'] == split]
        
        if count_filter == "Less Than 2K":
            df_filtered = df_filtered[df_filtered['Strikes'] < 2]
        elif count_filter == "2K":
            df_filtered = df_filtered[df_filtered['Strikes'] == 2]

        # --- LIVE TICKER (Always shows last 5, regardless of filters) ---
        st.subheader(f"🔥 Recent Sequence: {pitcher}")
        last_5 = df[df['Pitcher'] == pitcher].tail(5).iloc[::-1]
        t_cols = st.columns(5)
        for i, (idx, row) in enumerate(last_5.iterrows()):
            with t_cols[i]: st.metric(f"{row['Type']} ({row['Count']})", f"{row['Velo']} mph")

        # --- TABS ---
        tab1, tab2 = st.tabs(["📊 Tendencies & Zone", "🔄 Sequences & Order"])

        with tab1:
            c1, c2 = st.columns([1, 1.5])
            with c1:
                st.write(f"### Usage: {count_filter} ({split})")
                if not df_filtered.empty:
                    ct = pd.crosstab(df_filtered['Count'], df_filtered['Type'], normalize='index') * 100
                    # Sort table by count order
                    ct = ct.reindex([c for c in valid_counts if c in ct.index])
                    st.table(ct.style.format("{:.0f}%"))
                else:
                    st.write("No pitches found for this filter.")
            
            with c2:
                st.write("### Catcher's View")
                fig = go.Figure()
                for pt in df_filtered['Type'].unique():
                    d = df_filtered[df_filtered['Type'] == pt]
                    fig.add_trace(go.Scatter(x=d['X'], y=d['Z'], mode='markers', name=pt, marker=dict(size=14, line=dict(width=1, color='Black'), opacity=0.8)))
                
                # Strike Zone Visuals
                fig.add_shape(type="rect", x0=-0.85, y0=1.5,
