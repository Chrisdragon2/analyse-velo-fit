# map_plotter.py
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import plotly.colors
import streamlit as st

# MODIFIÉ : La fonction accepte 'mapbox_style'
def create_map_figure(df, mapbox_style="carto-positron"):
    """
    Crée une carte Scattermapbox (Version Efficace avec Ligne + Marqueurs "Heatmap")
    avec un style de carte sélectionnable.
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
    if 'estimated_power' in df_map.columns and not df_map['estimated_power'].isnull().all():
        df_map['plot_color_val'] = df_map['estimated_power']
        color_scale = 'Jet' 
        show_colorbar = True
        cmin = df_map['plot_color_val'].min()
        cmax = df_map['plot_color_val'].max()
        colorbar_title = 'Puissance (W)'
        customdata = np.stack((
            df_map['estimated_power'], 
            (df_map['speed'] * 3.6).round(1)
        ), axis=-1)
        hovertemplate = "<b>Puissance Est:</b> %{customdata[0]:.0f} W<br><b>Vitesse:</b> %{customdata[1]} km/h<extra></extra>"
    else:
        st.warning("Données de puissance estimée non disponibles. Tracé simple.")
        df_map['plot_color_val'] = 0
        color_scale = 'blues'
        show_colorbar = False
        cmin = 0; cmax = 1; colorbar_title = ''
        customdata = None
        hovertemplate = "<b>Vitesse:</b> %{text} km/h<extra></extra>"

    # Échantillonnage : 1 point toutes les 3 secondes
    df_sampled = df_map.iloc[::3, :]
    
    if df_sampled.empty:
        st.warning("Pas assez de données pour tracer la carte."); return go.Figure()
        
    center_lat = df_sampled['position_lat'].mean()
    center_lon = df_sampled['position_long'].mean()

    fig = go.Figure()

    # --- 2. Création d'UNE SEULE Trace (Ligne + Marqueurs "Heatmap") ---
    fig.add_trace(go.Scattermapbox(
        lat=df_sampled['position_lat'],
        lon=df_sampled['position_long'],
        mode='lines+markers',
        customdata=customdata,
        hovertemplate=hovertemplate,
        text=(df_sampled['speed'] * 3.6).round(1) if customdata is None else None,
        
        marker=go.scattermapbox.Marker(
            size=10,
            opacity=0.6,
            color=df_sampled['plot_color_val'],
            colorscale=color_scale,
            cmin=cmin,
            cmax=cmax,
            showscale=show_colorbar,
            colorbar=dict(
                title=colorbar_title, 
                title_side='right'
            )
        ),
        line=dict(width=1, color='rgba(0,0,0,0.2)')
    ))

    # --- 3. Mise en forme de la carte ---
    fig.update_layout(
        title="Carte du Parcours (Heatmap de Puissance Estimée)",
        showlegend=False,
        # --- MODIFIÉ : Utilise le style de carte passé en argument ---
        mapbox_style=mapbox_style,
        mapbox=dict(
            center=go.layout.mapbox.Center(lat=center_lat, lon=center_lon),
            zoom=12 
        ),
        margin={"r":0, "t":40, "l":0, "b":0},
        height=500,
        hoverlabel=dict(bgcolor="white", bordercolor="#E0E0E0", font=dict(color="#333333"))
    )
    
    return fig
