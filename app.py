import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

st.set_page_config(layout="wide", page_title="Dugout Command Center")

# Auto-refresh every 30s
st_autorefresh(interval=30 * 1000, key="datarefresh")

st.title("⚾ Pirates / Indians Strategy Tracker")

# --- STEP 1: SELECT TEAM AND DATE ---
col1, col2 = st.columns(2)
with col1:
    team_choice = st.selectbox("Select Team", ["Pittsburgh Pirates", "Indianapolis Indians"])
    team_id = 134 if team_choice == "Pittsburgh Pirates" else 484  # Pirates=134, Indians=484
with col2:
    selected_date = st.date_input("Select Date", datetime.today())

# --- STEP 2: FETCH GAME PK ---
date_str = selected_date.strftime('%Y-%m-%d')
sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}&date={date_str}"
if team_choice == "Indianapolis Indians":
    # Triple-A uses sportId=11
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=11&teamId={team_id}&date={date_str}"

game_pk = None
try:
    sched_data = requests.get(sched_url).json()
    games = sched_data.get('dates', [{}])[0].get('games', [])
    
    if not games:
        st.warning(f"No games found for {team_choice} on {date_str}.")
    else:
        # Handle doubleheaders
        game_options = {f"{g['teams']['away']['team']['name']} @ {g['teams']['home']['team']['name']} (ID: {g['gamePk']})": g['gamePk'] for g in games}
        selected_game_label = st.selectbox("Select Matchup", list(game_options.keys()))
        game_pk = game_options[selected_game_label]
except Exception:
    st.error("Error fetching schedule. Check internet connection.")

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
                        "Prev": prev_p, "Velo": p_data.get('startSpeed', 0), "Count": count,
                        "X": p_data.get('coordinates', {}).get('pX'), "Z": p_data.get('coordinates', {}).get('pZ'),
                        "Batter_Num": batter_count_in_game
                    })
                prev_p = event.get('details', {}).get('type', {}).get('description', 'Unknown')

    df = pd.DataFrame(pitch_data)

    if not df.empty:
        # [THE REST OF YOUR PREVIOUS DASHBOARD CODE GOES HERE: TICKER, TABLES, ZONE CHART]
        # (I've truncated the repetition here, but keep all the visuals we built!)
        st.subheader("🔥 Recent Sequence (Auto-Updating)")
        last_5 = df.tail(5).iloc[::-1]
        t_cols = st.columns(5)
        for i, (idx, row) in enumerate(last_5.iterrows()):
            with t_cols[i]: st.metric(f"{row['Type']} ({row['Count']})", f"{row['Velo']} mph")

        st.sidebar.header("Dugout Controls")
        pitcher = st.sidebar.selectbox("Pitcher", df['Pitcher'].unique())
        split = st.sidebar.radio("Batter Side", ["All", "Left", "Right"])
        df_p = df[df['Pitcher'] == pitcher].copy()
        if split != "All": df_p = df_p[df_p['Side'] == split]

        tab1, tab2 = st.tabs(["📊 Tendencies & Zone", "🔄 Sequences & Order"])
        with tab1:
            c1, c2 = st.columns([1, 1.5])
            with c1:
                ct = pd.crosstab(df_p['Count'], df_p['Type'], normalize='index') * 100
                ct = ct.reindex([c for c in valid_counts if c in ct.index])
                st.table(ct.style.format("{:.0f}%"))
            with c2:
                fig = go.Figure()
                for pt in df_p['Type'].unique():
                    d = df_p[df_p['Type'] == pt]
                    fig.add_trace(go.Scatter(x=d['X'], y=d['Z'], mode='markers', name=pt, marker=dict(size=12)))
                fig.add_shape(type="rect", x0=-0.85, y0=1.5, x1=0.85, y1=3.5, line=dict(color="White", width=4))
                for x in [-0.28, 0.28]: fig.add_shape(type="line", x0=x, y0=1.5, x1=x, y1=3.5, line=dict(color="Gray", width=1, dash="dash"))
                for y in [2.16, 2.83]: fig.add_shape(type="line", x0=-0.85, y0=y, x1=0.85, y1=y, line=dict(color="Gray", width=1, dash="dash"))
                fig.update_layout(template="plotly_dark", xaxis=dict(range=[-2,2], visible=False), yaxis=dict(range=[0,5], visible=False))
                st.plotly_chart(fig, use_container_width=True)
