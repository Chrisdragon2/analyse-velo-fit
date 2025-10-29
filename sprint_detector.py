# sprint_detector.py
import pandas as pd
import numpy as np
import streamlit as st

def detect_sprints(df, min_speed_kmh=40.0, min_gradient=-5.0, max_gradient=5.0, min_duration_sec=5):
    """
    Détecte les segments de sprint basés sur la vitesse et la pente moyenne.
    Retourne le début en km ET l'heure de début.
    """
    sprints = []
    df_sprint = df.copy()

    required_cols = ['speed', 'distance', 'pente']
    missing_cols = [col for col in required_cols if col not in df_sprint.columns]
    if missing_cols:
        st.warning(f"Colonnes manquantes : {', '.join(missing_cols)}. Détection annulée.")
        return []

    if 'delta_time' not in df_sprint.columns:
         if not isinstance(df_sprint.index, pd.DatetimeIndex):
             try: df_sprint.index = pd.to_datetime(df_sprint.index)
             except Exception:
                 st.error("Index non DatetimeIndex.")
                 return []
         df_sprint['delta_time'] = df_sprint.index.to_series().diff().dt.total_seconds().fillna(1.0).clip(lower=0.1)

    min_speed_ms = min_speed_kmh / 3.6
    df_sprint['is_high_speed'] = (df_sprint['speed'] >= min_speed_ms)
    df_sprint['high_speed_block'] = (df_sprint['is_high_speed'] != df_sprint['is_high_speed'].shift()).cumsum()
    high_speed_segments_groups = df_sprint[df_sprint['is_high_speed']].groupby('high_speed_block')

    for block_id, segment_orig in high_speed_segments_groups:
        segment = segment_orig.copy()

        if len(segment) > 1:
            duration = (segment.index[-1] - segment.index[0]).total_seconds() + segment['delta_time'].iloc[-1]
        elif len(segment) == 1:
             duration = segment['delta_time'].iloc[0]
        else:
             continue

        if duration >= min_duration_sec:
            avg_gradient = segment['pente'].mean()

            if min_gradient <= avg_gradient <= max_gradient:
                # --- MODIFIÉ : Garder les deux infos de début ---
                start_time = segment.index[0] # Garde l'objet Timestamp
                start_distance_km = segment['distance'].iloc[0] / 1000
                # --- FIN MODIFICATION ---

                peak_speed_kmh = segment['speed'].max() * 3.6
                avg_speed_kmh = segment['speed'].mean() * 3.6
                segment['delta_distance'] = segment['distance'].diff().fillna(0)
                distance_covered = segment['delta_distance'].sum()
                max_power = segment['estimated_power'].max() if 'estimated_power' in segment.columns and not segment['estimated_power'].isnull().all() else np.nan

                if 'delta_speed' not in segment.columns:
                    segment['delta_speed'] = segment['speed'].diff().fillna(0)
                segment['acceleration'] = np.where(segment['delta_time'] == 0, 0, segment['delta_speed'] / segment['delta_time'])
                max_accel = segment['acceleration'].max()

                sprints.append({
                    # --- MODIFIÉ : Ajouter les deux clés ---
                    'Début': start_time, # Pour l'extraction des données du graphique (objet Timestamp)
                    'Début (km)': f"{start_distance_km:.1f}", # Pour l'affichage dans le tableau
                    # --- FIN MODIFICATION ---
                    'Durée (s)': f"{duration:.1f}",
                    'Vitesse Max (km/h)': f"{peak_speed_kmh:.1f}",
                    'Vitesse Moy (km/h)': f"{avg_speed_kmh:.1f}",
                    'Pente Moy (%)': f"{avg_gradient:.1f}",
                    'Accel Max (m/s²)': f"{max_accel:.2f}",
                    'Distance (m)': f"{distance_covered:.0f}",
                    'Puissance Max Est. (W)': f"{max_power:.0f}" if pd.notna(max_power) else "N/A"
                })

    return sprints
