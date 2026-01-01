import streamlit as st
import pydeck as pdk
import pandas as pd

TERRARIUM_ELEVATION_TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
ELEVATION_DECODER_TERRARIUM = {"rScaler": 256, "gScaler": 1, "bScaler": 1 / 256, "offset": -32768}

def prepare_segment_data(segments):
    """Prépare une liste de DataFrames pour Pydeck PathLayer."""
    path_data = []
    if not segments:
        return path_data
    for seg in segments:
        # Nettoyage et extraction des coordonnées
        df_coords = seg[['position_long', 'position_lat', 'altitude']].dropna()
        if not df_coords.empty:
            path_data.append({"path": df_coords.values.tolist()})
    return path_data

def create_pydeck_chart(df, climb_segments, sprint_segments, selected_point_data=None):
    if "MAPBOX_API_KEY" not in st.secrets:
        st.error("Clé Mapbox manquante")
        return None
    
    token = st.secrets["MAPBOX_API_KEY"]

    # --- DEBUG : On vérifie si les segments arrivent ---
    with st.sidebar:
        st.write(f"DEBUG Carte : {len(climb_segments) if climb_segments else 0} montées reçues")

    # 1. Trace principale
    df_main = df[['position_long', 'position_lat', 'altitude']].dropna()
    sampling = max(1, len(df_main) // 8000)
    main_path = [{"path": df_main.iloc[::sampling].values.tolist()}]

    layers = [
        # Relief 3D
        pdk.Layer("TerrainLayer", id="terrain", elevation_decoder=ELEVATION_DECODER_TERRARIUM, 
                  elevation_data=TERRARIUM_ELEVATION_TILE_URL, 
                  texture=f"https://api.mapbox.com/v4/mapbox.satellite/{{z}}/{{x}}/{{y}}@2x.jpg?access_token={token}"),
        # Trace Orange
        pdk.Layer("PathLayer", id="track", data=main_path, get_path="path",
                  get_color=[255, 69, 0, 255], width_min_pixels=3)
    ]

    # 2. Ajout des Montées (Rose)
    if climb_segments and len(climb_segments) > 0:
        layers.append(pdk.Layer("PathLayer", id="climbs-3d", data=prepare_segment_data(climb_segments),
                                get_path="path", get_color=[255, 0, 255, 255], width_min_pixels=5))

    # 3. Ajout des Sprints (Cyan)
    if sprint_segments and len(sprint_segments) > 0:
        layers.append(pdk.Layer("PathLayer", id="sprints-3d", data=prepare_segment_data(sprint_segments),
                                get_path="path", get_color=[0, 255, 255, 255], width_min_pixels=5))

    # 4. Point Cycliste et Caméra
    if selected_point_data is not None:
        pt = selected_point_data
        layers.append(pdk.Layer("ScatterplotLayer", id="cyclist",
                                data=[{"pos": [pt['position_long'], pt['position_lat'], pt['altitude'] + 15]}],
                                get_position="pos", get_radius=60, get_fill_color=[255, 0, 0, 255],
                                transitions={"get_position": 150}))
        
        view_state = pdk.ViewState(latitude=pt['position_lat'], longitude=pt['position_long'], 
                                   zoom=14, pitch=60, bearing=140, transition_duration=150)
    else:
        view_state = pdk.ViewState(latitude=df_main['position_lat'].mean(), 
                                   longitude=df_main['position_long'].mean(), 
                                   zoom=12, pitch=40)

    return pdk.Deck(layers=layers, initial_view_state=view_state, map_style="mapbox://styles/mapbox/satellite-v9", api_keys={"mapbox": token})
