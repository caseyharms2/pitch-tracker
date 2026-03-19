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
            c1, c2 = st.columns([1, 1.5])
            with c1:
                st.write(f"### Usage: {count_filter}")
                
                if not df_filtered.empty:
                    # 1. Sorting Priority Function
                    def pitch_sort_priority(p_name):
                        p = p_name.lower()
                        if any(x in p for x in ["fastball", "sinker", "cutter"]): return 1
                        if any(x in p for x in ["slider", "curve", "sweeper", "slurve"]): return 2
                        if any(x in p for x in ["changeup", "splitter", "forkball", "screwball"]): return 3
                        return 4

                    # 2. Generate Data
                    df_counts = pd.crosstab(df_filtered['Count'], df_filtered['Type'], margins=True, margins_name="Total")
                    df_perc = pd.crosstab(df_filtered['Count'], df_filtered['Type'], normalize='index') * 100
                    
                    # 3. Sort Columns & Define Rows
                    pitch_cols = [c for c in df_counts.columns if c != "Total"]
                    sorted_pitch_cols = sorted(pitch_cols, key=pitch_sort_priority)
                    display_rows = [c for c in valid_counts if c in df_counts.index]
                    if "Total" in df_counts.index: display_rows.append("Total")

                    # 4. Build Formatted DataFrame
                    formatted_rows = []
                    for count_row in display_rows:
                        row_display = {}
                        for pitch_col in sorted_pitch_cols:
                            count_val = df_counts.loc[count_row, pitch_col]
                            if count_row == "Total":
                                total_overall = df_counts.loc["Total", "Total"]
                                perc_val = (count_val / total_overall * 100) if total_overall > 0 else 0
                            else:
                                perc_val = df_perc.loc[count_row, pitch_col] if pitch_col in df_perc.columns else 0
                            
                            row_display[pitch_col] = f"{perc_val:.0f}% ({count_val})"
                        formatted_rows.append(row_display)

                    final_df = pd.DataFrame(formatted_rows, index=display_rows)

                    # 5. Apply Red Styling to the Total Row
                    def highlight_total_row(s):
                        return ['background-color: #8b0000; color: white; font-weight: bold' if s.name == "Total" else '' for _ in s]

                    styled_df = final_df.style.apply(highlight_total_row, axis=1)

                    # 6. Display with Column Config to lock width (prevents wrapping)
                    # We create a config for every column to ensure enough space for "100% (99)"
                    col_config = {col: st.column_config.Column(width="medium") for col in final_df.columns}
                    
                    st.dataframe(
                        styled_df, 
                        use_container_width=True, 
                        column_config=col_config
                    )
                else:
                    st.write("No pitches found for this selection.")
            
            with c2:
                order_view = st.radio("View Zone By Order:", ["All", "1st Time", "2nd Time", "3rd Time+"], horizontal=True)
                df_zone = df_filtered.copy()
                if order_view != "All":
                    map_order = {"1st Time": "1st", "2nd Time": "2nd", "3rd Time+": "3rd+"}
                    df_zone = df_zone[df_zone['Order'] == map_order[order_view]]

                fig = go.Figure()
                
                # --- DRAW THE 9-ZONE GRID ---
                # Vertical Lines
                for x in [-0.283, 0.283]:
                    fig.add_shape(type="line", x0=x, y0=1.5, x1=x, y1=3.5, 
                                  line=dict(color="rgba(255,255,255,0.3)", width=2))
                # Horizontal Lines
                for y in [2.166, 2.833]:
                    fig.add_shape(type="line", x0=-0.85, y0=y, x1=0.85, y1=y, 
                                  line=dict(color="rgba(255,255,255,0.3)", width=2))
                
                # Outer Strike Zone Box
                fig.add_shape(type="rect", x0=-0.85, y0=1.5, x1=0.85, y1=3.5, 
                              line=dict(color="White", width=4))

                # Pitch Markers
                for pt in df_zone['Type'].unique():
                    d = df_zone[df_zone['Type'] == pt]
                    fig.add_trace(go.Scatter(
                        x=d['X'], y=d['Z'], 
                        mode='markers', 
                        name=pt, 
                        marker=dict(size=14, color=get_color(pt), line=dict(width=1, color='Black'), opacity=0.9)
                    ))
                
                fig.update_layout(
                    template="plotly_dark",
                    yaxis=dict(scaleanchor="x", scaleratio=1, range=[0, 5], visible=False),
                    xaxis=dict(range=[-2.5, 2.5], visible=False),
                    height=550, margin=dict(l=0,r=0,t=0,b=0),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.write("### Sequence Matrix")
            seq_df = df_filtered[df_filtered['Prev'] != "None"]
            if not seq_df.empty:
                st.table((pd.crosstab(seq_df['Prev'], seq_df['Type'], normalize='index') * 100).style.format("{:.1f}%"))
            
            st.write("### Times Through Order Usage")
            st.table((pd.crosstab(df_filtered['Order'], df_filtered['Type'], normalize='index') * 100).style.format("{:.0f}%"))
