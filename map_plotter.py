# map_plotter.py
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import plotly.colors
import streamlit as st

def create_map_figure(df):
    """
    Crée une carte Scattermapbox du parcours, colorée par la puissance estimée.
    Utilise la méthode multi-traces pour une ligne colorée (peut être lent).
    """
    
    # --- 1. Préparation des données ---
    df_map = df.copy()
    
    # Vérifier les colonnes GPS
    if 'position_lat' not in df_map.columns or 'position_long' not in df_map.columns:
        st.warning("Données GPS (position_lat/long) non trouvées. Impossible d'afficher la carte.")
        return go.Figure() # Retourne une figure vide

    # Vérifier la puissance (colonne de couleur)
    if 'estimated_power' not in df_map.columns or df_map['estimated_power'].isnull().all():
        st.warning("Données de puissance estimée non disponibles pour la carte. Tracé simple.")
        df_map['plot_color_val'] = 0
        show_colorbar = False
        colorscale = [[0.0, 'rgb(0,104,201)'], [1.0, 'rgb(0,104,201)']] # Bleu uni
    else:
        df_map['plot_color_val'] = df_map['estimated_power']
        show_colorbar = True
        # Palette de "chaleur" : Bleu (basse) -> Vert -> Jaune -> Rouge (haute)
        colorscale = 'Jet' 
    
    # Échantillonnage : 1 point toutes les 5 secondes pour la performance
    # (Tracer chaque seconde est trop lourd pour le navigateur)
    df_sampled = df_map.iloc[::5, :]
    
    if df_sampled.empty:
        st.warning("Pas assez de données pour tracer la carte.")
        return go.Figure()
        
    # Définir les seuils de couleur
    min_color_val = df_sampled['plot_color_val'].min()
    max_color_val = df_sampled['plot_color_val'].max()
    range_color = max_color_val - min_color_val
    # Éviter la division par zéro si la puissance est constante
    if range_color == 0: range_color = 1.0 

    # Trouver le centre de la carte
    center_lat = df_sampled['position_lat'].mean()
    center_lon = df_sampled['position_long'].mean()

    fig = go.Figure()

    # --- 2. Création des micro-segments (La seule façon de colorer une ligne) ---
    # On itère sur chaque segment point par point (de l'échantillon)
    for i in range(len(df_sampled) - 1):
        row_start = df_sampled.iloc[i]
        row_end = df_sampled.iloc[i+1]
        
        # Obtenir la valeur de puissance
        power_val = row_start['plot_color_val']
        # Normaliser la valeur (0.0 à 1.0)
        power_norm = (power_val - min_color_val) / range_color
        
        # Contourner le bug de sample_colorscale (comme pour les sprints)
        epsilon = 1e-9
        power_norm_clamped = max(epsilon, min(1.0 - epsilon, power_norm))
        
        # Obtenir la couleur pour ce segment
        color_rgb_str = plotly.colors.sample_colorscale(colorscale, power_norm_clamped)[0]

        fig.add_trace(go.Scattermapbox(
            lat=[row_start['position_lat'], row_end['position_lat']],
            lon=[row_start['position_long'], row_end['position_long']],
            mode='lines',
            line=dict(width=3, color=color_rgb_str),
            name=f"Segment {i}",
            hovertemplate=f"<b>Puissance Est:</b> {power_val:.0f} W<br>" +
                          f"<b>Vitesse:</b> {row_start['speed']*3.6:.1f} km/h<br>" +
                          f"<b>Altitude:</b> {row_start['altitude']:.0f} m<extra></extra>"
        ))

    # --- 3. Mise en forme de la carte ---
    fig.update_layout(
        title="Carte du Parcours (Colorée par Puissance Estimée)",
        showlegend=False, # Important pour ne pas avoir 1000+ légendes
        mapbox_style="open-street-map", # Fond de carte gratuit
        mapbox=dict(
            center=go.layout.mapbox.Center(lat=center_lat, lon=center_lon),
            zoom=12 # Niveau de zoom initial
        ),
        margin={"r":0, "t":40, "l":0, "b":0},
        height=500,
        # Ajout manuel de la barre de couleur (si on a de la puissance)
        coloraxis_showscale=show_colorbar,
        coloraxis=dict(
            colorscale=colorscale,
            cmin=min_color_val,
            cmax=max_color_val,
            colorbar=dict(title='Puissance (W)')
        )
    )
    
    return fig
