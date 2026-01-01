import streamlit as st
import pydeck as pdk
import pandas as pd

# --- CONSTANTES ---
TERRARIUM_ELEVATION_TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
ELEVATION_DECODER_TERRARIUM = {"rScaler": 256, "gScaler": 1, "bScaler": 1 / 256, "offset": -32768}

def prepare_segment_data(segments):
    """Prépare les segments (montées/sprints) pour Pydeck."""
    path_data = []
    if not segments:
        return path_data
    for seg in segments:
        # On extrait lon, lat, alt et on enlève les lignes vides
        df_coords = seg[['position_long', 'position_lat', 'altitude']].dropna()
        if not df_coords.empty:
            path_data.append({"path": df_coords.values.tolist()})
    return path_data

def create_pydeck_chart(df, climb_segments, sprint_segments, selected_point_data=None):
    if "MAPBOX_API_KEY" not in st.secrets:
        st.error("Clé Mapbox manquante dans les secrets.")
        return None
    
    token = st.secrets["MAPBOX_API_KEY"]

    # 1. Préparation de la trace principale (Orange)
    df_main = df[['position_long', 'position_lat', 'altitude']].dropna()
    sampling = max(1, len(df_main) // 8000)
    main_path = [{"path": df_main.iloc[::sampling].values.tolist()}]

    # --- LISTE DES COUCHES ---
    layers = [
        # Relief 3D (Texture satellite)
        pdk.Layer("TerrainLayer", id="terrain", elevation_decoder=ELEVATION_DECODER_TERRARIUM, 
                  elevation_data=TERRARIUM_ELEVATION_TILE_URL, 
                  texture=f"https://api.mapbox.com/v4/mapbox.satellite/{{z}}/{{x}}/{{y}}@2x.jpg?access_token={token}"),
        # Trace Orange (Parcours complet)
        pdk.Layer("PathLayer", id="track", data=main_path, get_path="path",
                  get_color=[255, 69, 0, 255], width_min_pixels=3)
    ]

    # 2. Ajout des Montées (Rose)
    data_climbs = prepare_segment_data(climb_segments)
    if data_climbs:
        layers.append(pdk.Layer("PathLayer", id="climbs-3d", data=data_climbs,
                                get_path="path", get_color=[255, 0, 255, 255], width_min_pixels=5))

    # 3. Ajout des Sprints (Cyan)
    data_sprints = prepare_segment_data(sprint_segments)
    if data_sprints:
        layers.append(pdk.Layer("PathLayer", id="sprints-3d", data=data_sprints,
                                get_path="path", get_color=[0, 255, 255, 255], width_min_pixels=5))

    # 4. Point Cycliste (Rouge) et Caméra
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

    return pdk.Deck(layers=layers, initial_view_state=view_state, 
                    map_style="mapbox://styles/mapbox/satellite-v9", api_keys={"mapbox": token})
