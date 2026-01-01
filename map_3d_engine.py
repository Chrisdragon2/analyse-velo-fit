import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np

def check_mapbox_api_key():
    if "MAPBOX_API_KEY" not in st.secrets:
        st.error("Clé API Mapbox non trouvée.")
        return False, None
    return True, st.secrets["MAPBOX_API_KEY"]

def prepare_segment_data(segments, required_cols):
    path_data_list = []
    for segment in segments:
        if not all(col in segment.columns for col in required_cols):
            continue
        segment_map = segment[required_cols].dropna().copy()
        segment_map = segment_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
        if not segment_map.empty:
            segment_sampled = segment_map.iloc[::2, :] 
            path_data_list.append({
                "path": segment_sampled[['lon', 'lat', 'altitude']].values.tolist()
            })
    return path_data_list

def create_pydeck_chart(df, climb_segments, sprint_segments, selected_point_data=None):
    
    key_ok, MAPBOX_KEY = check_mapbox_api_key()
    if not key_ok: return None

    required_cols_main = ['position_lat', 'position_long', 'altitude']
    if not all(col in df.columns for col in required_cols_main): return None
    
    df_map = df[required_cols_main].dropna().copy()
    df_map = df_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
    if df_map.empty: return None
        
    sampling_rate = max(1, len(df_map) // 5000) 
    df_sampled = df_map.iloc[::sampling_rate, :]

    # --- 1. COUCHE SATELLITE (ID FIXE = PAS DE RECHARGEMENT) ---
    satellite_layer = pdk.Layer(
        "TileLayer",
        id="satellite-layer",  # <--- LE SECRET EST ICI
        data="https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}@2x.jpg?access_token=" + MAPBOX_KEY,
        min_zoom=0,
        max_zoom=19,
        tileSize=512,
    )
    
    # --- 2. TRACE DU PARCOURS ---
    path_data_main = [{"path": df_sampled[['lon', 'lat', 'altitude']].values.tolist(), "name": "Trace Complète"}]
    layer_main = pdk.Layer(
        'PathLayer',
        id="main-track-layer", # <--- ID FIXE
        data=path_data_main, 
        get_color=[255, 69, 0, 200], 
        width_min_pixels=3, 
        get_path='path', 
        get_width=5,
        parameters={"depthTest": False} 
    )
    
    # --- 3. COUCHES SPECIFIQUES ---
    path_data_climbs = prepare_segment_data(climb_segments, required_cols_main)
    layer_climbs = pdk.Layer(
        'PathLayer', 
        id="climbs-layer", # <--- ID FIXE
        data=path_data_climbs, 
        get_color=[255, 0, 255, 255], 
        width_min_pixels=4, 
        get_path='path', 
        get_width=5,
        parameters={"depthTest": False} 
    )
    
    path_data_sprints = prepare_segment_data(sprint_segments, required_cols_main)
    layer_sprints = pdk.Layer(
        'PathLayer', 
        id="sprints-layer", # <--- ID FIXE
        data=path_data_sprints, 
        get_color=[0, 255, 255, 255], 
        width_min_pixels=4, 
        get_path='path', 
        get_width=5,
        parameters={"depthTest": False} 
    )

    all_layers = [satellite_layer, layer_main, layer_climbs, layer_sprints]
    
    # --- 4. LE POINT ROUGE ET LA CAMÉRA ---
    view_state = None
    
    if selected_point_data is not None:
        pt_lat = selected_point_data['position_lat']
        pt_lon = selected_point_data['position_long']
        
        point_data = [{"position": [pt_lon, pt_lat], "name": "Cycliste"}]
        point_layer = pdk.Layer(
            "ScatterplotLayer",
            id="cyclist-marker", # <--- ID FIXE IMPORTANTE
            data=point_data,
            get_position="position",
            get_radius=30, 
            get_fill_color=[255, 0, 0, 255], 
            get_line_color=[255, 255, 255, 255],
            stroked=True,
            line_width_min_pixels=2,
            # transition={"get_position": 50} # Petite interpolation pour fluidifier (optionnel)
        )
        all_layers.append(point_layer)

        view_state = pdk.ViewState(
            latitude=pt_lat, 
            longitude=pt_lon, 
            zoom=14,       
            pitch=0,       
            bearing=0      
        )
    else:
        view_state = pdk.ViewState(
            latitude=df_sampled['lat'].mean(), 
            longitude=df_sampled['lon'].mean(), 
            zoom=11, 
            pitch=0, 
            bearing=0
        )

    deck = pdk.Deck(
        layers=all_layers,
        initial_view_state=view_state,
        tooltip={"text": "{name}"},
        api_keys={'mapbox': MAPBOX_KEY}, 
        map_provider='mapbox',
        map_style="" 
    )
    
    return deck
