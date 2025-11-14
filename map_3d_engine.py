import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np

# Constantes AWS
TERRARIUM_ELEVATION_TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
ELEVATION_DECODER_TERRARIUM = {"rScaler": 256, "gScaler": 1, "bScaler": 1 / 256, "offset": -32768}


# ... (check_mapbox_api_key inchangée) ...
def check_mapbox_api_key():
    if "MAPBOX_API_KEY" not in st.secrets:
        st.error("Clé API Mapbox non trouvée.")
        return False, None
    return True, st.secrets["MAPBOX_API_KEY"]

# ... (prepare_segment_data inchangée, toujours avec depthTest: False) ...
def prepare_segment_data(segments, required_cols):
    path_data_list = []
    for segment in segments:
        if not all(col in segment.columns for col in required_cols):
            continue
        segment_map = segment[required_cols].dropna().copy()
        segment_map = segment_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
        if not segment_map.empty:
            sampling_rate_seg = 1 
            segment_sampled = segment_map.iloc[::sampling_rate_seg, :]
            path_data_list.append({
                "path": segment_sampled[['lon', 'lat', 'altitude']].values.tolist()
            })
    return path_data_list

# --- MODIFICATION 1 : Accepter le point sélectionné ---
def create_pydeck_chart(df, climb_segments, sprint_segments, selected_point_data=None):
    
    key_ok, MAPBOX_KEY = check_mapbox_api_key()
    if not key_ok: return None

    # ... (logique de préparation de df_sampled inchangée) ...
    required_cols_main = ['position_lat', 'position_long', 'altitude']
    if not all(col in df.columns for col in required_cols_main):
        st.warning("Données de trace principale manquantes.")
        return None
    df_map = df[required_cols_main].dropna().copy()
    df_map = df_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
    if df_map.empty:
        st.warning("Données GPS/Altitude invalides."); return None
    sampling_rate = max(1, len(df_map) // 10000) 
    df_sampled = df_map.iloc[::sampling_rate, :]

    # --- URLS ---
    TERRAIN_ELEVATION_TILE_URL = TERRARIUM_ELEVATION_TILE_URL
    TERRAIN_TEXTURE_TILE_URL = f"https://api.mapbox.com/v4/mapbox.satellite/{{z}}/{{x}}/{{y}}@2x.jpg?access_token={MAPBOX_KEY}"


    # --- COUCHES DE BASE ---
    terrain_layer = pdk.Layer(
        "TerrainLayer",
        elevation_decoder=ELEVATION_DECODER_TERRARIUM,
        elevation_data=TERRAIN_ELEVATION_TILE_URL,
        texture=TERRAIN_TEXTURE_TILE_URL, 
        min_zoom=0,
        max_zoom=15 
    )
    
    path_data_main = [{"path": df_sampled[['lon', 'lat', 'altitude']].values.tolist(), "name": "Trace Complète"}]
    layer_main = pdk.Layer(
        'PathLayer', 
        data=path_data_main, 
        get_color=[255, 69, 0, 255], 
        width_min_pixels=3, 
        get_path='path', 
        get_width=5,
        parameters={"depthTest": False} 
    )
    
    path_data_climbs = prepare_segment_data(climb_segments, required_cols_main)
    layer_climbs = pdk.Layer(
        'PathLayer', 
        data=path_data_climbs, 
        get_color=[255, 0, 255, 255], 
        width_min_pixels=5, 
        get_path='path', 
        get_width=5,
        parameters={"depthTest": False} 
    )
    
    path_data_sprints = prepare_segment_data(sprint_segments, required_cols_main)
    layer_sprints = pdk.Layer(
        'PathLayer', 
        data=path_data_sprints, 
        get_color=[0, 255, 255, 255], 
        width_min_pixels=5, 
        get_path='path', 
        get_width=5,
        parameters={"depthTest": False} 
    )

    # Liste de toutes les couches
    all_layers = [terrain_layer, layer_main, layer_climbs, layer_sprints]
    
    # --- MODIFICATION 2 : Ajouter la couche du point sélectionné ---
    if selected_point_data is not None:
        # On surélève le point de 20m pour être sûr qu'il soit visible au-dessus du sol
        point_data = [{
            "position": [
                selected_point_data['position_long'], 
                selected_point_data['position_lat'], 
                selected_point_data['altitude'] + 20
            ],
            "name": "Position Actuelle"
        }]
        
        point_layer = pdk.Layer(
            "ScatterplotLayer",
            data=point_data,
            get_position="position",
            get_radius=50, # 50 mètres de rayon
            get_fill_color=[255, 0, 0, 255], # Rouge vif
            pickable=True,
            tooltip={"text": "{name}"}
        )
        all_layers.append(point_layer) # Ajoute le point à la carte

    # --- VUE ---
    mid_lat = df_sampled['lat'].mean()
    mid_lon = df_sampled['lon'].mean()
    
    initial_view_state = pdk.ViewState(
        latitude=mid_lat, 
        longitude=mid_lon, 
        zoom=11, 
        pitch=60, 
        bearing=140
    )

    # --- CARTE PYDECK FINALE ---
    deck = pdk.Deck(
        layers=all_layers, # <--- Utilise la liste dynamique de couches
        initial_view_state=initial_view_state,
        tooltip={"text": "{name}"}, # Tooltip par défaut (pour le point)
        api_keys={'mapbox': MAPBOX_KEY}, 
        map_provider='mapbox',
        map_style='mapbox://styles/mapbox/satellite-v9' 
    )
    
    return deck
