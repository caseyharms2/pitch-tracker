import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

st.set_page_config(layout="wide", page_title="Dugout Command Center")

# --- AUTO-REFRESH (Every 30 seconds) ---
st_autorefresh(interval=30 * 1000, key="datarefresh")

st.title("⚾ Pro Strategy: Pitch Usage & Splits")
url_input = st.text_input("Gameday URL:", placeholder="https://www.mlb.com/gameday/745301")

def get_game_pk(url):
    try: return url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
    except: return None

if url_input:
    game_pk = get_game_pk(url_input)
    if game_pk:
        api_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
        try:
            data = requests.get(api_url).json()
            all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])
        except:
            st.error("Connection error. Waiting for next refresh...")
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
            st.subheader("🔥 Recent Sequence (Auto-Updating)")
            last_5 = df.tail(5).iloc[::-1]
            t_cols = st.columns(5)
            for i, (idx, row) in enumerate(last_5.iterrows()):
                with t_cols[i]:
                    st.metric(f"{row['Type']} ({row['Count']})", f"{row['Velo']} mph")

            st.sidebar.header("Dugout Controls")
            pitcher = st.sidebar.selectbox("Pitcher", df['Pitcher'].unique())
            split = st.sidebar.radio("Batter Side", ["All", "Left", "Right"])
            
            df_p = df[df['Pitcher'] == pitcher].copy()
            if split != "All": df_p = df_p[df_p['Side'] == split]

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
                    for p_type in df_p['Type'].unique():
                        d = df_p[df_p['Type'] == p_type]
                        fig.add_trace(go.Scatter(x=d['X'], y=d['Z'], mode='markers', name=p_type, marker=dict(size=12)))
                    
                    # Outer Strike Zone Box
                    fig.add_shape(type="rect", x0=-0.85, y0=1.5, x1=0.85, y1=3.5, line=dict(color="White", width=4))
                    # Internal 9-Segment Grid Lines (Grey dashed lines)
                    fig.add_shape(type="line", x0=-0.28, y0=1.5, x1=-0.28, y1=3.5, line=dict(color="Gray", width=1, dash="dash"))
                    fig.add_shape(type="line", x0=0.28, y0=1.5, x1=0.28, y1=3.5, line=dict(color="Gray", width=1, dash="dash"))
                    fig.add_shape(type="line", x0=-0.85, y0=2.16, x1=0.85, y1=2.16, line=dict(color="Gray", width=1, dash="dash"))
                    fig.add_shape(type="line", x0=-0.85, y0=2.83, x1=0.85, y1=2.83, line=dict(color="Gray", width=1, dash="dash"))
                    
                    fig.update_layout(template="plotly_dark", xaxis=dict(range=[-2,2], visible=False), yaxis=dict(range=[0,5], visible=False), height=500, margin=dict(l=0,r=0,t=0,b=0))
                    st.plotly_chart(fig, use_container_width=True)

            with tab2:
                st.write(f"### Sequence Matrix vs {split}HH")
                seq_df = df_p[df_p['Prev'] != "None"]
                if not seq_df.empty:
                    st.table((pd.crosstab(seq_df['Prev'], seq_df['Type'], normalize='index') * 100).style.format("{:.1f}%"))
                
                st.write("### Times Through Order")
                df_p['Order'] = df_p['Batter_Num'].apply(lambda n: "1st" if n<=9 else "2nd" if n<=18 else "3rd+")
                st.table((pd.crosstab(df_p['Order'], df_p['Type'], normalize='index') * 100).style.format("{:.0f}%"))
