import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta

# Set page to wide for dugout tablet viewing
st.set_page_config(layout="wide", page_title="Opposing Pitcher Tendencies")

# Auto-refresh every 30 seconds
st_autorefresh(interval=30 * 1000, key="datarefresh")

st.title("⚾ Opposing Pitcher Tendencies")

# --- CUSTOM PITCH COLORS ---
PITCH_COLORS = {
    "4-Seam Fastball": "red",
    "Four-Seam Fastball": "red",
    "Fastball": "red",
    "Slider": "lightgreen",
    "Curveball": "blue",
    "Knuckle Curve": "blue",
    "2-Seam Fastball": "orange",
    "Sinker": "orange",
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
    # BUG FIX: Adjust UTC to local "today" (subtracting 5 hours for EST/EDT safety)
    local_today = datetime.utcnow() - timedelta(hours=5)
    selected_date = st.date_input("Select Date", local_today)

# --- STEP 2: FETCH GAME PK ---
date_str = selected_date.strftime('%Y-%m-%d')
sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId={s_id}&teamId={t_id}&date={date_str}"

game_pk = None
opponent_id = None

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
        
        for g in games:
            if g['gamePk'] == game_pk:
                away_id = g['teams']['away']['team']['id']
                home_id = g['teams']['home']['team']['id']
                opponent_id = away_id if home_id == t_id else home_id
except Exception:
    st.error("Connection error. Check stadium Wi-Fi.")

# --- STEP 3: PULL LIVE DATA ---
if game_pk and opponent_id:
    api_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    try:
        data = requests.get(api_url).json()
        all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])
    except:
        all_plays = []
    
    pitch_data = []
    pitcher_batter_counts = {}
    valid_counts = ["0-0", "1-0", "2-0", "3-0", "0-1", "1-1", "2-1", "3-1", "0-2", "1-2", "2-2", "3-2"]
    
    for play in all_plays:
        p_name = play['matchup']['pitcher']['fullName']
        # FETCH HANDEDNESS (L or R)
        p_hand_code = play['matchup'].get('pitchHand', {}).get('code', 'U')
        p_display_name = f"{p_name} ({p_hand_code}HP)"
        
        is_home_pitching = play.get('about', {}).get('isTopInning', True)
        current_pitching_team_id = data.get('gameData', {}).get('teams', {}).get('home', {}).get('id') if is_home_pitching else data.get('gameData', {}).get('teams', {}).get('away', {}).get('id')

        if current_pitching_team_id == t_id:
            continue
            
        if p_display_name not in pitcher_batter_counts:
            pitcher_batter_counts[p_display_name] = 0
        pitcher_batter_counts[p_display_name] += 1
        b_num = pitcher_batter_counts[p_display_name]
        
        order = "1st" if b_num <= 9 else "2nd" if b_num <= 18 else "3rd+"

        prev_p = "None"
        side = play['matchup'].get('batSide', {}).get('code', 'U')
        
        for event in play.get('playEvents', []):
            if event.get('isPitch'):
                p_data = event.get('pitchData', {})
                p_type = event.get('details', {}).get('type', {}).get('description', 'Unknown')
                count = f"{event.get('count', {}).get('balls')}-{event.get('count', {}).get('strikes')}"
                strikes = event.get('count', {}).get('strikes')
                
                if count in valid_counts:
                    pitch_data.append({
                        "Pitcher": p_display_name,
                        "Side": "LHH" if side == 'L' else "RHH", 
                        "Type": p_type,
                        "Prev": prev_p, 
                        "Velo": p_data.get('startSpeed', 0), 
                        "Count": count,
                        "Strikes": strikes,
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
        count_filter = st.sidebar.radio("Filter by Strikes", ["All Counts", "Less Than 2K", "2K"], horizontal=True)
        
        df_filtered = df[df['Pitcher'] == pitcher].copy()
        if split != "All":
            df_filtered = df_filtered[df_filtered['Side'] == split]
        if count_filter == "Less Than 2K":
            df_filtered = df_filtered[df_filtered['Strikes'] < 2]
        elif count_filter == "2K":
            df_filtered = df_filtered[df_filtered['Strikes'] == 2]

        # --- LIVE TICKER ---
        st.subheader(f"🔥 Live Sequence: {pitcher}")
        last_5 = df[df['Pitcher'] == pitcher].tail(5).iloc[::-1]
        t_cols = st.columns(5)
        for i, (idx, row) in enumerate(last_5.iterrows()):
            color = get_color(row['Type'])
            with t_cols[i]: 
                st.markdown(f"<p style='color:{color}; font-weight:bold; margin-bottom:-10px;'>{row['Type']}</p>", unsafe_allow_html=True)
                st.metric(f"({row['Count']})", f"{row['Velo']} mph")

        # --- TABS ---
        tab1, tab2 = st.tabs(["📊 Tendencies & Zone", "🔄 Sequences & Order"])

        with tab1:
            c1, c2 = st.columns([1.2, 1]) 
            
            with c1:
                st.write(f"### Usage vs League Average: {count_filter}")
                
                if not df_filtered.empty:
                    # 1. FULL 12-COUNT BENCHMARKS
                    benchmarks = {
                        "0-0": {"FB": 52, "BR": 32, "OS": 16}, "1-0": {"FB": 58, "BR": 27, "OS": 15},
                        "2-0": {"FB": 72, "BR": 18, "OS": 10}, "3-0": {"FB": 92, "BR": 5,  "OS": 3},
                        "0-1": {"FB": 48, "BR": 36, "OS": 16}, "1-1": {"FB": 49, "BR": 31, "OS": 20},
                        "2-1": {"FB": 62, "BR": 23, "OS": 15}, "3-1": {"FB": 84, "BR": 11, "OS": 5},
                        "0-2": {"FB": 38, "BR": 44, "OS": 18}, "1-2": {"FB": 40, "BR": 42, "OS": 18},
                        "2-2": {"FB": 44, "BR": 38, "OS": 18}, "3-2": {"FB": 55, "BR": 25, "OS": 20},
                        "Total": {"FB": 52, "BR": 32, "OS": 16}
                    }

                    def get_group(p_name):
                        p = p_name.lower()
                        if any(x in p for x in ["fastball", "sinker", "cutter"]): return "FB"
                        if any(x in p for x in ["slider", "curve", "sweeper", "slurve"]): return "BR"
                        if any(x in p for x in ["changeup", "splitter", "forkball"]): return "OS"
                        return "OTHER"

                    # 2. CREATE FULL MATRIX (Ensures all 12 counts appear in order)
                    df_counts = pd.crosstab(df_filtered['Count'], df_filtered['Type'], margins=True, margins_name="Total")
                    df_perc = pd.crosstab(df_filtered['Count'], df_filtered['Type'], normalize='index') * 100
                    
                    # Sort pitch types by FB -> BR -> OS
                    pitch_cols = [c for c in df_counts.columns if c != "Total"]
                    sorted_pitch_cols = sorted(pitch_cols, key=lambda x: 1 if get_group(x)=="FB" else 2 if get_group(x)=="BR" else 3)
                    
                    # Reindex rows to show ALL counts in baseball order
                    display_rows = [c for c in valid_counts if c in df_counts.index]
                    if "Total" in df_counts.index: display_rows.append("Total")

                  # 3. BUILD THE TABLE
                    formatted_rows = []
                        for count_row in display_rows:
                            row_display = {}
                        for pitch_col in sorted_pitch_cols:
                    # Use .get() to safely handle missing rows/cols
                    # If the count or pitch doesn't exist, it defaults to 0
                    count_val = df_counts.get(pitch_col, {}).get(count_row, 0)
                    perc_val = df_perc.get(pitch_col, {}).get(count_row, 0)
        
                    row_display[pitch_col] = f"{perc_val:.0f}% ({int(count_val)})"
                    formatted_rows.append(row_display)

                    final_df = pd.DataFrame(formatted_rows, index=display_rows)
                    # 4. HEAT MAP STYLING
                    def apply_heat_map(val, count_label, pitch_name):
                        if count_label == "Total": return 'background-color: #444; color: white; font-weight: bold;'
                        try:
                            actual_perc = float(val.split('%')[0])
                            group = get_group(pitch_name)
                            avg = benchmarks.get(count_label, {}).get(group, 0)
                            if actual_perc > (avg + 7): return 'background-color: #8b0000; color: white;' 
                            if actual_perc < (avg - 7): return 'background-color: #00008b; color: white;' 
                        except: pass
                        return 'color: white;'

                    st.table(final_df.style.apply(lambda x: [apply_heat_map(v, x.name, c) for v, c in zip(x, final_df.columns)], axis=1))

        with tab2:
            st.write("### Sequence Matrix")
            seq_df = df_filtered[df_filtered['Prev'] != "None"]
            if not seq_df.empty:
                st.table((pd.crosstab(seq_df['Prev'], seq_df['Type'], normalize='index') * 100).style.format("{:.1f}%"))
            
            st.write("### Times Through Order Usage")
            st.table((pd.crosstab(df_filtered['Order'], df_filtered['Type'], normalize='index') * 100).style.format("{:.0f}%"))
