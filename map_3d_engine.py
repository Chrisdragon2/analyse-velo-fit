import streamlit as st
import pydeck as pdk
import pandas as pd

# --- CONSTANTES POUR LE RELIEF ET LA TEXTURE ---
# Utilisation des tuiles Terrarium pour l'élévation (relief 3D)
TERRARIUM_ELEVATION_TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
ELEVATION_DECODER_TERRARIUM = {"rScaler": 256, "gScaler": 1, "bScaler": 1 / 256, "offset": -32768}

def check_mapbox_api_key():
    """Vérifie la présence de la clé Mapbox dans les secrets Streamlit."""
    if "MAPBOX_API_KEY" not in st.secrets:
        st.error("Clé API Mapbox non trouvée dans .streamlit/secrets.toml")
        return False, None
    return True, st.secrets["MAPBOX_API_KEY"]

def prepare_segment_data(segments, required_cols):
    """Prépare les segments (montées/sprints) pour l'affichage en chemins (PathLayer)."""
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
    """Crée et configure la carte Pydeck 3D avec transitions fluides."""
    
    key_ok, MAPBOX_KEY = check_mapbox_api_key()
    if not key_ok:
        return None

    # 1. Nettoyage et préparation des données de base
    required_cols_main = ['position_lat', 'position_long', 'altitude']
    if not all(col in df.columns for col in required_cols_main):
        return None
    
    df_map = df[required_cols_main].dropna().copy()
    df_map = df_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
    
    # Échantillonnage pour garantir la performance (max 8000 points)
    sampling_rate = max(1, len(df_map) // 8000) 
    df_sampled = df_map.iloc[::sampling_rate, :]

    # URL pour la texture satellite Mapbox
    TERRAIN_TEXTURE_TILE_URL = f"https://api.mapbox.com/v4/mapbox.satellite/{{z}}/{{x}}/{{y}}@2x.jpg?access_token={MAPBOX_KEY}"

    # --- COUCHES DE LA CARTE ---
    
    # A. Couche de Terrain (Relief 3D)
    terrain_layer = pdk.Layer(
        "TerrainLayer",
        id="terrain_layer_3d",
        elevation_decoder=ELEVATION_DECODER_TERRARIUM,
        elevation_data=TERRARIUM_ELEVATION_TILE_URL,
        texture=TERRAIN_TEXTURE_TILE_URL, 
        min_zoom=0,
        max_zoom=15 
    )
    
    # B. Trace complète du parcours (Ligne orange)
    layer_main = pdk.Layer(
        'PathLayer', 
        id="main_track_layer",
        data=[{"path": df_sampled[['lon', 'lat', 'altitude']].values.tolist()}], 
        get_color=[255, 69, 0, 255], 
        width_min_pixels=3,
        get_path='path'
    )
    
    all_layers = [terrain_layer, layer_main]

    # C. Ajout des segments spécifiques (Montées en Rose / Sprints en Cyan)
    if climb_segments:
        path_climbs = prepare_segment_data(climb_segments, required_cols_main)
        all_layers.append(pdk.Layer(
            'PathLayer', id="climbs_layer", data=path_climbs,
            get_color=[255, 0, 255, 255], width_min_pixels=5, get_path='path'
        ))

    if sprint_segments:
        path_sprints = prepare_segment_data(sprint_segments, required_cols_main)
        all_layers.append(pdk.Layer(
            'PathLayer', id="sprints_layer", data=path_sprints,
            get_color=[0, 255, 255, 255], width_min_pixels=5, get_path='path'
        ))

    # --- GESTION DU POINT MOBILE ET DE LA CAMÉRA ---
    
    if selected_point_data is not None:
        pt_lat = selected_point_data['position_lat']
        pt_lon = selected_point_data['position_long']
        pt_alt = selected_point_data['altitude']

        # D. Le marqueur du cycliste (Point rouge)
        point_layer = pdk.Layer(
            "ScatterplotLayer",
            id="cyclist_marker",
            data=[{"position": [pt_lon, pt_lat, pt_alt + 15]}],
            get_position="position",
            get_radius=50, 
            get_fill_color=[255, 0, 0, 255], 
            get_line_color=[255, 255, 255, 255],
            stroked=True,
            line_width_min_pixels=2,
            # Transition pour que le point "glisse" au lieu de sauter
            transitions={"get_position": 150} 
        )
        all_layers.append(point_layer)

        # E. État de la vue (Caméra centrée sur le cycliste)
        view_state = pdk.ViewState(
            latitude=pt_lat, 
            longitude=pt_lon, 
            zoom=14, 
            pitch=60,       
            bearing=140,
            # Durée de transition pour un suivi de caméra fluide
            transition_duration=150 
        )
    else:
        # Vue par défaut au centre du parcours
        view_state = pdk.ViewState(
            latitude=df_sampled['lat'].mean(), 
            longitude=df_sampled['lon'].mean(), 
            zoom=11, 
            pitch=60, 
            bearing=140
        )

    # Création de l'objet Deck final
    return pdk.Deck(
        layers=all_layers,
        initial_view_state=view_state,
        api_keys={'mapbox': MAPBOX_KEY}, 
        map_provider='mapbox',
        map_style='mapbox://styles/mapbox/satellite-v9' 
    )
