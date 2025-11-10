# pydeck_plotter.py
import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np

# --- MODIFIÉ : Le nom de la fonction (pour correspondre à analyse_fit.py) ---
def create_pydeck_chart(df):
    """
    Crée une carte 3D inclinée de la trace GPS en utilisant Pydeck
    AVEC l'altitude pour montrer le relief.
    """
    
    # --- 1. Vérification des données (CORRIGÉ) ---
    # On utilise les noms de colonnes de notre DataFrame : 'position_lat', 'position_long', 'altitude'
    required_cols = ['position_lat', 'position_long', 'altitude']
    if not all(col in df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df.columns]
        st.warning(f"Données manquantes ({', '.join(missing)}) pour la carte 3D.")
        return None # Renvoyer None pour que l'appelant le gère
        
    df_map = df[required_cols].dropna().copy()
    
    # Renommer pour Pydeck
    df_map = df_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
    
    if df_map.empty:
        st.warning("Données GPS/Altitude invalides pour la carte 3D."); return None
        
    # --- 2. Échantillonnage pour la performance ---
    # Pydeck est performant, mais un échantillonnage reste une bonne idée
    sampling_rate = max(1, len(df_map) // 5000) # Garder max 5000 points
    df_sampled = df_map.iloc[::sampling_rate, :].copy()

    # Créer la liste de coordonnées pour le "path"
    # Le chemin inclut [lon, lat, altitude] pour le relief
    path_data = [
        {"path": df_sampled[['lon', 'lat', 'altitude']].values.tolist(), "name": "Trace"}
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

    # --- 4. Définition de la couche (Layer) ---
    path_layer = pdk.Layer(
        'PathLayer',
        data=path_data,
        pickable=True,
        get_color=[255, 69, 0, 255], # Ton orange vif
        width_scale=1, # Échelle de largeur (1 est souvent OK pour la 3D)
        width_min_pixels=3, # Ligne épaisse
        get_path='path',
        get_width=5,
    )

    # --- 5. Création de la carte Pydeck (sans clé) ---
    deck = pdk.Deck(
        layers=[path_layer],
        initial_view_state=initial_view_state,
        # Utiliser un fond de carte sombre pour faire ressortir la trace
        map_style=pdk.map_styles.DARK, 
        tooltip={"text": "{name}"}
    )
    
    return deck
