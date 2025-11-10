# pydeck_plotter.py
import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np

def create_pydeck_chart(df):
    """
    Crée une carte 3D inclinée (style "beau visuel" avec glow).
    """
    
    # --- 1. Vérification des données ---
    if 'position_lat' not in df.columns or 'position_long' not in df.columns:
        st.warning("Données 'position_lat' ou 'position_long' manquantes pour la carte 3D.")
        return None # Renvoyer None pour que l'appelant le gère
        
    df_map = df[['position_lat', 'position_long']].dropna().copy()
    
    # Renommer pour Pydeck
    df_map = df_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
    
    if df_map.empty:
        st.warning("Données GPS invalides pour la carte 3D."); return None
        
    # --- 2. Échantillonnage ---
    sampling_rate = max(1, len(df_map) // 5000)
    df_sampled = df_map.iloc[::sampling_rate, :].copy()

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
        pitch=45, # Vue 3D Inclinée
        bearing=0
    )

    # --- 4. Définition des Couches (Layers) ---
    
    # Couche 1 : Le "Glow" (en dessous)
    glow_layer = pdk.Layer(
        'PathLayer',
        data=path_data,
        pickable=False, # Pas cliquable
        get_color=[255, 100, 0, 80], # Orange, mais semi-transparent (80 sur 255)
        width_scale=20,
        width_min_pixels=10, # Plus large que la ligne principale
        get_path='path',
        get_width=10,
    )

    # Couche 2 : La Ligne Principale (par-dessus)
    # (Utilise tes réglages)
    path_layer = pdk.Layer(
        'PathLayer',
        data=path_data,
        pickable=True,
        get_color=[255, 69, 0, 255], # Ton orange vif et opaque
        width_scale=20,
        width_min_pixels=5, # Ton réglage
        get_path='path',
        get_width=10, # Ton réglage
    )

    # --- 5. Création de la carte Pydeck ---
    deck = pdk.Deck(
        layers=[
            glow_layer, # Le glow en premier (en dessous)
            path_layer  # La ligne principale par-dessus
        ],
        initial_view_state=initial_view_state,
        map_style=pdk.map_styles.DARK, # <-- Passage en Dark Mode
        tooltip={"text": "{name}"}
    )
    
    return deck
