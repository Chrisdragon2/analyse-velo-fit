# map_3d_engine.py
import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np

# Fonction pour vérifier la clé API Mapbox
def check_mapbox_api_key():
    if "MAPBOX_API_KEY" not in st.secrets:
        st.error("Clé API Mapbox non trouvée dans les secrets.")
        st.info("Veuillez ajouter 'MAPBOX_API_KEY = \"votre_clé\"' à vos secrets Streamlit.")
        return False, None
    return True, st.secrets["MAPBOX_API_KEY"]

# Fonction pour préparer les segments (montées ou sprints)
def prepare_segment_data(segments, required_cols):
    path_data_list = []
    for segment in segments:
        if not all(col in segment.columns for col in required_cols):
            continue
            
        segment_map = segment[required_cols].dropna().copy()
        segment_map = segment_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
        
        if not segment_map.empty:
            sampling_rate_seg = max(1, len(segment_map) // 500)
            segment_sampled = segment_map.iloc[::sampling_rate_seg, :]
            
            path_data_list.append({
                "path": segment_sampled[['lon', 'lat', 'altitude']].values.tolist()
            })
    return path_data_list

def create_pydeck_chart(df, climb_segments, sprint_segments):
    """
    Crée l'objet pdk.Deck avec toutes les couches (Terrain + Traces).
    """
    
    key_ok, MAPBOX_KEY = check_mapbox_api_key()
    if not key_ok: return None

    required_cols_main = ['position_lat', 'position_long', 'altitude']
    if not all(col in df.columns for col in required_cols_main):
        st.warning("Données de trace principale manquantes.")
        return None
        
    df_map = df[required_cols_main].dropna().copy()
    df_map = df_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
    
    if df_map.empty:
        st.warning("Données GPS/Altitude invalides."); return None
        
    sampling_rate = max(1, len(df_map) // 5000)
    df_sampled = df_map.iloc[::sampling_rate, :].copy()

    TERRAIN_ELEVATION_TILE_URL = f"https://api.mapbox.com/v4/mapbox.terrain-rgb/{{z}}/{{x}}/{{y}}.png?access_token={MAPBOX_KEY}"
    TERRAIN_TEXTURE_TILE_URL = f"https://api.mapbox.com/v4/mapbox.satellite/{{z}}/{{x}}/{{y}}@2x.png?access_token={MAPBOX_KEY}"

    # --- 4. Création des couches (Layers) ---
    terrain_layer = pdk.Layer(
        "TerrainLayer",
        elevation_decoder={"r_scale": 6553.6, "g_scale": 25.6, "b_scale": 0.1, "offset": -10000},
        elevation_data=TERRAIN_ELEVATION_TILE_URL,
        texture=TERRAIN_TEXTURE_TILE_URL,
        min_zoom=0
    )
    
    path_data_main = [{"path": df_sampled[['lon', 'lat', 'altitude']].values.tolist(), "name": "Trace Complète"}]
    layer_main = pdk.Layer(
        'PathLayer', data=path_data_main, pickable=True,
        get_color=[255, 69, 0, 255], width_scale=1,
        width_min_pixels=3, get_path='path', get_width=5,
        tooltip={"text": "Trace Complète"}
    )
    
    path_data_climbs = prepare_segment_data(climb_segments, required_cols_main)
    layer_climbs = pdk.Layer(
        'PathLayer', data=path_data_climbs, pickable=True,
        get_color=[255, 0, 255, 255], width_scale=1,
        width_min_pixels=5, get_path='path', get_width=5,
        tooltip={"text": "Montée"}
    )
    
    path_data_sprints = prepare_segment_data(sprint_segments, required_cols_main)
    layer_sprints = pdk.Layer(
        'PathLayer', data=path_data_sprints, pickable=True,
        get_color=[0, 255, 255, 255], width_scale=1,
        width_min_pixels=5, get_path='path', get_width=5,
        tooltip={"text": "Sprint"}
    )

    # --- 5. Centrage de la vue ---
    mid_lat = df_sampled['lat'].mean()
    mid_lon = df_sampled['lon'].mean()
    
    initial_view_state = pdk.ViewState(
        latitude=mid_lat,
        longitude=mid_lon,
        zoom=11,
        pitch=45,
        bearing=0
    )

    # --- 6. Création de la carte Pydeck (Stable) ---
    deck = pdk.Deck(
        layers=[
            terrain_layer,
            layer_main,
            layer_climbs,
            layer_sprints
        ],
        initial_view_state=initial_view_state, # On utilise initial_view_state
        api_keys={'mapbox': MAPBOX_KEY},
        tooltip={"text": "{name}"},
        map_style=None # Pour éviter le conflit de double carte
    )
    
    return deck
