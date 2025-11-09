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
    cmin, cmax = 0, 1 # Valeurs par défaut pour éviter les erreurs
    
    # S'assurer que les colonnes nécessaires existent pour le calcul de cmin/cmax
    if 'speed_kmh' not in df_3d.columns and 'speed' in df_3d.columns:
        df_3d['speed_kmh'] = df_3d['speed'] * 3.6

    # Mapper le nom du sélecteur à la colonne réelle et à la palette
    if color_metric == 'Puissance' and 'estimated_power' in df_3d.columns and not df_3d['estimated_power'].isnull().all():
        df_3d[color_col_name] = df_3d['estimated_power'].clip(upper=POWER_SCALE_MAX_W)
        colorscale_to_use = COLORSCALE_POWER
        colorbar_title = 'Puissance (W)'
        cmin, cmax = 0, POWER_SCALE_MAX_W
    elif color_metric == 'Vitesse' and 'speed_kmh' in df_3d.columns and not df_3d['speed_kmh'].isnull().all():
        df_3d[color_col_name] = df_3d['speed_kmh']
        colorscale_to_use = COLORSCALE_SPEED
        colorbar_title = 'Vitesse (km/h)'
        cmin, cmax = df_3d[color_col_name].min(), df_3d[color_col_name].max()
    elif color_metric == 'Fréquence Cardiaque' and 'heart_rate' in df_3d.columns and not df_3d['heart_rate'].isnull().all():
        df_3d[color_col_name] = df_3d['heart_rate']
        colorscale_to_use = COLORSCALE_HR
        colorbar_title = 'FC (bpm)'
        cmin, cmax = df_3d[color_col_name].min(), df_3d[color_col_name].max()
    elif color_metric == 'Altitude' and 'altitude' in df_3d.columns and not df_3d['altitude'].isnull().all():
        df_3d[color_col_name] = df_3d['altitude']
        colorscale_to_use = COLORSCALE_ALTITUDE
        colorbar_title = 'Altitude (m)'
        cmin, cmax = df_3d[color_col_name].min(), df_3d[color_col_name].max()
    else:
        # Fallback si la donnée n'existe pas ou est vide
        if 'altitude' in df_3d.columns and not df_3d['altitude'].isnull().all():
            df_3d[color_col_name] = df_3d['altitude']
            colorscale_to_use = COLORSCALE_ALTITUDE
            colorbar_title = 'Altitude (m)'
            cmin, cmax = df_3d[color_col_name].min(), df_3d[color_col_name].max()
        else: # Fallback ultime si rien n'est valide
            df_3d[color_col_name] = 0
            cmin, cmax = 0, 1

    # --- 2. Création de la figure 3D ---
    fig = go.Figure()
    
    # Texte d'info au survol (dynamique)
    hover_text = df_3d.apply(
        lambda row: (
            f"<b>Distance:</b> {row.get('distance', 0) / 1000:.2f} km<br>"
            f"<b>Altitude:</b> {row.get('altitude', 0):.0f} m<br>"
            f"<b>Vitesse:</b> {row.get('speed_kmh', row.get('speed', 0) * 3.6):.1f} km/h<br>"
            f"<b>Puissance Est:</b> {row.get('estimated_power', 0):.0f} W<br>"
            f"<b>FC:</b> {row.get('heart_rate', 'N/A'):.0f} bpm"
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
    camera_target = None
    if camera_index > 0 and camera_index < len(df_3d):
        point = df_3d.iloc[camera_index]
        # Regarde un peu en avant si possible, sinon le point actuel
        look_at_idx = min(camera_index + 5, len(df_3d) - 1)
        look_at = df_3d.iloc[look_at_idx]

        # Calcul d'une position de caméra derrière et au-dessus du point actuel
        # Cible (center) est le point actuel
        camera_target = dict(x=point['position_long'], y=point['position_lat'], z=point['altitude'])

        # Position de l'œil (eye): un peu en arrière, en décalé, et plus haut
        # Ces valeurs sont des ajustements "visuels" pour une bonne perspective
        # Distance arbitraire pour un angle de vue sympa
        dist_offset = 0.0005 
        height_offset = 50 # 50m au-dessus du point

        # Calculer une direction "derrière" en fonction de la direction du parcours
        if look_at_idx > camera_index: # Si on avance
            dir_lon = look_at['position_long'] - point['position_long']
            dir_lat = look_at['position_lat'] - point['position_lat']
        elif camera_index > 0: # Si c'est le dernier point ou qu'on recule
            dir_lon = point['position_long'] - df_3d.iloc[camera_index - 1]['position_long']
            dir_lat = point['position_lat'] - df_3d.iloc[camera_index - 1]['position_lat']
        else: # Premier point
            dir_lon = dist_offset # Par défaut
            dir_lat = dist_offset # Par défaut

        # Normaliser la direction (pour que la longueur du vecteur soit 1)
        magnitude = np.sqrt(dir_lon**2 + dir_lat**2)
        if magnitude == 0: magnitude = 1 # Éviter division par zéro
        dir_lon_norm = dir_lon / magnitude
        dir_lat_norm = dir_lat / magnitude
        
        # Position de la caméra (œil) : derrière, un peu sur le côté, et au-dessus
        camera_eye = dict(
            x=point['position_long'] - dir_lon_norm * dist_offset - dir_lat_norm * dist_offset * 0.5, # Décalage lat/long
            y=point['position_lat'] - dir_lat_norm * dist_offset + dir_lon_norm * dist_offset * 0.5, # Décalage lat/long
            z=point['altitude'] + height_offset
        )
        
        camera_up = dict(x=0, y=0, z=1) # L'axe Z est toujours le "haut"
        camera_projection = dict(type='perspective') # Projection perspective par défaut
        
        # Le dict complet pour camera
        camera_settings = dict(
            up=camera_up,
            center=dict(x=0, y=0, z=0), # On le laisse à 0, l'orientation fait le reste
            eye=camera_eye
        )
    else:
        # Vue d'ensemble par défaut (quand slider à 0)
        camera_settings = dict(eye=dict(x=1.5, y=-1.5, z=1.5))


    # --- 4. Mise en page de la figure 3D ---
    fig.update_layout(
        title='Parcours en 3D (Longitude / Latitude / Altitude)',
        scene=dict(
            xaxis_title='Longitude',
            yaxis_title='Latitude',
            zaxis_title='Altitude (m)',
            # TRÈS IMPORTANT : Définir des ratios d'aspect pour que la carte ne soit pas déformée
            aspectmode='manual', # On gère manuellement les proportions
            aspectratio=dict(x=1, y=1, z=0.2), # Ex: l'axe Z (altitude) est 5x moins "long" que X ou Y
            camera=camera_settings # Applique la position de la caméra
        ),
        height=700,
        margin={"r":0, "t":40, "l":0, "b":0},
        showlegend=False
    )

    return fig
