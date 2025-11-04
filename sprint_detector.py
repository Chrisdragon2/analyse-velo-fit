# sprint_detector.py
import pandas as pd
import numpy as np
import streamlit as st

def detect_sprints(df, min_speed_kmh=40.0, min_gradient=-5.0, max_gradient=5.0, min_duration_sec=5, max_gap_distance_m=50, rewind_sec=10):
    """
    Détecte les segments de sprint (avec fusion et rembobinage V-min).
    
    Args:
        df (pd.DataFrame): DataFrame analysé (avec pente, deltas...).
        min_speed_kmh (float): Seuil de vitesse pour déclencher la détection.
        min_gradient (float): Pente min.
        max_gradient (float): Pente max.
        min_duration_sec (int): Durée min. de la phase "officielle" (haute vitesse).
        max_gap_distance_m (int): Distance max. pour fusionner deux sprints.
        rewind_sec (int): Secondes à rembobiner avant le début officiel pour trouver V-min.
    """
    sprints_final = []
    df_sprint = df.copy()

    # --- Vérification Colonnes ---
    required_cols = ['speed', 'distance', 'pente', 'delta_time', 'delta_speed']
    missing_cols = [col for col in required_cols if col not in df_sprint.columns]
    if missing_cols:
        st.warning(f"Colonnes manquantes : {', '.join(missing_cols)}. Détection sprint annulée.")
        return []

    # --- 1. Détection des Sprints Initiaux (Segments "Officiels") ---
    min_speed_ms = min_speed_kmh / 3.6
    df_sprint['is_high_speed'] = (df_sprint['speed'] >= min_speed_ms)
    df_sprint['high_speed_block'] = (df_sprint['is_high_speed'] != df_sprint['is_high_speed'].shift()).cumsum()
    high_speed_segments_groups = df_sprint[df_sprint['is_high_speed']].groupby('high_speed_block')

    initial_sprints_data = []
    for block_id, segment_orig in high_speed_segments_groups:
        segment = segment_orig.copy()
        duration = (segment.index[-1] - segment.index[0]).total_seconds() + segment['delta_time'].iloc[-1] if not segment.empty else 0
        if duration >= min_duration_sec:
            avg_gradient = segment['pente'].mean()
            if min_gradient <= avg_gradient <= max_gradient:
                initial_sprints_data.append({
                    'block_id': block_id,
                    'start_time': segment.index[0], 'end_time': segment.index[-1],
                    'start_distance': segment['distance'].iloc[0], 'end_distance': segment['distance'].iloc[-1],
                })
    if not initial_sprints_data: return []

    # --- 2. Logique de Fusion par DISTANCE ---
    merged_sprints_segments = [] # Stocke les segments de DF fusionnés
    df_sprint_blocs = pd.DataFrame(initial_sprints_data)
    bloc_map = {}; current_merged_id = 0
    if df_sprint_blocs.empty: return []

    for i in range(len(df_sprint_blocs)):
        current_sprint_bloc = df_sprint_blocs.iloc[i]
        if current_sprint_bloc['block_id'] in bloc_map: continue
        current_merged_id += 1
        bloc_map[current_sprint_bloc['block_id']] = current_merged_id
        
        start_time_fusion = current_sprint_bloc['start_time']
        end_time_fusion = current_sprint_bloc['end_time']
        
        j = i + 1
        while j < len(df_sprint_blocs):
            next_sprint_bloc = df_sprint_blocs.iloc[j]
            gap_start_dist = next_sprint_bloc['start_distance']
            gap_end_dist = df_sprint_blocs.iloc[j-1]['end_distance']
            distance_gap = gap_start_dist - gap_end_dist
            
            if distance_gap >= 0 and distance_gap <= max_gap_distance_m:
                end_time_fusion = next_sprint_bloc['end_time'] # Étend la fin
                bloc_map[next_sprint_bloc['block_id']] = current_merged_id
                j += 1
            else:
                break
        
        # Sélectionner le segment complet (incluant la récup fusionnée)
        segment = df_sprint.loc[start_time_fusion:end_time_fusion]
        merged_sprints_segments.append(segment)

    # --- 3. Calcul des Statistiques Finales (avec Rembobinage V-min) ---
    for i, segment_officiel in enumerate(merged_sprints_segments):
        
        # 1. Définir le segment "officiel"
        official_start_time = segment_officiel.index[0]
        official_end_time = segment_officiel.index[-1]

        # 2. "Rembobiner" pour trouver le V-min
        search_window_start = official_start_time - pd.Timedelta(seconds=rewind_sec)
        if search_window_start < df_sprint.index[0]:
            search_window_start = df_sprint.index[0]
        
        pre_sprint_window = df_sprint.loc[search_window_start:official_start_time]
        
        # 3. Trouver le nouveau début
        if not pre_sprint_window.empty:
            v_min_start_time = pre_sprint_window['speed'].idxmin()
        else:
            v_min_start_time = official_start_time # Sécurité

        # 4. Créer le segment FINAL (de V-min à la fin officielle)
        segment = df_sprint.loc[v_min_start_time:official_end_time].copy()
        
        # 5. Calculer les stats sur ce segment FINAL
        if segment.empty: continue
            
        start_time = segment.index[0]; end_time = segment.index[-1]
        duration = (end_time - start_time).total_seconds() + segment['delta_time'].iloc[-1]
        peak_speed_kmh = segment['speed'].max() * 3.6
        avg_speed_kmh = segment['speed'].mean() * 3.6
        avg_gradient = segment['pente'].mean()
        start_distance_km = segment['distance'].iloc[0] / 1000
        end_distance_km = segment['distance'].iloc[-1] / 1000
        
        segment['delta_distance'] = segment['distance'].diff().fillna(0)
        distance_covered = segment['delta_distance'].sum()
        max_power = segment['estimated_power'].max() if 'estimated_power' in segment.columns and not segment['estimated_power'].isnull().all() else np.nan
        
        segment['acceleration'] = np.where(segment['delta_time'] == 0, 0, segment['delta_speed'] / segment['delta_time'])
        max_accel = segment['acceleration'].max()
        
        sprints_final.append({
            'Début': start_time, # Timestamp de V-min (pour le graphique)
            'Début (km)': f"{start_distance_km:.3f}", 
            'Fin (km)': f"{end_distance_km:.3f}",
            'Durée (s)': f"{duration:.1f}",
            'Vitesse Max (km/h)': f"{peak_speed_kmh:.1f}",
            'Vitesse Moy (km/h)': f"{avg_speed_kmh:.1f}",
            'Pente Moy (%)': f"{avg_gradient:.1f}",
            'Accel Max (m/s²)': f"{max_accel:.2f}",
            'Distance (m)': f"{distance_covered:.0f}",
            'Puissance Max Est. (W)': f"{max_power:.0f}" if pd.notna(max_power) else "N/A"
        })
        
    return sprints_final
