# pydeck_plotter.py (VERSION CORRIGÉE POUR UN BEAU TRACÉ PRINCIPAL)
import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np

# Fonction pour vérifier la clé API
def check_mapbox_api_key():
    if "MAPBOX_API_KEY" not in st.secrets:
        st.error("Clé API Mapbox non trouvée dans les secrets.")
        st.info("Veuillez ajouter 'MAPBOX_API_KEY = \"votre_clé\"' à vos secrets Streamlit.")
        return False, None
    return True, st.secrets["MAPBOX_API_KEY"]

# Fonction pour préparer les segments (montées ou sprints)
def prepare_segment_data(segments, required_cols):
    """Convertit une liste de DataFrames de segment en une liste de données pour Pydeck."""
    path_data_list = []
    for segment in segments:
        if not all(col in segment.columns for col in col in required_cols):
            continue # Ignorer ce segment s'il manque des données
            
        segment_map = segment[required_cols].dropna().copy()
        segment_map = segment_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
        
        if not segment_map.empty:
            path_data_list.append({
                "path": segment_map[['lon', 'lat', 'altitude']].values.tolist()
            })
    return path_data_list

def create_pydeck_chart(df, climb_segments, sprint_segments):
    """
    Crée une carte 3D inclinée de la trace GPS en utilisant Pydeck
    AVEC l'altitude, le fond de carte satellite Mapbox, ET les highlights.
    """
    
    # --- 0. Vérifier la clé API ---
    key_ok, MAPBOX_KEY = check_mapbox_api_key()
    if not key_ok:
        return None # Arrêter si la clé n'est pas là

    # --- 1. Vérification des données ---
    required_cols = ['position_lat', 'position_long', 'altitude']
    if not all(col in df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df.columns]
        st.warning(f"Données de trace principale manquantes ({', '.join(missing)})")
        return None
        
    df_map = df[required_cols].dropna().copy()
    df_map = df_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
    
    if df_map.empty:
        st.warning("Données GPS/Altitude invalides pour la carte 3D."); return None
        
    # --- 2. Échantillonnage de la trace principale ---
    # !! CHANGEMENT 1: Réduire l'agressivité de l'échantillonnage pour la trace principale
    # max(1, len(df_map) // 5000) était trop élevé pour des traces fines.
    # On met une limite plus basse pour garder plus de points, ou même pas d'échantillonnage si petite trace.
    sampling_rate = max(1, len(df_map) // 1000) # Ex: si 1000 points, sampling_rate=1 (pas d'échantillonnage)
                                               # si 10000 points, sampling_rate=10
    df_sampled = df_map.iloc[::sampling_rate, :].copy()

    # --- 3. Création des couches (Layers) ---
    layers = []

    # Couche 1: La trace principale
    path_data_main = [{
        "path": df_sampled[['lon', 'lat', 'altitude']].values.tolist(),
        "name": "Trace Complète"
    }]
    layers.append(pdk.Layer(
        'PathLayer',
        data=path_data_main,
        pickable=True,
        # !! CHANGEMENT 2: Couleur de la trace principale (plus foncée, moins transparente)
        get_color=[255, 100, 0, 200], # Orange vif, opacité 200 (sur 255)
        width_scale=10, 
        width_min_pixels=2,
        get_path='path',
        get_width=5,
        tooltip={"text": "{name}"}
    ))

    # Couche 2: Les Montées (en rouge vif)
    if climb_segments:
        climb_path_data = prepare_segment_data(climb_segments, required_cols)
        if climb_path_data:
            layers.append(pdk.Layer(
                'PathLayer',
                data=climb_path_data,
                pickable=True,
                get_color=[255, 0, 0, 255], # Rouge vif, entièrement opaque
                width_scale=10, 
                width_min_pixels=3, 
                get_path='path',
                get_width=5,
                tooltip={"text": "Montée"}
            ))

    # Couche 3: Les Sprints (en cyan vif)
    if sprint_segments:
        sprint_path_data = prepare_segment_data(sprint_segments, required_cols)
        if sprint_path_data:
            layers.append(pdk.Layer(
                'PathLayer',
                data=sprint_path_data,
                pickable=True,
                get_color=[0, 255, 255, 255], # Cyan vif, entièrement opaque
                width_scale=10, 
                width_min_pixels=3,
                get_path='path',
                get_width=5,
                tooltip={"text": "Sprint"}
            ))

    # --- 4. Centrage de la vue ---
    mid_lat = df_sampled['lat'].mean()
    mid_lon = df_sampled['lon'].mean()
    
    initial_view_state = pdk.ViewState(
        latitude=mid_lat,
        longitude=mid_lon,
        zoom=12,
        pitch=60, 
        bearing=0
    )

    # --- 5. Création de la carte Pydeck ---
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=initial_view_state,
        map_provider="mapbox",
        map_style=pdk.map_styles.SATELLITE, 
        api_keys={'mapbox': MAPBOX_KEY},
    )
    
    return deck
