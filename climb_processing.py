# climb_processing.py
import pandas as pd
import numpy as np

# --- Constantes (peuvent être ajustées ou passées en arguments) ---
FENETRE_LISSAGE_SEC = 20
SEUIL_DISTANCE_MIN_BLOC_MONTEE = 100 # Anti-bruit

# --- Fonctions de Traitement ---

def calculate_derivatives(df):
    """Calcule l'altitude lissée, les deltas et la pente."""
    df_processed = df.copy()
    # S'assurer que l'index est datetime pour le rolling window
    if not isinstance(df_processed.index, pd.DatetimeIndex):
         # Tenter la conversion si ce n'est pas le cas (sécurité)
         try:
             df_processed.index = pd.to_datetime(df_processed.index)
         except Exception:
             raise ValueError("L'index doit être de type DatetimeIndex pour le lissage temporel.")

    df_processed['altitude_lisse'] = df_processed['altitude'].rolling(window=f'{FENETRE_LISSAGE_SEC}s').mean().ffill().bfill()
    df_processed['delta_distance'] = df_processed['distance'].diff().fillna(0)
    df_processed['delta_altitude'] = df_processed['altitude_lisse'].diff().fillna(0)
    df_processed['pente'] = np.where(df_processed['delta_distance'] == 0, 0, (df_processed['delta_altitude'] / df_processed['delta_distance']) * 100)
    df_processed['pente'] = df_processed['pente'].fillna(0)
    return df_processed

def identify_and_filter_initial_climbs(df, min_pente):
    """Identifie les blocs de montée bruts et filtre les segments trop courts."""
    df_processed = df.copy()
    df_processed['en_montee_brute'] = (df_processed['pente'] > min_pente)
    df_processed['bloc_initial'] = (df_processed['en_montee_brute'] != df_processed['en_montee_brute'].shift()).cumsum()

    bloc_distances = df_processed.groupby('bloc_initial')['delta_distance'].sum()
    is_climb_first = df_processed.groupby('bloc_initial')['en_montee_brute'].first()
    blocs_montée_courts = bloc_distances.loc[(bloc_distances < SEUIL_DISTANCE_MIN_BLOC_MONTEE) & (is_climb_first == True)].index

    df_processed['en_montee_filtree'] = df_processed['en_montee_brute']
    df_processed.loc[df_processed['bloc_initial'].isin(blocs_montée_courts), 'en_montee_filtree'] = False

    df_processed['bloc_a_fusionner'] = (df_processed['en_montee_filtree'] != df_processed['en_montee_filtree'].shift()).cumsum()
    return df_processed

def group_and_merge_climbs(df, max_gap_distance):
    """Groupe les segments filtrés et fusionne ceux séparés par un court replat."""
    blocs_data = []
    for bloc_id, segment in df.groupby('bloc_a_fusionner'):
        blocs_data.append({
            'bloc_id': bloc_id,
            'is_climb': segment['en_montee_filtree'].iloc[0],
            'distance': segment['delta_distance'].sum()
        })
    df_blocs = pd.DataFrame(blocs_data)

    merged_bloc_id = 0
    bloc_map = {}
    for i in range(len(df_blocs)):
        current_bloc = df_blocs.iloc[i]
        if current_bloc['bloc_id'] in bloc_map: continue
        bloc_map[current_bloc['bloc_id']] = merged_bloc_id
        if not current_bloc['is_climb']:
            merged_bloc_id += 1; continue
        j = i + 1
        while j < len(df_blocs) - 1:
            replat_bloc, next_climb_bloc = df_blocs.iloc[j], df_blocs.iloc[j+1]
            if not replat_bloc['is_climb'] and next_climb_bloc['is_climb']:
                if replat_bloc['distance'] < max_gap_distance:
                    bloc_map[replat_bloc['bloc_id']] = merged_bloc_id
                    bloc_map[next_climb_bloc['bloc_id']] = merged_bloc_id
                    j += 2
                else: break
            else: break
        merged_bloc_id += 1

    df['bloc_fusionne'] = df['bloc_a_fusionner'].map(bloc_map)
    climb_merged_ids = df_blocs.loc[df_blocs['is_climb'] == True, 'bloc_id'].map(bloc_map).unique()
    df_segments_a_garder = df[df['bloc_fusionne'].isin(climb_merged_ids)]

    # Utiliser observed=True si possible
    try:
        montees_grouped = df_segments_a_garder.groupby('bloc_fusionne', observed=True)
    except TypeError:
        montees_grouped = df_segments_a_garder.groupby('bloc_fusionne')

    return montees_grouped, df_blocs, bloc_map # Retourne le groupby et les infos de blocs

def calculate_climb_summary(montees_grouped, min_climb_distance):
    """Calcule les statistiques pour chaque montée valide et retourne une liste de résultats."""
    resultats_montees = []
    for nom_bloc, segment in montees_grouped:
        segment = segment.copy() # Travailler sur une copie
        distance_segment = segment['delta_distance'].sum()
        if distance_segment < min_climb_distance: continue

        # Calculs des stats (identiques à avant)
        altitude_debut, altitude_fin = segment['altitude'].iloc[0], segment['altitude'].iloc[-1]
        denivele = max(0, altitude_fin - altitude_debut); dist_debut_km = segment['distance'].iloc[0] / 1000
        pente_moyenne = np.where(distance_segment == 0, 0, (denivele / distance_segment) * 100)
        duree_secondes = (segment.index[-1] - segment.index[0]).total_seconds();
        if duree_secondes <= 0: continue
        duree_formatted = pd.to_timedelta(duree_secondes, unit='s'); vitesse_moyenne_kmh = (distance_segment / 1000) / (duree_secondes / 3600)
        fc_moyenne = segment['heart_rate'].mean() if 'heart_rate' in segment.columns else np.nan
        cadence_moyenne = segment['cadence'].mean() if 'cadence' in segment.columns else np.nan
        power_moyenne = segment['estimated_power'].mean() if 'estimated_power' in segment.columns else np.nan

        resultats_montees.append({
            'Début (km)': f"{dist_debut_km:.1f}", 'Distance (m)': f"{distance_segment:.0f}", 'Dénivelé (m)': f"{denivele:.0f}",
            'Pente (%)': f"{pente_moyenne:.1f}", 'Durée': str(duree_formatted).split('.')[0].replace('0 days ', ''),
            'Vitesse (km/h)': f"{vitesse_moyenne_kmh:.1f}",
            'FC Moy (bpm)': f"{fc_moyenne:.0f}" if pd.notna(fc_moyenne) else "N/A",
            'Cadence Moy': f"{cadence_moyenne:.0f}" if pd.notna(cadence_moyenne) else "N/A",
            'Puissance Est. (W)': f"{power_moyenne:.0f}" if pd.notna(power_moyenne) else "N/A"
        })
    return resultats_montees