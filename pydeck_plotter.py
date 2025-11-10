# pydeck_plotter.py
import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np

def create_pydeck_chart(df):
    """
    Crée une carte 3D inclinée de la trace GPS en utilisant Pydeck.
    """
    
    # --- 1. Vérification des données ---
    if 'position_lat' not in df.columns or 'position_long' not in df.columns:
        st.warning("Données 'position_lat' ou 'position_long' manquantes pour la carte 3D.")
        return
        
    df_map = df[['position_lat', 'position_long']].dropna().copy()
    
    # Renommer pour Pydeck
    df_map = df_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
    
    if df_map.empty:
        st.warning("Données GPS invalides pour la carte 3D."); return
        
    # --- 2. Échantillonnage pour la performance ---
    # Pydeck est performant, mais un échantillonnage reste une bonne idée
    sampling_rate = max(1, len(df_map) // 5000)
    df_sampled = df_map.iloc[::sampling_rate, :].copy()

    # Créer la liste de coordonnées pour le "path"
    # Pydeck attend une liste de listes de coordonnées [lon, lat]
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
        pitch=45, # <-- C'EST LA VUE 3D INCLINÉE
        bearing=0
    )

    # --- 4. Définition de la couche (Layer) ---
    path_layer = pdk.Layer(
        'PathLayer',
        data=path_data,
        pickable=True,
        get_color=[255, 100, 0], # Orange
        width_scale=20,
        width_min_pixels=2,
        get_path='path',
        get_width=5,
    )

    # --- 5. Création de la carte Pydeck (sans clé) ---
    deck = pdk.Deck(
        layers=[path_layer],
        initial_view_state=initial_view_state,
        # On utilise un style simple qui ne requiert pas de clé
        map_style=pdk.map_styles.LIGHT,
        tooltip={"text": "{name}"}
    )
    
    # Renvoyer l'objet Deck pour que Streamlit l'affiche
    return deck
