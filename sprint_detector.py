# sprint_detector.py
import pandas as pd
import numpy as np
import streamlit as st

def detect_sprints(df, min_speed_kmh=40.0, min_gradient=-5.0, max_gradient=5.0, min_duration_sec=5, max_gap_distance_m=50):
    """
    Détecte les segments de sprint (avec fusion par distance CORRIGÉE).
    """
    sprints_final = []
    df_sprint = df.copy()

    # --- Vérification Colonnes ---
    required_cols = ['speed', 'distance', 'pente', 'delta_time']
    missing_cols = [col for col in required_cols if col not in df_sprint.columns]
    if missing_cols:
        st.warning(f"Colonnes manquantes : {', '.join(missing_cols)}. Détection sprint annulée.")
        return []
    if 'delta_speed' not in df_sprint.columns:
        df_sprint['delta_speed'] = df_sprint['speed'].diff().fillna(0)

    # --- 1. Détection des Sprints Initiaux ---
    min_speed_ms = min_speed_kmh / 3.6
    df_sprint['is_high_speed'] = (df_sprint['speed'] >= min_speed_ms)
    df_sprint['high_speed_block'] = (df_sprint['is_high_speed'] != df_sprint['is_high_speed'].shift()).cumsum()
    high_speed_segments_groups = df_sprint[df_sprint['is_high_speed']].groupby('high_speed_block')

    initial_sprints_data = []
    for block_id, segment_orig in high_speed_segments_groups:
        segment = segment_orig.copy()
        if len(segment) > 1: duration = (segment.index[-1] - segment.index[0]).total_seconds() + segment['delta_time'].iloc[-1]
        elif len(segment) == 1: duration = segment['delta_time'].iloc[0]
        else: continue
        if duration >= min_duration_sec:
            avg_gradient = segment['pente'].mean()
            if min_gradient <= avg_gradient <= max_gradient:
                initial_sprints_data.append({
                    'block_id': block_id,
                    'start_time': segment.index[0], 'end_time': segment.index[-1],
                    'start_distance': segment['distance'].iloc[0], 'end_distance': segment['distance'].iloc[-1],
                })
    if not initial_sprints_data:
        return []

    # --- 2. Logique de Fusion par DISTANCE (CORRIGÉE) ---
    merged_sprints_data = []
    if not initial_sprints_data: return []
    df_sprint_blocs = pd.DataFrame(initial_sprints_data) # Convertir en DataFrame pour accès plus facile
    bloc_map = {}
    current_merged_id = 0

    for i in range(len(df_sprint_blocs)):
        current_sprint_bloc = df_sprint_blocs.iloc[i]
        if current_sprint_bloc['block_id'] in bloc_map: continue
        
        current_merged_id += 1
        bloc_map[current_sprint_bloc['block_id']] = current_merged_id
        
        # Le segment fusionné commence avec ce bloc
        # Il est crucial de récupérer les données depuis df_sprint pour inclure la pente, vitesse, etc.
        merged_segment_data = df_sprint[df_sprint['high_speed_block'] == current_sprint_bloc['block_id']]
        
        j = i + 1
        while j < len(df_sprint_blocs):
            next_sprint_bloc = df_sprint_blocs.iloc[j]
            
            # Utiliser la fin du segment de données fusionné actuel
            gap_start = next_sprint_bloc['start_distance']
            gap_end = merged_segment_data['distance'].iloc[-1] # Fin du dernier segment de données ajouté
            distance_gap = gap_start - gap_end
            
            if distance_gap >= 0 and distance_gap <= max_gap_distance_m:
                # Fusionner : récupérer TOUTES les données entre la fin du segment précédent et la fin du suivant
                segment_a_ajouter = df_sprint.loc[gap_end:next_sprint_bloc['end_time']]
                # Concaténer en enlevant le premier point (doublon)
                merged_segment_data = pd.concat([merged_segment_data, segment_a_ajouter.iloc[1:]])
                bloc_map[next_sprint_bloc['block_id']] = current_merged_id
                j += 1
            else:
                break
        
        merged_sprints_data.append(merged_segment_data) # Stocker le DataFrame fusionné

    # --- 3. Calcul des Statistiques Finales ---
    for i, segment in enumerate(merged_sprints_data):
        
        start_time = segment.index[0]; end_time = segment.index[-1]
        duration = (end_time - start_time).total_seconds() + segment['delta_time'].iloc[-1] if not segment.empty else 0
        peak_speed_kmh = segment['speed'].max() * 3.6 if not segment.empty else 0
        avg_speed_kmh = segment['speed'].mean() * 3.6 if not segment.empty else 0
        avg_gradient = segment['pente'].mean() if not segment.empty else 0
        
        # --- MODIFIÉ : Calculer début et fin en km ---
        start_distance_km = segment['distance'].iloc[0] / 1000 if not segment.empty else 0
        end_distance_km = segment['distance'].iloc[-1] / 1000 if not segment.empty else 0
        
        segment['delta_distance'] = segment['distance'].diff().fillna(0)
        distance_covered = segment['delta_distance'].sum()
        max_power = segment['estimated_power'].max() if 'estimated_power' in segment.columns and not segment['estimated_power'].isnull().all() else np.nan
        
        if 'delta_speed' not in segment.columns: segment['delta_speed'] = segment['speed'].diff().fillna(0)
        if 'delta_time' not in segment.columns:
            if isinstance(segment.index, pd.DatetimeIndex): segment['delta_time'] = segment.index.to_series().diff().dt.total_seconds().fillna(1.0).clip(lower=0.1)
            else: segment['delta_time'] = 1.0
        
        segment['acceleration'] = np.where(segment['delta_time'] == 0, 0, segment['delta_speed'] / segment['delta_time'])
        max_accel = segment['acceleration'].max() if not segment.empty else 0
        
        sprints_final.append({
            'Début': start_time,
            # --- MODIFIÉ : Formater avec 3 décimales ---
            'Début (km)': f"{start_distance_km:.3f}", 
            'Fin (km)': f"{end_distance_km:.3f}", # Nouvelle colonne
            'Durée (s)': f"{duration:.1f}",
            'Vitesse Max (km/h)': f"{peak_speed_kmh:.1f}",
            'Vitesse Moy (km/h)': f"{avg_speed_kmh:.1f}",
            'Pente Moy (%)': f"{avg_gradient:.1f}",
            'Accel Max (m/s²)': f"{max_accel:.2f}",
            'Distance (m)': f"{distance_covered:.0f}",
            'Puissance Max Est. (W)': f"{max_power:.0f}" if pd.notna(max_power) else "N/A"
        })
        
    return sprints_final
