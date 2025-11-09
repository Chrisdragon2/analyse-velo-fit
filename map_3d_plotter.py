# map_3d_plotter.py
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import plotly.colors
import streamlit as st

# --- Palettes de couleurs ---
COLORSCALE_POWER = [
    [0.0, 'rgb(0,128,0)'], [0.25, 'rgb(255,255,0)'], [0.5, 'rgb(255,165,0)'],
    [0.75, 'rgb(255,0,0)'], [1.0, 'rgb(0,0,0)']
]
POWER_SCALE_MAX_W = 1000.0
COLORSCALE_SPEED = 'Blues'
COLORSCALE_HR = 'Reds'
COLORSCALE_ALTITUDE = 'Viridis'

def create_3d_map_figure(df_sampled, color_metric, climb_segments, sprint_segments, camera_index):
    """
    Crée une visualisation 3D du parcours, avec toutes les options.
    
    Args:
        df_sampled (pd.DataFrame): Le DataFrame échantillonné pour le tracé principal.
        color_metric (str): La colonne à utiliser pour la couleur ('Puissance', 'Vitesse', 'FC', 'Altitude').
        climb_segments (list): Liste de DataFrames, un pour chaque montée à surligner.
        sprint_segments (list): Liste de DataFrames, un pour chaque sprint à surligner.
        camera_index (int): L'index (position iloc) du point de données où centrer la caméra.
    """
    
    df_3d = df_sampled.copy()

    # --- 1. Préparation des données de couleur (basé sur le sélecteur) ---
    color_col_name = 'plot_color_val'
    colorbar_title = ''
    colorscale_to_use = 'gray'
    
    # Mapper le nom du sélecteur à la colonne réelle et à la palette
    if color_metric == 'Puissance' and 'estimated_power' in df_3d.columns:
        df_3d[color_col_name] = df_3d['estimated_power'].clip(upper=POWER_SCALE_MAX_W)
        colorscale_to_use = COLORSCALE_POWER
        colorbar_title = 'Puissance (W)'
        cmin, cmax = 0, POWER_SCALE_MAX_W
    elif color_metric == 'Vitesse' and 'speed_kmh' in df_3d.columns:
        df_3d[color_col_name] = df_3d['speed_kmh']
        colorscale_to_use = COLORSCALE_SPEED
        colorbar_title = 'Vitesse (km/h)'
        cmin, cmax = df_3d[color_col_name].min(), df_3d[color_col_name].max()
    elif color_metric == 'Fréquence Cardiaque' and 'heart_rate' in df_3d.columns:
        df_3d[color_col_name] = df_3d['heart_rate']
        colorscale_to_use = COLORSCALE_HR
        colorbar_title = 'FC (bpm)'
        cmin, cmax = df_3d[color_col_name].min(), df_3d[color_col_name].max()
    elif color_metric == 'Altitude' and 'altitude' in df_3d.columns:
        df_3d[color_col_name] = df_3d['altitude']
        colorscale_to_use = COLORSCALE_ALTITUDE
        colorbar_title = 'Altitude (m)'
        cmin, cmax = df_3d[color_col_name].min(), df_3d[color_col_name].max()
    else:
        # Fallback si la donnée n'existe pas (ex: pas de FC)
        if 'altitude' in df_3d.columns:
            df_3d[color_col_name] = df_3d['altitude']
            colorscale_to_use = COLORSCALE_ALTITUDE
            colorbar_title = 'Altitude (m)'
            cmin, cmax = df_3d[color_col_name].min(), df_3d[color_col_name].max()
        else: # Fallback ultime
            df_3d[color_col_name] = 0
            cmin, cmax = 0, 1

    # --- 2. Création de la figure 3D ---
    fig = go.Figure()
    
    # Texte d'info au survol (dynamique)
    hover_text = df_3d.apply(
        lambda row: (
            f"<b>Distance:</b> {row.get('distance', 0) / 1000:.2f} km<br>"
            f"<b>Altitude:</b> {row.get('altitude', 0):.0f} m<br>"
            f"<b>Vitesse:</b> {row.get('speed_kmh', 0):.1f} km/h<br>"
            f"<b>Puissance Est:</b> {row.get('estimated_power', 0):.0f} W"
        ), axis=1
    )

    # --- Trace 1: Le parcours principal coloré ---
    fig.add_trace(go.Scatter3d(
        x=df_3d['position_long'],
        y=df_3d['position_lat'],
        z=df_3d['altitude'],
        mode='lines+markers',
        marker=dict(
            size=3,
            color=df_3d[color_col_name],
            colorscale=colorscale_to_use,
            cmin=cmin, cmax=cmax,
            colorbar=dict(title=colorbar_title, len=0.7),
            opacity=0.8
        ),
        line=dict(
            color=df_3d[color_col_name],
            colorscale=colorscale_to_use,
            cmin=cmin, cmax=cmax,
            width=4 # Ligne principale un peu plus épaisse
        ),
        text=hover_text,
        hoverinfo='text',
        name='Parcours'
    ))

    # --- Trace 2: Surlignage des Montées ---
    for i, segment in enumerate(climb_segments):
        if not segment.empty:
            fig.add_trace(go.Scatter3d(
                x=segment['position_long'],
                y=segment['position_lat'],
                z=segment['altitude'],
                mode='lines',
                line=dict(color='red', width=10), # Ligne ROUGE épaisse
                name=f'Montée {i+1}',
                hoverinfo='name'
            ))

    # --- Trace 3: Surlignage des Sprints ---
    for i, segment in enumerate(sprint_segments):
        if not segment.empty:
            fig.add_trace(go.Scatter3d(
                x=segment['position_long'],
                y=segment['position_lat'],
                z=segment['altitude'],
                mode='lines',
                line=dict(color='cyan', width=10), # Ligne CYAN épaisse
                name=f'Sprint {i+1}',
                hoverinfo='name'
            ))

    # --- 3. Gestion de la Caméra (Animation) ---
    if camera_index == 0 or camera_index >= len(df_3d):
        # Vue d'ensemble par défaut
        camera_eye = dict(x=1.5, y=-1.5, z=1.5)
    else:
        # Vue "Fly-Through" basée sur le slider
        point = df_3d.iloc[camera_index]
        # Calcule un point "derrière et au-dessus"
        look_at = df_3d.iloc[min(camera_index + 5, len(df_3d) - 1)] # Regarde un peu en avant
        
        camera_eye = dict(
            x=point['position_long'] - (look_at['position_long'] - point['position_long']) * 0.1 - 0.0005, # Un peu derrière
            y=point['position_lat'] - (look_at['position_lat'] - point['position_lat']) * 0.1 - 0.0005, # Un peu derrière
            z=point['altitude'] + 50 # 50m au-dessus du point
        )

    # --- 4. Mise en page de la figure 3D ---
    fig.update_layout(
        title='Parcours en 3D (Altitude vs Longitude/Latitude)',
        scene=dict(
            xaxis_title='Longitude',
            yaxis_title='Latitude',
            zaxis_title='Altitude (m)',
            aspectmode='data', # Maintient les proportions GPS/Altitude
            camera=dict(
                eye=camera_eye # Applique la position de la caméra
            )
        ),
        height=700,
        margin={"r":0, "t":40, "l":0, "b":0},
        showlegend=False # Trop de traces
    )

    return fig
