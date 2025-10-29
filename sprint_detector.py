# sprint_detector.py (Version corrigée de la fusion)
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
        # Utiliser print() au lieu de st.warning() pour le test notebook
        print(f"AVERTISSEMENT: Colonnes manquantes : {', '.join(missing_cols)}. Détection sprint annulée.")
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
    if not initial_sprints_data: return []

    # --- 2. Logique de Fusion par DISTANCE (CORRIGÉE) ---
    print("\n--- DEBUG FUSION SPRINTS (Final) ---")
    
    df_sprint_blocs = pd.DataFrame(initial_sprints_data)
    merged_sprints_data = []
    bloc_map = {}
    current_merged_id = 0

    if df_sprint_blocs.empty: return []

    for i in range(len(df_sprint_blocs)):
        current_sprint_bloc = df_sprint_blocs.iloc[i]
        
        if current_sprint_bloc['block_id'] in bloc_map:
            continue
            
        current_merged_id += 1
        bloc_map[current_sprint_bloc['block_id']] = current_merged_id
        
        # Trouver la première et la dernière ligne du segment à fusionner
        start_time_fusion = current_sprint_bloc['start_time']
        end_time_fusion = current_sprint_bloc['end_time']
        
        # Le segment fusionné commence avec ce bloc
        j = i + 1
        while j < len(df_sprint_blocs):
            next_sprint_bloc = df_sprint_blocs.iloc[j]
            
            # --- CALCUL DU GAP EN DISTANCE ---
            gap_start_dist = next_sprint_bloc['start_distance']
            gap_end_dist = df_sprint_blocs.iloc[j-1]['end_distance'] # Fin du bloc précédent initial
            distance_gap = gap_start_dist - gap_end_dist
            
            # Pour le debug, on utilise la fin de l'intervalle TEMP de fusion, pour éviter confusion
            print(f"DEBUG: Fin Précédent (Temp): {gap_end_dist:.0f}m, Début Suivant: {gap_start_dist:.0f}m, Gap: {distance_gap:.0f}m")
            
            if distance_gap >= 0 and distance_gap <= max_gap_distance_m:
                print(f"   -> Fusion (Gap {distance_gap:.0f}m <= {max_gap_distance_m}m)")
                
                # METTRE À JOUR LA FIN DU SEGMENT FUSIONNÉ avec la fin du NOUVEAU bloc
                end_time_fusion = next_sprint_bloc['end_time'] 
                
                # Marquer le bloc suivant comme fusionné
                bloc_map[next_sprint_bloc['block_id']] = current_merged_id
                j += 1
            else:
                print(f"   -> Pas de fusion (Gap {distance_gap:.0f}m > {max_gap_distance_m}m)")
                break
        
        # Sélectionner TOUTES les données du début du premier bloc à la fin du dernier bloc fusionné
        # C'est la ligne la plus cruciale pour obtenir toutes les colonnes requises (y compris la pente)
        segment = df_sprint.loc[start_time_fusion:end_time_fusion]
        merged_sprints_data.append(segment)

    print("--- FIN DEBUG FUSION ---\n")

    # --- 3. Calcul des Statistiques Finales ---
    for i, segment in enumerate(merged_sprints_data): # segment est maintenant un DataFrame
        
        # Sécurité: s'assurer que le segment n'est pas vide
        if segment.empty: continue
            
        start_time = segment.index[0]; end_time = segment.index[-1]
        
        # Utiliser .iloc[-1] est plus sûr que .loc[end_time] pour delta_time
        duration = (end_time - start_time).total_seconds() + segment['delta_time'].iloc[-1]
        
        peak_speed_kmh = segment['speed'].max() * 3.6
        avg_speed_kmh = segment['speed'].mean() * 3.6
        avg_gradient = segment['pente'].mean()
        
        start_distance_km = segment['distance'].iloc[0] / 1000
        end_distance_km = segment['distance'].iloc[-1] / 1000
        
        segment['delta_distance'] = segment['distance'].diff().fillna(0)
        distance_covered = segment['delta_distance'].sum()
        max_power = segment['estimated_power'].max() if 'estimated_power' in segment.columns and not segment['estimated_power'].isnull().all() else np.nan
        
        if 'delta_speed' not in segment.columns: segment['delta_speed'] = segment['speed'].diff().fillna(0)
        if 'delta_time' not in segment.columns:
            if isinstance(segment.index, pd.DatetimeIndex): segment['delta_time'] = segment.index.to_series().diff().dt.total_seconds().fillna(1.0).clip(lower=0.1)
            else: segment['delta_time'] = 1.0
        
        segment['acceleration'] = np.where(segment['delta_time'] == 0, 0, segment['delta_speed'] / segment['delta_time'])
        max_accel = segment['acceleration'].max()
        
        sprints_final.append({
            'Début': start_time,
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
