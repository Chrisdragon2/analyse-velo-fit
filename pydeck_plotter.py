import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np

def create_3d_map_trace_nomapbox(df):
    """
    Crée une carte 3D de la trace GPS (style 3D incliné)
    en utilisant Pydeck avec un fond de carte simple (pas de clé API).
    """
    
    # --- 1. Vérification des données ---
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        st.error("Données 'latitude' ou 'longitude' manquantes pour la carte 3D.")
        return
        
    df_map = df[['latitude', 'longitude']].dropna()
    
    # Renommer pour Pydeck
    df_map = df_map.rename(columns={"latitude": "lat", "longitude": "lon"})
    
    if df_map.empty:
        st.warning("Données invalides pour la carte 3D."); return
        
    # --- 2. Échantillonnage pour la performance ---
    sampling_rate = max(1, len(df_map) // 5000)
    df_sampled = df_map.iloc[::sampling_rate, :].copy()

    # Créer la liste de coordonnées pour le "path"
    path_data = [
        {"path": df_sampled[['lon', 'lat']].values.tolist(), "name": "Trace"}
    ]

    # --- 3. Centrage de la vue ---
    mid_lat = df_sampled['lat'].mean()
    mid_lon = df_sampled['lon'].mean()
    
    initial_view_state = pdk.ViewState(
        latitude=mid_lat,
        longitude=mid_lon,
        zoom=11,
        pitch=45, 
        bearing=0
    )

    # --- 4. Définition de la couche (Layer) ---
    # LA SECTION MODIFIÉE EST ICI :
    path_layer = pdk.Layer(
        'PathLayer',
        data=path_data,
        pickable=True,
        # get_color=[255, 100, 0], # Ancienne couleur orange
        get_color=[255, 69, 0, 255], # NOUVEAU : Orange plus vif et opaque (RGBA)
        # width_scale=20, # On peut le garder si on veut
        width_min_pixels=5, # NOUVEAU : Largeur minimale en pixels (plus épais)
        get_path='path',
        get_width=10, # NOUVEAU : Largeur de la ligne relative (plus épais)
        # get_billboard=True, # OPTIONNEL : Rend la ligne visible quelle que soit la distance de zoom
    )

    # --- 5. Création de la carte Pydeck (sans clé) ---
    st.pydeck_chart(pdk.Deck(
        layers=[path_layer],
        initial_view_state=initial_view_state,
        map_style=pdk.map_styles.LIGHT, # ou DARK, ou ROAD
        tooltip={"text": "{name}"}
    ))
