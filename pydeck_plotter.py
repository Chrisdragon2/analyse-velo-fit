# pydeck_plotter.py
import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np

def create_pydeck_chart(df, climb_segments, sprint_segments):
    """
    Crée une carte 3D inclinée de la trace GPS en utilisant Pydeck
    AVEC surbrillance (Montées en ROSE, Sprints en CYAN).
    """
    
    # --- 1. Vérification des données ---
    required_cols = ['position_lat', 'position_long', 'altitude']
    if not all(col in df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df.columns]
        st.warning(f"Données manquantes ({', '.join(missing)}) pour la carte 3D.")
        return None
        
    df_map = df[required_cols].dropna().copy()
    df_map = df_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
    
    if df_map.empty:
        st.warning("Données GPS/Altitude invalides pour la carte 3D."); return None
        
    # --- 2. Échantillonnage (pour la trace principale) ---
    sampling_rate = max(1, len(df_map) // 5000)
    df_sampled = df_map.iloc[::sampling_rate, :].copy()

    # --- 3. Préparation des données pour les couches ---
    
    # Couche 1: Trace Principale
    path_data_main = [
        {"path": df_sampled[['lon', 'lat', 'altitude']].values.tolist(), "name": "Trace Complète"}
    ]
    
    # Couche 2: Segments de Montée
    path_data_climbs = []
    for segment in climb_segments:
        sampling_rate_seg = max(1, len(segment) // 500)
        segment_sampled = segment.iloc[::sampling_rate_seg, :]
        if not segment_sampled.empty and all(col in segment_sampled.columns for col in ['position_long', 'position_lat', 'altitude']):
            seg_renamed = segment_sampled.rename(columns={"position_lat": "lat", "position_long": "lon"})
            path_data_climbs.append({
                "path": seg_renamed[['lon', 'lat', 'altitude']].values.tolist(),
                "name": "Montée"
            })
            
    # Couche 3: Segments de Sprint
    path_data_sprints = []
    for segment in sprint_segments:
        sampling_rate_seg = max(1, len(segment) // 500)
        segment_sampled = segment.iloc[::sampling_rate_seg, :]
        if not segment_sampled.empty and all(col in segment_sampled.columns for col in ['position_long', 'position_lat', 'altitude']):
            seg_renamed = segment_sampled.rename(columns={"position_lat": "lat", "position_long": "lon"})
            path_data_sprints.append({
                "path": seg_renamed[['lon', 'lat', 'altitude']].values.tolist(),
                "name": "Sprint"
            })

    # --- 4. Centrage de la vue ---
    mid_lat = df_sampled['lat'].mean()
    mid_lon = df_sampled['lon'].mean()
    
    initial_view_state = pdk.ViewState(
        latitude=mid_lat,
        longitude=mid_lon,
        zoom=11,
        pitch=45,
        bearing=0
    )

    # --- 5. Définition des Couches (Layers) ---
    
    # --- MODIFIÉ : Couche 1 (Trace Principale) ---
    layer_main = pdk.Layer(
        'PathLayer',
        data=path_data_main,
        pickable=True,
        get_color=[255, 69, 0, 255], # Orange vif Opaque
        width_scale=1,
        width_min_pixels=3, # Ligne principale (épaisseur moyenne)
        get_path='path',
        get_width=5,
        tooltip={"text": "{name}"}
    )
    
    # --- MODIFIÉ : Couche 2 (Montées) ---
    layer_climbs = pdk.Layer(
        'PathLayer',
        data=path_data_climbs,
        pickable=True,
        get_color=[255, 0, 255, 255], # Rose / Magenta vif
        width_scale=1,
        width_min_pixels=5, # Plus épais pour surligner
        get_path='path',
        get_width=5,
        tooltip={"text": "{name}"}
    )
    
    # --- MODIFIÉ : Couche 3 (Sprints) ---
    layer_sprints = pdk.Layer(
        'PathLayer',
        data=path_data_sprints,
        pickable=True,
        get_color=[0, 255, 255, 255], # Cyan vif (Gardé)
        width_scale=1,
        width_min_pixels=5, # Plus épais pour surligner
        get_path='path',
        get_width=5,
        tooltip={"text": "{name}"}
    )

    # --- 6. Création de la carte Pydeck ---
    
    # Lire la clé depuis les secrets
    try:
        MAPBOX_KEY = st.secrets["MAPBOX_API_KEY"]
    except KeyError:
        st.error("Clé 'MAPBOX_API_KEY' non trouvée dans les secrets Streamlit !")
        return None
    except FileNotFoundError:
         st.error("Fichier secrets.toml non trouvé.")
         return None

    deck = pdk.Deck(
        layers=[
            layer_main,     # 1. Trace de base (Orange)
            layer_climbs,   # 2. Montées (Rose)
            layer_sprints   # 3. Sprints (Cyan)
        ],
        initial_view_state=initial_view_state,
        map_provider="mapbox",
        map_style=pdk.map_styles.SATELLITE, # Style satellite
        api_keys={'mapbox': MAPBOX_KEY},
        tooltip={"text": "{name}"}
    )
    
    return deck
