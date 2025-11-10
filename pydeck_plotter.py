# pydeck_plotter.py
import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np

def create_pydeck_chart(df, climb_segments, sprint_segments):
    """
    Crée une carte 3D inclinée de la trace GPS en utilisant Pydeck
    AVEC surbrillance (Montées en ROUGE, Sprints en CYAN).
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
    
    # Couche 1: Trace Principale (Blanche/Grise)
    path_data_main = [
        {"path": df_sampled[['lon', 'lat', 'altitude']].values.tolist(), "name": "Trace Complète"}
    ]
    
    # Couche 2: Segments de Montée (Rouge)
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
            
    # Couche 3: Segments de Sprint (Cyan)
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
    
    # Couche 1: Trace Principale (Couleur neutre)
    layer_main = pdk.Layer(
        'PathLayer',
        data=path_data_main,
        pickable=True,
        get_color=[250, 250, 250, 255], # Blanc, semi-transparent (ou [100, 100, 100, 80] pour du gris)
        width_scale=1,
        width_min_pixels=2, # Ligne fine
        get_path='path',
        get_width=5,
        tooltip={"text": "{name}"}
    )
    
    # Couche 2: Montées (Rouge, plus large)
    layer_climbs = pdk.Layer(
        'PathLayer',
        data=path_data_climbs,
        pickable=True,
        get_color=[255, 0, 0, 255], # Rouge vif
        width_scale=1,
        width_min_pixels=5, # Plus épais pour surligner
        get_path='path',
        get_width=5,
        tooltip={"text": "{name}"}
    )
    
    # Couche 3: Sprints (Cyan, plus large)
    layer_sprints = pdk.Layer(
        'PathLayer',
        data=path_data_sprints,
        pickable=True,
        get_color=[0, 191, 255, 255],
        width_scale=1,
        width_min_pixels=5, # Plus épais pour surligner
        get_path='path',
        get_width=5,
        tooltip={"text": "{name}"}
    )

    # --- 6. Création de la carte Pydeck (Ordre Corrigé) ---
    deck = pdk.Deck(
        layers=[
            layer_main,     # 1. Trace de base (en dessous)
            layer_climbs,   # 2. Montées (au-dessus)
            layer_sprints   # 3. Sprints (tout au-dessus)
        ],
        initial_view_state=initial_view_state,
        map_style=pdk.map_styles.DARK
    )
    
    return deck
