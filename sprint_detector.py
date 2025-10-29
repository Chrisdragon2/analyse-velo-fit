# sprint_detector.py
import pandas as pd
import numpy as np
import streamlit as st

def detect_sprints(df, min_speed_kmh=40.0, min_gradient=-5.0, max_gradient=5.0, min_duration_sec=5, max_gap_sec=10):
    """
    Détecte les segments de sprint basés sur la vitesse et la pente,
    et fusionne les sprints rapprochés.

    Args:
        df (pd.DataFrame): DataFrame indexé par timestamp avec 'speed', 'distance', 'pente', 'delta_time'.
        min_speed_kmh (float): Vitesse minimale (km/h) pour être considéré en sprint.
        min_gradient (float): Pente moyenne minimale (%) pendant le sprint.
        max_gradient (float): Pente moyenne maximale (%) pendant le sprint.
        min_duration_sec (int): Durée minimale (secondes) pour qu'un effort soit classé comme sprint.
        max_gap_sec (int): Temps maximum (secondes) entre deux sprints pour les fusionner.

    Returns:
        list: Une liste de dictionnaires, chaque dictionnaire représentant un sprint (potentiellement fusionné).
    """
    sprints_final = []
    df_sprint = df.copy()

    # --- Vérification Colonnes ---
    required_cols = ['speed', 'distance', 'pente', 'delta_time']
    missing_cols = [col for col in required_cols if col not in df_sprint.columns]
    if missing_cols:
        st.warning(f"Colonnes manquantes : {', '.join(missing_cols)}. Détection sprint annulée.")
        return []
    # Assurer delta_speed pour calcul accel max
    if 'delta_speed' not in df_sprint.columns:
        df_sprint['delta_speed'] = df_sprint['speed'].diff().fillna(0)


    # --- 1. Détection des Sprints Initiaux (non fusionnés) ---
    min_speed_ms = min_speed_kmh / 3.6
    df_sprint['is_high_speed'] = (df_sprint['speed'] >= min_speed_ms)
    df_sprint['high_speed_block'] = (df_sprint['is_high_speed'] != df_sprint['is_high_speed'].shift()).cumsum()
    high_speed_segments_groups = df_sprint[df_sprint['is_high_speed']].groupby('high_speed_block')

    initial_sprints_data = [] # Stocke les infos des sprints valides AVANT fusion

    for block_id, segment_orig in high_speed_segments_groups:
        segment = segment_orig.copy()
        if len(segment) > 1: duration = (segment.index[-1] - segment.index[0]).total_seconds() + segment['delta_time'].iloc[-1]
        elif len(segment) == 1: duration = segment['delta_time'].iloc[0]
        else: continue

        if duration >= min_duration_sec:
            avg_gradient = segment['pente'].mean()
            if min_gradient <= avg_gradient <= max_gradient:
                initial_sprints_data.append({
                    'start_time': segment.index[0],
                    'end_time': segment.index[-1],
                    'segment_data': segment # Garde les données pour recalculer après fusion
                })

    if not initial_sprints_data:
        return [] # Aucun sprint initial trouvé

    # --- 2. Logique de Fusion ---
    merged_sprints_data = []
    if not initial_sprints_data: return []

    current_merged_sprint = initial_sprints_data[0] # Commence avec le premier

    for i in range(1, len(initial_sprints_data)):
        previous_sprint = current_merged_sprint
        next_sprint = initial_sprints_data[i]

        # Calculer le gap temporel
        time_gap = (next_sprint['start_time'] - previous_sprint['end_time']).total_seconds()

        if time_gap <= max_gap_sec:
            # Fusionner : étend la fin et concatène les données
            current_merged_sprint['end_time'] = next_sprint['end_time']
            # On doit récupérer les données entre les deux sprints pour le recalcul
            all_data_between = df_sprint.loc[previous_sprint['start_time']:next_sprint['end_time']]
            current_merged_sprint['segment_data'] = all_data_between
        else:
            # Pas de fusion, enregistre le sprint fusionné précédent et commence un nouveau
            merged_sprints_data.append(current_merged_sprint)
            current_merged_sprint = next_sprint

    # Ajouter le dernier sprint (qui n'a pas été suivi d'un autre ou n'a pas fusionné)
    merged_sprints_data.append(current_merged_sprint)


    # --- 3. Calcul des Statistiques Finales (sur les sprints fusionnés) ---
    for i, merged_sprint in enumerate(merged_sprints_data):
        segment = merged_sprint['segment_data'].copy() # Utilise les données (potentiellement fusionnées)

        # Recalculer les statistiques sur le segment potentiellement élargi
        start_time = segment.index[0]
        end_time = segment.index[-1]
        # Recalculer la durée sur le segment final
        duration = (end_time - start_time).total_seconds() + segment['delta_time'].iloc[-1]

        # Recalculer les autres stats sur ce segment
        peak_speed_kmh = segment['speed'].max() * 3.6
        avg_speed_kmh = segment['speed'].mean() * 3.6
        avg_gradient = segment['pente'].mean() # Pente moyenne du segment total
        start_distance_km = segment['distance'].iloc[0] / 1000

        # Recalculer delta_distance sur le segment fusionné
        segment['delta_distance'] = segment['distance'].diff().fillna(0)
        distance_covered = segment['delta_distance'].sum()

        max_power = segment['estimated_power'].max() if 'estimated_power' in segment.columns and not segment['estimated_power'].isnull().all() else np.nan

        # Recalculer Accel Max sur le segment fusionné
        if 'delta_speed' not in segment.columns: segment['delta_speed'] = segment['speed'].diff().fillna(0)
        segment['acceleration'] = np.where(segment['delta_time'] == 0, 0, segment['delta_speed'] / segment['delta_time'])
        max_accel = segment['acceleration'].max()

        sprints_final.append({
            'Début': start_time, # Garde le Timestamp pour le graphique
            'Début (km)': f"{start_distance_km:.1f}", # Pour l'affichage tableau
            'Durée (s)': f"{duration:.1f}",
            'Vitesse Max (km/h)': f"{peak_speed_kmh:.1f}",
            'Vitesse Moy (km/h)': f"{avg_speed_kmh:.1f}",
            'Pente Moy (%)': f"{avg_gradient:.1f}",
            'Accel Max (m/s²)': f"{max_accel:.2f}",
            'Distance (m)': f"{distance_covered:.0f}",
            'Puissance Max Est. (W)': f"{max_power:.0f}" if pd.notna(max_power) else "N/A"
        })

    return sprints_final
