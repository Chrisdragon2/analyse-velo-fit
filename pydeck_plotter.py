# pydeck_plotter.py
import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np

# --- MODIFIÉ : Nom de la fonction corrigé ---
def create_pydeck_chart(df):
    """
    Crée une carte 3D inclinée de la trace GPS en utilisant Pydeck
    AVEC l'altitude ET le fond de carte satellite Mapbox.
    """
    
    # --- 1. Vérification des données (Noms de colonnes corrigés) ---
    required_cols = ['position_lat', 'position_long', 'altitude']
    if not all(col in df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df.columns]
        st.warning(f"Données manquantes ({', '.join(missing)}) pour la carte 3D.")
        return None
        
    df_map = df[required_cols].dropna().copy()
    
    # Renommer pour Pydeck
    df_map = df_map.rename(columns={"position_lat": "lat", "position_long": "lon"})
    
    if df_map.empty:
        st.warning("Données GPS/Altitude invalides pour la carte 3D."); return None
        
    # --- 2. Échantillonnage ---
    sampling_rate = max(1, len(df_map) // 5000)
    df_sampled = df_map.iloc[::sampling_rate, :].copy()

    # Le chemin inclut [lon, lat, altitude]
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
        pitch=45, 
        bearing=0
    )

    # --- 4. Définition de la couche (Layer) ---
    path_layer = pdk.Layer(
        'PathLayer',
        data=path_data,
        pickable=True,
        get_color=[255, 100, 0], # Orange
        width_scale=10, 
        width_min_pixels=2,
        get_path='path',
        get_width=5,
    )

    # --- 5. Création de la carte Pydeck (AVEC Mapbox) ---
    
    # Lire la clé depuis les secrets
    try:
        MAPBOX_KEY = st.secrets["MAPBOX_API_KEY"]
    except KeyError:
        st.error("Clé 'MAPBOX_API_KEY' non trouvée dans les secrets Streamlit !")
        return None
    except FileNotFoundError:
         st.error("Fichier secrets.toml non trouvé. Assure-toi qu'il est dans .streamlit/")
         return None

    deck = pdk.Deck(
        layers=[path_layer],
        initial_view_state=initial_view_state,
        
        map_provider="mapbox",
        map_style=pdk.map_styles.SATELLITE, # Style satellite
        
        api_keys={'mapbox': MAPBOX_KEY}, # Passer la clé
        
        tooltip={"text": "{name}"}
    )
    
    return deck
