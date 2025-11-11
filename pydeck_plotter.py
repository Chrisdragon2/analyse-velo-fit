# pydeck_plotter.py
import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np

def create_pydeck_chart(df, climb_segments, sprint_segments):
    """
    Crée une carte 3D inclinée (Contrôles Inversés : Glisser=Pivoter)
    et la retourne sous forme de HTML brut.
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
        
    # --- 2. Échantillonnage ---
    sampling_rate = max(1, len(df_map) // 5000)
    df_sampled = df_map.iloc[::sampling_rate, :].copy()

    # --- 3. Préparation des données pour les couches ---
    
    # Couche 1: Trace Principale (Orange)
    path_data_main = [{"path": df_sampled[['lon', 'lat', 'altitude']].values.tolist(), "name": "Trace Complète"}]
    
    # Couche 2: Segments de Montée (Rose)
    path_data_climbs = []
    for segment in climb_segments:
        sampling_rate_seg = max(1, len(segment) // 500)
        segment_sampled = segment.iloc[::sampling_rate_seg, :]
        if not segment_sampled.empty and all(col in segment_sampled.columns for col in ['position_long', 'position_lat', 'altitude']):
            seg_renamed = segment_sampled.rename(columns={"position_lat": "lat", "position_long": "lon"})
            path_data_climbs.append({"path": seg_renamed[['lon', 'lat', 'altitude']].values.tolist(), "name": "Montée"})
            
    # Couche 3: Segments de Sprint (Cyan)
    path_data_sprints = []
    for segment in sprint_segments:
        sampling_rate_seg = max(1, len(segment) // 500)
        segment_sampled = segment.iloc[::sampling_rate_seg, :]
        if not segment_sampled.empty and all(col in segment_sampled.columns for col in ['position_long', 'position_lat', 'altitude']):
            seg_renamed = segment_sampled.rename(columns={"position_lat": "lat", "position_long": "lon"})
            path_data_sprints.append({"path": seg_renamed[['lon', 'lat', 'altitude']].values.tolist(), "name": "Sprint"})

    # --- 4. Centrage de la vue ---
    mid_lat = df_sampled['lat'].mean()
    mid_lon = df_sampled['lon'].mean()
    
    initial_view_state = pdk.ViewState(latitude=mid_lat, longitude=mid_lon, zoom=11, pitch=45, bearing=0)

    # --- 5. Définition des Couches (Layers) ---
    
    layer_main = pdk.Layer('PathLayer', data=path_data_main, pickable=True, get_color=[255, 69, 0, 255], 
                           width_scale=1, width_min_pixels=3, get_path='path', get_width=5, tooltip={"text": "{name}"})
    
    layer_climbs = pdk.Layer('PathLayer', data=path_data_climbs, pickable=True, get_color=[255, 0, 255, 255], 
                             width_scale=1, width_min_pixels=5, get_path='path', get_width=5, tooltip={"text": "{name}"})
    
    layer_sprints = pdk.Layer('PathLayer', data=path_data_sprints, pickable=True, get_color=[0, 255, 255, 255], 
                              width_scale=1, width_min_pixels=5, get_path='path', get_width=5, tooltip={"text": "{name}"})

    # --- 6. Création de la carte Pydeck (AVEC Mapbox et Contrôles Inversés) ---
    
    try:
        MAPBOX_KEY = st.secrets["MAPBOX_API_KEY"]
    except KeyError:
        st.error("Clé 'MAPBOX_API_KEY' non trouvée dans les secrets Streamlit !")
        return None
    except FileNotFoundError:
         st.error("Fichier secrets.toml non trouvé.")
         return None

    deck = pdk.Deck(
        layers=[layer_main, layer_climbs, layer_sprints],
        initial_view_state=initial_view_state,
        map_provider="mapbox",
        map_style=pdk.map_styles.SATELLITE,
        api_keys={'mapbox': MAPBOX_KEY},
        
        # --- LA MODIFICATION IMPORTANTE ---
        # dragRotate=True signifie que le glisser simple = rotation/inclinaison
        controller={'dragRotate': True},
        # --- FIN MODIFICATION ---
        
        tooltip={"html": "<b>{name}</b>"} # Tooltip simple
    )
    
    # --- MODIFICATION : Générer le HTML ---
    try:
        # Génère le HTML complet dans une chaîne de caractères
        html_content = deck.to_html(as_string=True, iframe_width="100%", iframe_height=700)
        return html_content
        
    except Exception as e:
        st.error(f"Erreur lors de la génération du HTML Pydeck : {e}")
        return None
