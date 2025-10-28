# sprint_detector.py
import pandas as pd
import numpy as np
import streamlit as st # Needed for potential warnings, though currently unused here

def detect_sprints(df, min_speed_kmh=40.0, min_gradient=-5.0, max_gradient=5.0, min_duration_sec=5):
    """
    Détecte les segments de sprint basés sur la vitesse et la pente moyenne.

    Args:
        df (pd.DataFrame): DataFrame indexé par timestamp avec 'speed', 'distance', 'pente'.
                           Doit aussi avoir 'delta_time'.
        min_speed_kmh (float): Vitesse minimale (km/h) pour être considéré en sprint.
        min_gradient (float): Pente moyenne minimale (%) pendant le sprint.
        max_gradient (float): Pente moyenne maximale (%) pendant le sprint.
        min_duration_sec (int): Durée minimale (secondes) pour qu'un effort soit classé comme sprint.

    Returns:
        list: Une liste de dictionnaires, chaque dictionnaire représentant un sprint détecté.
    """
    sprints = []
    # Work on a copy to avoid modifying the original DataFrame passed from cache
    df_sprint = df.copy()

    # S'assurer que les colonnes nécessaires existent
    required_cols = ['speed', 'distance', 'pente']
    missing_cols = [col for col in required_cols if col not in df_sprint.columns]
    if missing_cols:
        st.warning(f"Colonnes manquantes pour détecter les sprints : {', '.join(missing_cols)}. Détection annulée.")
        return []

    # Calculer delta_time si absent (sécurité)
    if 'delta_time' not in df_sprint.columns:
         if not isinstance(df_sprint.index, pd.DatetimeIndex):
             try: df_sprint.index = pd.to_datetime(df_sprint.index)
             except Exception:
                 st.error("Index non DatetimeIndex pour calculer delta_time dans detect_sprints.")
                 return [] # Stop if index is wrong
         df_sprint['delta_time'] = df_sprint.index.to_series().diff().dt.total_seconds().fillna(1.0).clip(lower=0.1)

    # Convertir la vitesse seuil en m/s
    min_speed_ms = min_speed_kmh / 3.6

    # 1. Identifier les moments de haute vitesse
    df_sprint['is_high_speed'] = (df_sprint['speed'] >= min_speed_ms)

    # 2. Créer des blocs de haute vitesse consécutifs
    df_sprint['high_speed_block'] = (df_sprint['is_high_speed'] != df_sprint['is_high_speed'].shift()).cumsum()

    # Garder uniquement les blocs qui sont à haute vitesse
    high_speed_segments_groups = df_sprint[df_sprint['is_high_speed']].groupby('high_speed_block')

    # Analyser chaque bloc
    for block_id, segment in high_speed_segments_groups:
        # Need to work on a copy to calculate acceleration within the loop
        segment = segment.copy()
        
        # Calculate duration robustly
        if len(segment) > 1:
            duration = (segment.index[-1] - segment.index[0]).total_seconds() + segment['delta_time'].iloc[-1]
        elif len(segment) == 1:
             duration = segment['delta_time'].iloc[0] # Duration of a single point block
        else:
             continue # Skip empty segments

        # 3. Vérifier la durée minimale
        if duration >= min_duration_sec:
            # 4. Calculer la pente moyenne du segment
            avg_gradient = segment['pente'].mean() # Utilise la colonne 'pente' déjà calculée

            # 5. Vérifier si la pente moyenne est dans la plage autorisée
            if min_gradient <= avg_gradient <= max_gradient:
                start_time = segment.index[0]
                peak_speed_kmh = segment['speed'].max() * 3.6
                avg_speed_kmh = segment['speed'].mean() * 3.6
                # Calculate distance more robustly using diff on the segment itself
                segment['delta_distance'] = segment['distance'].diff().fillna(0)
                distance_covered = segment['delta_distance'].sum()


                # Ajouter puissance max si disponible
                max_power = segment['estimated_power'].max() if 'estimated_power' in segment.columns and not segment['estimated_power'].isnull().all() else np.nan
                 # Calculer Accel Max pendant le sprint
                if 'delta_speed' not in segment.columns: # Recalculer si besoin
                    segment['delta_speed'] = segment['speed'].diff().fillna(0)
                # Avoid division by zero for acceleration
                segment['acceleration'] = np.where(segment['delta_time'] == 0, 0, segment['delta_speed'] / segment['delta_time'])
                max_accel = segment['acceleration'].max()


                sprints.append({
                    'Début': start_time.strftime('%H:%M:%S'),
                    'Durée (s)': f"{duration:.1f}",
                    'Vitesse Max (km/h)': f"{peak_speed_kmh:.1f}",
                    'Vitesse Moy (km/h)': f"{avg_speed_kmh:.1f}",
                    'Pente Moy (%)': f"{avg_gradient:.1f}", # Ajout de la pente moyenne
                    'Accel Max (m/s²)': f"{max_accel:.2f}",
                    'Distance (m)': f"{distance_covered:.0f}",
                    'Puissance Max Est. (W)': f"{max_power:.0f}" if pd.notna(max_power) else "N/A"
                })

    return sprints
