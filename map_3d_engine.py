import streamlit as st
import pydeck as pdk
import pandas as pd

# --- CONSTANTES ---
TERRARIUM_ELEVATION_TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
ELEVATION_DECODER_TERRARIUM = {"rScaler": 256, "gScaler": 1, "bScaler": 1 / 256, "offset": -32768}

def check_mapbox_api_key():
    if "MAPBOX_API_KEY" not in st.secrets:
        st.error("Clé API Mapbox non trouvée.")
        return False, None
    return True, st.secrets["MAPBOX_API_KEY"]

def prepare_segment_data(segments, required_cols):
    """Transforme les listes de DataFrames en format lisible par Pydeck."""
    path_data_list = []
    if not segments:
        return path_data_list
    for segment in segments:
        if not all(col in segment.columns for col in required_cols):
            continue
        # On nettoie et on renomme pour Pydeck
        df_seg = segment[required_cols].dropna().copy()
        df_seg = df_seg.rename(columns={"position_lat": "lat", "position_long": "lon"})
        if not df_seg.empty:
            path_data_list.append({"path": df_seg[['lon', 'lat', 'altitude']].values.tolist()})
    return path_data_list

def create_pydeck_chart(df, climb_segments, sprint_segments, selected_point_data=None):
    key_ok, MAPBOX_KEY = check_mapbox_api_key()
    if not key_ok: return None

    required_cols = ['position_lat', 'position_long', 'altitude']
    
    # 1. Préparation de la trace principale (Orange)
    df_main = df[required_cols].dropna().copy().rename(columns={"position_lat": "lat", "position_long": "lon"})
    sampling = max(1, len(df_main) // 8000)
    df_sampled = df_main.iloc[::sampling, :]

    TERRAIN_TEXTURE = f"https://api.mapbox.com/v4/mapbox.satellite/{{z}}/{{x}}/{{y}}@2x.jpg?access_token={MAPBOX_KEY}"

    # --- COUCHES ---
    layers = [
        # Relief 3D
        pdk.Layer("TerrainLayer", id="terrain", elevation_decoder=ELEVATION_DECODER_TERRARIUM, 
                  elevation_data=TERRARIUM_ELEVATION_TILE_URL, texture=TERRAIN_TEXTURE),
        # Trace Orange
        pdk.Layer("PathLayer", id="track", data=[{"path": df_sampled[['lon', 'lat', 'altitude']].values.tolist()}],
                  get_color=[255, 69, 0, 255], width_min_pixels=3, get_path="path")
    ]

    # Ajout des Montées (Rose)
    if climb_segments:
        layers.append(pdk.Layer("PathLayer", id="climbs", data=prepare_segment_data(climb_segments, required_cols),
                                get_color=[255, 0, 255, 255], width_min_pixels=5, get_path="path"))

    # Ajout des Sprints (Cyan)
    if sprint_segments:
        layers.append(pdk.Layer("PathLayer", id="sprints", data=prepare_segment_data(sprint_segments, required_cols),
                                get_color=[0, 255, 255, 255], width_min_pixels=5, get_path="path"))

    # 2. Gestion du Cycliste (Point Rouge) et Caméra
    if selected_point_data is not None:
        pt = selected_point_data
        layers.append(pdk.Layer("ScatterplotLayer", id="cyclist", stroked=True,
                                data=[{"pos": [pt['position_long'], pt['position_lat'], pt['altitude'] + 15]}],
                                get_position="pos", get_radius=50, get_fill_color=[255, 0, 0, 255],
                                transitions={"get_position": 150}))
        
        view_state = pdk.ViewState(latitude=pt['position_lat'], longitude=pt['position_long'], 
                                   zoom=14, pitch=60, bearing=140, transition_duration=150)
    else:
        view_state = pdk.ViewState(latitude=df_sampled['lat'].mean(), longitude=df_sampled['lon'].mean(), 
                                   zoom=11, pitch=60, bearing=140)

    return pdk.Deck(layers=layers, initial_view_state=view_state, api_keys={'mapbox': MAPBOX_KEY},
                    map_provider='mapbox', map_style='mapbox://styles/mapbox/satellite-v9')
