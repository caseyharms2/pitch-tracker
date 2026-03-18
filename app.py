import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# Set page to wide for dugout tablet viewing
st.set_page_config(layout="wide", page_title="Pirates Org Dugout Command")

# Auto-refresh every 30 seconds to catch live pitches
st_autorefresh(interval=30 * 1000, key="datarefresh")

st.title("⚾ Pirates Organizational Strategy Tracker")

# --- STEP 1: SELECT TEAM AND DATE ---
col1, col2 = st.columns(2)
with col1:
    org_teams = {
        "Pittsburgh Pirates (MLB)": {"id": 134, "sport": 1},
        "Indianapolis Indians (AAA)": {"id": 484, "sport": 11},
        "Altoona Curve (AA)": {"()": 452, "sport": 12},
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
                        "X": p_data.get('coordinates', {}).get('pX'), 
                        "Z": p_data.get('coordinates', {}).get('pZ'),
                        "Batter_Num": batter_count_in_game
                    })
                prev_p = event.get('details', {}).get('type', {}).get('description', 'Unknown')

    df = pd.DataFrame(pitch_data)

    if not df.empty:
        # --- LIVE TICKER (Last 5 Pitches) ---
        st.subheader("🔥 Recent Sequence (Auto-Updating)")
        last_5 = df.tail(5).iloc[::-1]
        t_cols = st.columns(5)
        for i, (idx, row) in enumerate(last_5.iterrows()):
            with t_cols[i]: st.metric(f"{row['Type']} ({row['Count']})", f"{row['Velo']} mph")

        # --- FILTERS ---
        st.sidebar.header("Dugout Controls")
        pitcher_list = sorted(df['Pitcher'].unique())
        pitcher = st.sidebar.selectbox("Select Pitcher", pitcher_list)
        split = st.sidebar.radio("Batter Side", ["All", "Left", "Right"])
        
        df_p = df[df['Pitcher'] == pitcher].copy()
        if split != "All": df_p = df_p[df_p['Side'] == split]

        # --- TABS ---
        tab1, tab2 = st.tabs(["📊 Tendencies & Zone", "🔄 Sequences & Order"])

        with tab1:
            c1, c2 = st.columns([1, 1.5])
            with c1:
                st.write(f"### Usage by Count ({split})")
                ct = pd.crosstab(df_p['Count'], df_p['Type'], normalize='index') * 100
                ct = ct.reindex([c for c in valid_counts if c in ct.index])
                st.table(ct.style.format("{:.0f}%"))
            
            with c2:
                st.write("### Catcher's View")
                fig = go.Figure()
                for pt in df_p['Type'].unique():
                    d = df_p[df_p['Type'] == pt]
                    fig.add_trace(go.Scatter(x=d['X'], y=d['Z'], mode='markers', name=pt, marker=dict(size=14, line=dict(width=1, color='Black'), opacity=0.8)))
                
                # Strike Zone Outer Box
                fig.add_shape(type="rect", x0=-0.85, y0=1.5, x1=0.85, y1=3.5, line=dict(color="White", width=4))
                # Internal 9-Grid Lines
                for x in [-0.28, 0.28]:
                    fig.add_shape(type="line", x0=x, y0=1.5, x1=x, y1=3.5, line=dict(color="rgba(255,255,255,0.3)", width=1, dash="dash"))
                for y in [2.16, 2.83]:
                    fig.add_shape(type="line", x0=-0.85, y0=y, x1=0.85, y1=y, line=dict(color="rgba(255,255,255,0.3)", width=1, dash="dash"))
                
                # Lock Aspect Ratio to prevent smushing
                fig.update_layout(
                    template="plotly_dark",
                    yaxis=dict(scaleanchor="x", scaleratio=1, range=[0, 5], visible=False),
                    xaxis=dict(range=[-2.5, 2.5], visible=False),
                    height=600, margin=dict(l=0,r=0,t=0,b=0),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.write(f"### Sequence Matrix vs {split}HH")
            seq_df = df_p[df_p['Prev'] != "None"]
            if not seq_df.empty:
                st.table((pd.crosstab(seq_df['Prev'], seq_df['Type'], normalize='index') * 100).style.format("{:.1f}%"))
            
            st.write("### Times Through Order")
            df_p['Order'] = df_p['Batter_Num'].apply(lambda n: "1st" if n<=9 else "2nd" if n<=18 else "3rd+")
            st.table((pd.crosstab(df_p['Order'], df_p['Type'], normalize='index') * 100).style.format("{:.0f}%"))
