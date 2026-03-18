import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# Set page to wide for dugout tablet viewing
st.set_page_config(layout="wide", page_title="Opposing Pitcher Tendencies")

# Auto-refresh every 30 seconds
st_autorefresh(interval=30 * 1000, key="datarefresh")

st.title("⚾ Opposing Pitcher Tendencies")

# --- CUSTOM PITCH COLORS ---
# Mapping the specific colors you requested
PITCH_COLORS = {
    "4-Seam Fastball": "red",
    "Slider": "lightgreen",
    "Curveball": "blue",
    "2-Seam Fastball": "orange",
    "Sinker": "orange", # Often grouped with 2-seam
    "Cutter": "forestgreen",
    "Sweeper": "maroon",
    "Changeup": "white",
    "Splitter": "cyan",
    "Unknown": "gray"
}

def get_color(pitch_type):
    return PITCH_COLORS.get(pitch_type, "gray")

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
    team_choice = st.selectbox("Select YOUR Team", list(org_teams.keys()))
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
        
        # Determine if your team is Home or Away to find the "Opponent"
        home_team_id = data.get('gameData', {}).get('teams', {}).get('home', {}).get('id')
        is_home = (home_team_id == t_id)
        opponent_field = 'away' if is_home else 'home'
        
    except:
        all_plays = []
    
    pitch_data = []
    # Dictionary to track batter count per individual pitcher
    pitcher_batter_counts = {}
    valid_counts = ["0-0", "1-0", "2-0", "3-0", "0-1", "1-1", "2-1", "3-1", "0-2", "1-2", "2-2", "3-2"]
    
    for play in all_plays:
        p_name = play['matchup']['pitcher']['fullName']
        p_team = play['matchup'].get('pitcherTeam', {}).get('id')
        
        # ONLY capture data if the pitcher is on the OPPOSING team
        if p_team == t_id:
            continue
            
        # Track "Times Through" for each specific pitcher
        if p_name not in pitcher_batter_counts:
            pitcher_batter_counts[p_name] = 0
        pitcher_batter_counts[p_name] += 1
        b_num = pitcher_batter_counts[p_name]
        
        # Determine "Times Through Order"
        if b_num <= 9: order = "1st"
        elif b_num <= 18: order = "2nd"
        else: order = "3rd+"

        prev_p = "None"
        side = play['matchup'].get('batSide', {}).get('code', 'U')
        
        for event in play.get('playEvents', []):
            if event.get('isPitch'):
                p_data = event.get('pitchData', {})
                p_type = event.get('details', {}).get('type', {}).get('description', 'Unknown')
                count = f"{event.get('count', {}).get('balls')}-{event.get('count', {}).get('strikes')}"
                
                if count in valid_counts:
                    pitch_data.append({
                        "Pitcher": p_name,
                        "Side": "LHH" if side == 'L' else "RHH", 
                        "Type": p_type,
                        "Prev": prev_p, 
                        "Velo": p_data.get('startSpeed', 0), 
                        "Count": count,
                        "Strikes": event.get('count', {}).get('strikes'),
                        "X": p_data.get('coordinates', {}).get('pX'), 
                        "Z": p_data.get('coordinates', {}).get('pZ'),
                        "Order": order
                    })
                prev_p = p_type

    df = pd.DataFrame(pitch_data)

    if not df.empty:
        # --- FILTERS ---
        st.sidebar.header("Dugout Controls")
        pitcher_list = sorted(df['Pitcher'].unique())
        pitcher = st.sidebar.selectbox("Select Opposing Pitcher", pitcher_list)
        split = st.sidebar.radio("Batter Side", ["All", "LHH", "RHH"])
        
        df_filtered = df[df['Pitcher'] == pitcher].copy()
        if split != "All":
            df_filtered = df_filtered[df_filtered['Side'] == split]

        # --- LIVE TICKER ---
        st.subheader(f"🔥 Live Sequence: {pitcher}")
        last_5 = df[df['Pitcher'] == pitcher].tail(5).iloc[::-1]
        t_cols = st.columns(5)
        for i, (idx, row) in enumerate(last_5.iterrows()):
            color = get_color(row['Type'])
            with t_cols[i]: 
                # Color code the pitch name in the metric
                st.markdown(f"<p style='color:{color}; font-weight:bold; margin-bottom:-10px;'>{row['Type']}</p>", unsafe_allow_html=True)
                st.metric(f"({row['Count']})", f"{row['Velo']} mph")

        # --- TABS ---
        tab1, tab2 = st.tabs(["📊 Tendencies & Zone", "🔄 Sequences & Order"])

        with tab1:
            c1, c2 = st.columns([1, 1.5])
            with c1:
                st.write(f"### Usage: {split}")
                if not df_filtered.empty:
                    ct = pd.crosstab(df_filtered['Count'], df_filtered['Type'], normalize='index') * 100
                    ct = ct.reindex([c for c in valid_counts if c in ct.index])
                    # Styling the table header colors isn't easy in Streamlit, 
                    # so we use the formatted dataframe
                    st.table(ct.style.format("{:.0f}%"))
                else:
                    st.write("No pitches found.")
            
            with c2:
                # ZONE VIEW BY TIMES THROUGH ORDER
                order_view = st.radio("View Zone By:", ["All", "1st Time", "2nd Time", "3rd Time+"], horizontal=True)
                
                df_zone = df_filtered.copy()
                if order_view == "1st Time": df_zone = df_zone[df_zone['Order'] == "1st"]
                elif order_view == "2nd Time": df_zone = df_zone[df_zone['Order'] == "2nd"]
                elif order_view == "3rd Time+": df_zone = df_zone[df_zone['Order'] == "3rd+"]

                fig = go.Figure()
                for pt in df_zone['Type'].unique():
                    d = df_zone[df_zone['Type'] == pt]
                    fig.add_trace(go.Scatter(
                        x=d['X'], y=d['Z'], 
                        mode='markers', 
                        name=pt, 
                        marker=dict(size=14, color=get_color(pt), line=dict(width=1, color='Black'), opacity=0.8)
                    ))
                
                # Strike Zone
                fig.add_shape(type="rect", x0=-0.85, y0=1.5, x1=0.85, y1=3.5, line=dict(color="White", width=4))
                fig.update_layout(
                    template="plotly_dark",
                    yaxis=dict(scaleanchor="x", scaleratio=1, range=[0, 5], visible=False),
                    xaxis=dict(range=[-2.5, 2.5], visible=False),
                    height=500, margin=dict(l=0,r=0,t=0,b=0),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.write(f"### Sequence Matrix")
            seq_df = df_filtered[df_filtered['Prev'] != "None"]
            if not seq_df.empty:
                st.table((pd.crosstab(seq_df['Prev'], seq_df['Type'], normalize='index') * 100).style.format("{:.1f}%"))
            
            st.write("### Times Through Order Usage")
            # Only show rows if they exist in the data
            order_counts = pd.crosstab(df_filtered['Order'], df_filtered['Type'], normalize='index') * 100
            st.table(order_counts.style.format("{:.0f}%"))
