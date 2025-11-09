# map_plotter.py
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import plotly.colors
import streamlit as st

def create_map_figure(df):
    """
    Crée une carte Scattermapbox du parcours, colorée par la puissance estimée.
    (Version avec Ligne Continue Colorée par Micro-Segments)
    """
    
    # --- 1. Préparation des données ---
    df_map = df.copy()
    
    if 'position_lat' not in df_map.columns or 'position_long' not in df_map.columns:
        st.warning("Données GPS (position_lat/long) non trouvées. Impossible d'afficher la carte.")
        return go.Figure()

    df_map = df_map.dropna(subset=['position_lat', 'position_long'])
    
    if df_map.empty:
        st.warning("Données GPS invalides après nettoyage.")
        return go.Figure()
        
    # Vérifier la puissance (colonne de couleur)
    has_power_data = 'estimated_power' in df_map.columns and not df_map['estimated_power'].isnull().all()
    
    if has_power_data:
        df_map['plot_color_val'] = df_map['estimated_power']
        # Palette 'Jet' (Bleu -> Rouge)
        colorscale_name = 'Jet' 
        colorbar_title = 'Puissance (W)'
        # Préparer les données pour le hover
        df_map['speed_kmh'] = (df_map['speed'] * 3.6).round(1)
        hovertemplate_base = "<b>Puissance Est:</b> %{customdata[0]:.0f} W<br><b>Vitesse:</b> %{customdata[1]} km/h<extra></extra>"
    else:
        st.warning("Données de puissance estimée non disponibles pour la carte. Tracé simple (bleu).")
        df_map['plot_color_val'] = 0 # Couleur unique si pas de puissance
        colorscale_name = 'Blues'
        colorbar_title = ''
        df_map['speed_kmh'] = (df_map['speed'] * 3.6).round(1)
        hovertemplate_base = "<b>Vitesse:</b> %{customdata[0]} km/h<extra></extra>"

    # Échantillonnage : 1 point toutes les 5 secondes pour la performance
    # Plus les fichiers sont longs, plus on peut augmenter l'échantillonnage (ex: 10, 20)
    df_sampled = df_map.iloc[::5, :]
    
    if df_sampled.empty:
        st.warning("Pas assez de données pour tracer la carte.")
        return go.Figure()
        
    # Trouver le centre de la carte
    center_lat = df_sampled['position_lat'].mean()
    center_lon = df_sampled['position_long'].mean()

    fig = go.Figure()

    # --- 2. Création des micro-segments colorés ---
    
    # Obtenir la colormap de Plotly
    plotly_colorscale = plotly.colors.get_colorscale(colorscale_name)
    
    # Définir les bornes de couleur pour la normalisation
    if has_power_data:
        min_color_val = df_sampled['plot_color_val'].min()
        max_color_val = df_sampled['plot_color_val'].max()
        range_color = max_color_val - min_color_val
        if range_color == 0: range_color = 1.0 # Éviter division par zéro
    else:
        min_color_val = 0; max_color_val = 1; range_color = 1.0

    # Itérer sur les segments pour colorer la ligne
    for i in range(len(df_sampled) - 1):
        row_start = df_sampled.iloc[i]
        row_end = df_sampled.iloc[i+1]
        
        # Obtenir la valeur de puissance (ou 0 si pas de puissance)
        color_val = row_start['plot_color_val']
        
        # Normaliser la valeur (0.0 à 1.0) pour la colorscale
        # Ajouter une petite valeur epsilon pour éviter les bornes extrêmes qui peuvent planter sample_colorscale
        epsilon = 1e-9 
        color_norm = max(epsilon, min(1.0 - epsilon, (color_val - min_color_val) / range_color))
        
        # Obtenir la couleur pour ce segment
        segment_color_rgb_str = plotly.colors.sample_colorscale(plotly_colorscale, color_norm)[0]

        # Données pour le hover pour ce segment
        if has_power_data:
            segment_customdata = (row_start['estimated_power'], row_start['speed_kmh'])
        else:
            segment_customdata = (row_start['speed_kmh'],) # Tuple pour un seul élément
        
        fig.add_trace(go.Scattermapbox(
            lat=[row_start['position_lat'], row_end['position_lat']],
            lon=[row_start['position_long'], row_end['position_long']],
            mode='lines',
            line=dict(width=4, color=segment_color_rgb_str), # Épaisseur de la ligne
            customdata=segment_customdata,
            hovertemplate=hovertemplate_base,
            showlegend=False # Important pour éviter une légende pour chaque segment
        ))
    
    # --- 3. Ajout manuel de la barre de couleur (si données de puissance) ---
    if has_power_data:
        # Créer un trace invisible juste pour la colorbar
        fig.add_trace(go.Scattermapbox(
            lat=[df_sampled['position_lat'].iloc[0]],
            lon=[df_sampled['position_long'].iloc[0]],
            mode='markers',
            marker=dict(
                size=0, # Rendre le marqueur invisible
                color=[min_color_val, max_color_val],
                colorscale=colorscale_name,
                showscale=True,
                colorbar=dict(
                    title=colorbar_title,
                    title_side='right',
                    len=0.7, # Longueur de la barre
                    thickness=20 # Épaisseur de la barre
                )
            ),
            hoverinfo='none'
        ))

    # --- 4. Mise en forme de la carte ---
    fig.update_layout(
        title="Carte du Parcours (Colorée par Puissance Estimée)",
        mapbox_style="open-street-map", # Fond de carte gratuit
        mapbox=dict(
            center=go.layout.mapbox.Center(lat=center_lat, lon=center_lon),
            zoom=12 # Niveau de zoom initial
        ),
        margin={"r":0, "t":40, "l":0, "b":0},
        height=500,
        hoverlabel=dict(bgcolor="white", bordercolor="#E0E0E0", font=dict(color="#333333"))
    )
    
    return fig
