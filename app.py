import streamlit as st
import requests
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide", page_title="Dugout Pitch Tracker Pro")

st.title("⚾ Pro Pitch Strategy & Trends")
url_input = st.text_input("Paste MLB/MiLB Gameday URL:", placeholder="https://www.mlb.com/gameday/745301")

def get_game_pk(url):
    try: return url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
    except: return None

if url_input:
    game_pk = get_game_pk(url_input)
    if game_pk:
        api_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
        data = requests.get(api_url).json()
        all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])
        
        pitch_data = []
        batter_count_in_game = 0
        
        for play in all_plays:
            batter_count_in_game += 1
            prev_pitch_type = "None (First)"
            
            for event in play.get('playEvents', []):
                if event.get('isPitch'):
                    p_type = event.get('details', {}).get('type', {}).get('description', 'Unknown')
                    coords = event.get('pitchData', {}).get('coordinates', {})
                    
                    pitch_data.append({
                        "Pitcher": play['matchup']['pitcher']['fullName'],
                        "Type": p_type,
                        "Prev_Type": prev_pitch_type,
                        "Count": f"{event.get('count', {}).get('balls')}-{event.get('count', {}).get('strikes')}",
                        "X": coords.get('pX'), "Z": coords.get('pZ'),
                        "Inning": play['about']['inning'],
                        "Batter_Num": batter_count_in_game
                    })
                    prev_pitch_type = p_type # Update for next pitch in sequence

        df = pd.DataFrame(pitch_data)

        if not df.empty:
            st.sidebar.header("Dugout Controls")
            pitcher = st.sidebar.selectbox("Pitcher", df['Pitcher'].unique())
            df_p = df[df['Pitcher'] == pitcher].copy()

            # --- 1. TIMES THROUGH ORDER LOGIC ---
            # Approximating: 1-9 (1st), 10-18 (2nd), 19+ (3rd)
            def get_order(n):
                if n <= 9: return "1st Time"
                elif n <= 18: return "2nd Time"
                else: return "3rd+ Time"
            df_p['Order'] = df_p['Batter_Num'].apply(get_order)

            # --- TABS FOR ORGANIZATION ---
            tab1, tab2, tab3 = st.tabs(["📍 Locations", "📈 Sequences", "🕒 Thru Order"])

            with tab1:
                col_a, col_b = st.columns([1, 2])
                with col_a:
                    st.write("### Usage by Count")
                    count_table = pd.crosstab(df_p['Count'], df_p['Type'], normalize='index') * 100
                    st.dataframe(count_table.style.format("{:.0f}%"))
                with col_b:
                    st.write("### Zone Chart")
                    fig = px.scatter(df_p, x='X', y='Z', color='Type', range_x=[-2,2], range_y=[0,5])
                    fig.add_shape(type="rect", x0=-0.85, y0=1.5, x1=0.85, y1=3.5, line=dict(color="White"))
                    st.plotly_chart(fig)

            with tab2:
                st.write("### Following Pitch Patterns")
                st.info("What does he throw after a specific pitch? (Sequence Logic)")
                # Filter out 'None' for sequences
                seq_df = df_p[df_p['Prev_Type'] != "None (First)"]
                seq_table = pd.crosstab(seq_df['Prev_Type'], seq_df['Type'], normalize='index') * 100
                st.table(seq_table.style.format("{:.1f}%"))

            with tab3:
                st.write("### Usage: Times Through the Order")
                order_table = pd.crosstab(df_p['Order'], df_p['Type'], normalize='index') * 100
                st.bar_chart(order_table)
                st.dataframe(order_table.style.format("{:.0f}%"))
