# pydeck_plotter.py
import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np

# Fonction pour vérifier la clé API Mapbox
def check_mapbox_api_key():
    if "MAPBOX_API_KEY" not in st.secrets:
        st.error("Clé API Mapbox non trouvée dans les secrets Streamlit.")
        st.info("Veuillez ajouter 'MAPBOX_API_KEY = \"votre_clé\"' à vos secrets Streamlit pour afficher la carte 3D.")
        return False, None
    return True, st.secrets["MAPBOX_API_KEY"]

# Fonction pour préparer les segments (montées ou sprints)
def prepare_segment_data(segments, required_cols):
    """Convertit une liste de DataFrames de segment en une liste de données pour Pydeck."""
    path_data_list = []
    for segment in segments:
        # Assurer que toutes les colonnes requises sont présentes dans le segment
        if not all(col in segment.columns for col in required_cols):
            # st.warning(f"Segment ignoré en raison de colonnes manquantes: {segment.columns}") # Décommenter pour debug
            continue
            
        segment_map = segment[required_cols].dropna().copy()
        segment_map = segment_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
        
        if not segment_map.empty:
            path_data_list.append({
                "path": segment_map[['lon', 'lat', 'altitude']].values.tolist()
            })
    return path_data_list

def create_pydeck_chart(df, climb_segments, sprint_segments):
    """
    Crée une carte 3D inclinée de la trace GPS ET du terrain réel
    en utilisant Pydeck avec la TerrainLayer de Mapbox.
    """
    
    # --- 0. Vérifier la clé API ---
    key_ok, MAPBOX_KEY = check_mapbox_api_key()
    if not key_ok:
        return None

    # --- 1. Vérification des données de la trace principale ---
    required_cols_main = ['position_lat', 'position_long', 'altitude']
    if not all(col in df.columns for col in required_cols_main):
        missing = [col for col in required_cols_main if col not in df.columns]
        st.warning(f"Données de trace principale manquantes ({', '.join(missing)}) pour la carte 3D.")
        return None
        
    df_map = df[required_cols_main].dropna().copy()
    df_map = df_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
    
    if df_map.empty:
        st.warning("Données GPS/Altitude invalides pour la carte 3D."); return None
        
    # --- 2. Échantillonnage de la trace principale ---
    sampling_rate = max(1, len(df_map) // 5000) # Échantillonne pour ne pas surcharger
    df_sampled = df_map.iloc[::sampling_rate, :].copy()

    # --- 3. Création des couches (Layers) ---
    
    # --- AJUSTEMENT DES URLS POUR LE TERRAIN 3D ---
    # Ces URLs construisent les tuiles d'élévation et de texture.
    # On utilise un paramètre 'tiles' pour Pydeck, plutôt que des URLs directes pour 'elevation_data' et 'texture'
    # et on passe les api_keys au niveau du Deck.
    
    # Pour elevation_data (le relief) - Utilise le terrain-rgb de Mapbox
    TERRAIN_ELEVATION_TILE_URL = f"https://api.mapbox.com/v4/mapbox.terrain-rgb/{{z}}/{{x}}/{{y}}.png?access_token={MAPBOX_KEY}"
    
    # Pour texture (l'image satellite) - Utilise le satellite de Mapbox
    TERRAIN_TEXTURE_TILE_URL = f"https://api.mapbox.com/v4/mapbox.satellite/{{z}}/{{x}}/{{y}}@2x.png?access_token={MAPBOX_KEY}"

    # Couche 0: Le Terrain 3D (fond de carte avec relief et image satellite)
    terrain_layer = pdk.Layer(
        "TerrainLayer",
        # Ces valeurs sont des constantes pour le format Mapbox Terrain-RGB
        elevation_decoder={"r_scale": 6553.6, "g_scale": 25.6, "b_scale": 0.1, "offset": -10000},
        
        # On passe les URLs des tuiles ici.
        # elevation_data et texture peuvent prendre des URLs de tuiles comme ça.
        elevation_data=TERRAIN_ELEVATION_TILE_URL,
        texture=TERRAIN_TEXTURE_TILE_URL,
        
        # Paramètres pour la couche de terrain
        min_zoom=0,
        max_zoom=15 # Zoom max pour les détails du terrain
    )

    # Couche 1: Trace Principale (ORANGE) - Plus visible
    path_data_main = [{"path": df_sampled[['lon', 'lat', 'altitude']].values.tolist(), "name": "Trace Complète"}]
    layer_main = pdk.Layer(
        'PathLayer',
        data=path_data_main,
        pickable=True,
        get_color=[255, 140, 0, 255], # Orange vif et opaque
        width_scale=1,
        width_min_pixels=3,          # Un peu plus épais
        get_path='path',
        get_width=5,
        tooltip={"text": "{name}"}
    )
    
    # Couche 2: Montées (ROSE / MAGENTA VIF) - Très visible
    path_data_climbs = prepare_segment_data(climb_segments, required_cols_main)
    layer_climbs = pdk.Layer(
        'PathLayer',
        data=path_data_climbs,
        pickable=True,
        get_color=[255, 0, 255, 255], # Rose / Magenta vif
        width_scale=1,
        width_min_pixels=5,          # Épais pour surligner
        get_path='path',
        get_width=5,
        tooltip={"text": "Montée"}
    )
    
    # Couche 3: Sprints (CYAN VIF) - Très visible
    path_data_sprints = prepare_segment_data(sprint_segments, required_cols_main)
    layer_sprints = pdk.Layer(
        'PathLayer',
        data=path_data_sprints,
        pickable=True,
        get_color=[0, 255, 255, 255], # Cyan vif
        width_scale=1,
        width_min_pixels=5,          # Épais pour surligner
        get_path='path',
        get_width=5,
        tooltip={"text": "Sprint"}
    )

    # --- 4. Centrage de la vue ---
    mid_lat = df_sampled['lat'].mean()
    mid_lon = df_sampled['lon'].mean()
    
    initial_view_state = pdk.ViewState(
        latitude=mid_lat,
        longitude=mid_lon,
        zoom=11, # Zoom un peu plus important pour voir le relief
        pitch=45,
        bearing=0
    )

    # --- 5. Création de la carte Pydeck ---
    deck = pdk.Deck(
        layers=[
            terrain_layer,  # Le terrain 3D avec image satellite (en premier)
            layer_main,     # La trace principale (au-dessus du terrain)
            layer_climbs,   # Les montées (au-dessus de la trace principale)
            layer_sprints   # Les sprints (tout au-dessus)
        ],
        initial_view_state=initial_view_state,
        
        # IMPORTANT : Quand on utilise TerrainLayer, on ne met PAS map_provider/map_style
        # car la TerrainLayer gère elle-même le fond de carte.
        # map_provider="mapbox", 
        # map_style=pdk.map_styles.SATELLITE, 
        
        api_keys={'mapbox': MAPBOX_KEY}, # La clé est toujours nécessaire pour les tuiles
        tooltip={"text": "{name}"},
        
        # --- Contrôles : Glisser pour pivoter ---
        # Cette ligne est essentielle pour que le glisser simple pivote la vue 3D
        controller={'dragRotate': True} 
    )
    
    return deck
