# map_plotter.py
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import plotly.colors
import streamlit as st

def create_map_figure(df):
    """
    Crée une carte Scattermapbox (Version Efficace avec LIGNES colorées par CHUNKS).
    """
    
    # --- 1. Préparation des données ---
    df_map = df.copy()
    
    if 'position_lat' not in df_map.columns or 'position_long' not in df_map.columns:
        st.warning("Données GPS (position_lat/long) non trouvées.")
        return go.Figure()

    df_map = df_map.dropna(subset=['position_lat', 'position_long'])
    
    if df_map.empty:
        st.warning("Données GPS invalides après nettoyage.")
        return go.Figure()
        
    has_power_data = 'estimated_power' in df_map.columns and not df_map['estimated_power'].isnull().all()
    
    if has_power_data:
        df_map['plot_color_val'] = df_map['estimated_power']
        colorscale = 'Jet'
        min_color_val = df_map['plot_color_val'].min()
        max_color_val = df_map['plot_color_val'].max()
        range_color = max_color_val - min_color_val
        if range_color == 0: range_color = 1.0 # Éviter division par zéro
        colorbar_title = 'Puissance (W)'
    else:
        st.warning("Données de puissance estimée non disponibles. Tracé simple.")
        df_map['plot_color_val'] = 0
        colorscale = 'Blues'
        min_color_val = 0; max_color_val = 1; range_color = 1.0
        colorbar_title = ''

    # --- 2. NOUVELLE LOGIQUE : Grouper par Chunks de Distance ---
    # Définir la taille du chunk (ex: 250 mètres)
    CHUNK_DISTANCE_MAP = 50 
    
    if 'distance' not in df_map.columns:
        st.error("Colonne 'distance' manquante pour les chunks de carte.")
        return go.Figure()
        
    df_map['distance_bin'] = (df_map['distance'] // CHUNK_DISTANCE_MAP) * CHUNK_DISTANCE_MAP
    
    # Grouper les données par ces chunks
    try:
        grouped = df_map.groupby('distance_bin', observed=True)
    except TypeError:
        grouped = df_map.groupby('distance_bin')
    
    # Trouver le centre de la carte (sur tout le parcours)
    center_lat = df_map['position_lat'].mean()
    center_lon = df_map['position_long'].mean()

    fig = go.Figure()
    
    # Obtenir la colormap
    plotly_colorscale = plotly.colors.get_colorscale(colorscale)

    # --- 3. Créer une trace par CHUNK coloré ---
    for name, group in grouped:
        if group.empty:
            continue
            
        # Calculer la couleur moyenne pour ce chunk
        if has_power_data:
            avg_power = group['plot_color_val'].mean()
            # Normaliser et clamper
            power_norm = max(0.00001, min(0.99999, (avg_power - min_color_val) / range_color))
            segment_color_rgb_str = plotly.colors.sample_colorscale(plotly_colorscale, power_norm)[0]
            hovertemplate = f"<b>Puissance Moy:</b> {avg_power:.0f} W<br><b>Distance:</b> {name}m - {name + CHUNK_DISTANCE_MAP}m<extra></extra>"
        else:
            segment_color_rgb_str = 'rgb(0,104,201)' # Bleu uni
            hovertemplate = "Trace GPS<extra></extra>"

        # Ajouter une trace (ligne) pour ce chunk
        fig.add_trace(go.Scattermapbox(
            lat=group['position_lat'],
            lon=group['position_long'],
            mode='lines',
            line=dict(width=4, color=segment_color_rgb_str), # Ligne épaisse
            hovertemplate=hovertemplate,
            showlegend=False
        ))

    # --- 4. Ajout manuel de la barre de couleur (si données de puissance) ---
    if has_power_data:
        fig.add_trace(go.Scattermapbox(
            lat=[center_lat], lon=[center_lon], # Position arbitraire
            mode='markers',
            marker=dict(
                size=0, # Invisible
                color=[min_color_val, max_color_val],
                colorscale=colorscale,
                showscale=True,
                colorbar=dict(title=colorbar_title, title_side='right', len=0.7, thickness=20)
            ),
            hoverinfo='none', showlegend=False
        ))

    # --- 5. Mise en forme de la carte ---
    fig.update_layout(
        title="Carte du Parcours (Lignes colorées par Puissance Moyenne)",
        showlegend=False,
        mapbox_style="carto-positron", # Fond épuré
        mapbox=dict(
            center=go.layout.mapbox.Center(lat=center_lat, lon=center_lon),
            zoom=12 
        ),
        margin={"r":0, "t":40, "l":0, "b":0},
        height=500,
        hoverlabel=dict(bgcolor="white", bordercolor="#E0E0E0", font=dict(color="#333333"))
    )
    
    return fig
