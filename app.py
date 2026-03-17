import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# Set page to wide for dugout tablet viewing
st.set_page_config(layout="wide", page_title="Dugout Pitch Tracker")

st.title("⚾ Real-Time Pitch Usage & Location")
url_input = st.text_input("Paste MLB or MiLB Gameday URL:", placeholder="https://www.mlb.com/gameday/745301")

def get_game_pk(url):
    try:
        # Works for both mlb.com and milb.com structures
        return url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
    except:
        return None

if url_input:
    game_pk = get_game_pk(url_input)
    
    if game_pk:
        # MLB Stats API Endpoint
        api_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
        response = requests.get(api_url).json()
        
        # Extracting plays
        all_plays = response.get('liveData', {}).get('plays', {}).get('allPlays', [])
        
        pitch_data = []
        for play in all_plays:
            count = f"{play['atBatIndex']}: {play['count']['balls']}-{play['count']['strikes']}"
            # Extracting every pitch in the at-bat
            for pitch in play.get('playEvents', []):
                if pitch.get('isPitch'):
                    details = pitch.get('details', {})
                    coords = pitch.get('pitchData', {}).get('coordinates', {})
                    
                    pitch_data.append({
                        "Pitcher": play['matchup']['pitcher']['fullName'],
                        "Type": details.get('type', {}).get('description', 'Unknown'),
                        "Balls": pitch.get('count', {}).get('balls'),
                        "Strikes": pitch.get('count', {}).get('strikes'),
                        "X": coords.get('pX'), # Horizontal location
                        "Z": coords.get('pZ'), # Vertical location
                        "Runner_1B": play['matchup'].get('postOnFirst') is not None,
                        "Runner_2B": play['matchup'].get('postOnSecond') is not None,
                        "Runner_3B": play['matchup'].get('postOnThird') is not None
                    })

        df = pd.DataFrame(pitch_data)

        if not df.empty:
            # --- FILTERS ---
            st.sidebar.header("Dugout Filters")
            selected_pitcher = st.sidebar.selectbox("Select Pitcher", df['Pitcher'].unique())
            
            # Filter by Count
            count_filter = st.sidebar.multiselect("Filter by Count", 
                                                ["0-0", "0-1", "0-2", "1-0", "1-1", "1-2", "2-0", "2-1", "2-2", "3-0", "3-1", "3-2"],
                                                default=[])
            
            # Filter by Runners
            risp = st.sidebar.checkbox("Only RISP (Runners on 2nd or 3rd)")

            # Apply logic
            filtered_df = df[df['Pitcher'] == selected_pitcher]
            if count_filter:
                filtered_df = filtered_df[filtered_df.apply(lambda x: f"{x['Balls']}-{x['Strikes']}" in count_filter, axis=1)]
            if risp:
                filtered_df = filtered_df[(filtered_df['Runner_2B']) | (filtered_df['Runner_3B'])]

            # --- VISUALIZATION ---
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Pitch Usage")
                usage_chart = px.bar(filtered_df['Type'].value_counts().reset_index(), 
                                   x='Type', y='count', color='Type',
                                   labels={'count': 'Number of Pitches'})
                st.plotly_chart(usage_chart, use_container_width=True)

            with col2:
                st.subheader("Location (Catcher's View)")
                # Strike zone approximation
                location_map = px.scatter(filtered_df, x='X', y='Z', color='Type',
                                        range_x=[-2, 2], range_y=[0, 5],
                                        hover_data=['Balls', 'Strikes'])
                # Drawing a basic strike zone box
                location_map.add_shape(type="rect", x0=-0.85, y0=1.5, x1=0.85, y1=3.5,
                                      line=dict(color="White", width=2))
                st.plotly_chart(location_map, use_container_width=True)
                
        else:
            st.warning("No pitch data found yet. Is the game live?")
