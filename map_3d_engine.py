import streamlit as st
import pydeck as pdk
import pandas as pd

# --- CONSTANTES POUR LE RELIEF ET LA TEXTURE ---
TERRARIUM_ELEVATION_TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
ELEVATION_DECODER_TERRARIUM = {"rScaler": 256, "gScaler": 1, "bScaler": 1 / 256, "offset": -32768}

def check_mapbox_api_key():
    """Vérifie la présence de la clé Mapbox."""
    if "MAPBOX_API_KEY" not in st.secrets:
        st.error("Clé API Mapbox non trouvée.")
        return False, None
    return True, st.secrets["MAPBOX_API_KEY"]

def prepare_segment_data(segments, required_cols):
    """Prépare les segments pour l'affichage."""
    path_data_list = []
    if segments is None:
        return path_data_list
    for segment in segments:
        if not all(col in segment.columns for col in required_cols):
            continue
        segment_map = segment[required_cols].dropna().copy()
        segment_map = segment_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
        if not segment_map.empty:
            path_data_list.append({
                "path": segment_map[['lon', 'lat', 'altitude']].values.tolist()
            })
    return path_data_list

def create_pydeck_chart(df, climb_segments, sprint_segments, selected_point_data=None):
    """Crée la carte Pydeck 3D."""
    key_ok, MAPBOX_KEY = check_mapbox_api_key()
    if not key_ok:
        return None

    required_cols_main = ['position_lat', 'position_long', 'altitude']
    if not all(col in df.columns for col in required_cols_main):
        return None
    
    df_map = df[required_cols_main].dropna().copy()
    df_map = df_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
    
    sampling_rate = max(1, len(df_map) // 8000) 
    df_sampled = df_map.iloc[::sampling_rate, :]

    TERRAIN_TEXTURE_TILE_URL = f"https://api.mapbox.com/v4/mapbox.satellite/{{z}}/{{x}}/{{y}}@2x.jpg?access_token={MAPBOX_KEY}"

    # 1. COUCHES FIXES
    terrain_layer = pdk.Layer(
        "TerrainLayer",
        id="terrain_layer_3d",
        elevation_decoder=ELEVATION_DECODER_TERRARIUM,
        elevation_data=TERRARIUM_ELEVATION_TILE_URL,
        texture=TERRAIN_TEXTURE_TILE_URL, 
    )
    
    layer_main = pdk.Layer(
        'PathLayer', 
        id="main_track_layer",
        data=[{"path": df_sampled[['lon', 'lat', 'altitude']].values.tolist()}], 
        get_color=[255, 69, 0, 255], 
        width_min_pixels=3,
        get_path='path'
    )
    
    all_layers = [terrain_layer, layer_main]

    # 2. GESTION DU POINT ET DE LA CAMÉRA
    if selected_point_data is not None:
        pt_lat = selected_point_data['position_lat']
        pt_lon = selected_point_data['position_long']
        pt_alt = selected_point_data['altitude']

        # Point du cycliste
        point_layer = pdk.Layer(
            "ScatterplotLayer",
            id="cyclist_marker",
            data=[{"position": [pt_lon, pt_lat, pt_alt + 15]}],
            get_position="position",
            get_radius=50, 
            get_fill_color=[255, 0, 0, 255], 
            get_line_color=[255, 255, 255, 255],
            stroked=True,
            transitions={"get_position": 150} 
        )
        all_layers.append(point_layer)

        # Caméra
        view_state = pdk.ViewState(
            latitude=pt_lat, 
            longitude=pt_lon, 
            zoom=14, 
            pitch=60,       
            bearing=140,
            transition_duration=150 
        )
    else:
        view_state = pdk.ViewState(
            latitude=df_sampled['lat'].mean(), 
            longitude=df_sampled['lon'].mean(), 
            zoom=11, 
            pitch=60, 
            bearing=140
        )

    return pdk.Deck(
        layers=all_layers,
        initial_view_state=view_state,
        api_keys={'mapbox': MAPBOX_KEY}, 
        map_provider='mapbox',
        map_style='mapbox://styles/mapbox/satellite-v9' 
    )
