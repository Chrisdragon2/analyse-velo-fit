# sprint_detector.py
import pandas as pd
import numpy as np

def detect_sprints(df, min_accel=1.0, min_peak_speed_kmh=35.0, min_duration_sec=5):
    """
    Détecte les segments de sprint dans un DataFrame de sortie vélo.

    Args:
        df (pd.DataFrame): DataFrame indexé par timestamp avec colonnes 'speed', 'distance'.
                           Doit aussi avoir 'delta_time', 'delta_speed'.
        min_accel (float): Accélération minimale (m/s^2) pour considérer un sprint.
        min_peak_speed_kmh (float): Vitesse de pointe minimale (km/h) à atteindre pendant le sprint.
        min_duration_sec (int): Durée minimale (secondes) pour qu'un effort soit classé comme sprint.

    Returns:
        list: Une liste de dictionnaires, chaque dictionnaire représentant un sprint détecté
              avec ses statistiques (début, durée, Vmax, Vmoy, AccelMax, Distance, PowerMax).
    """
    sprints = []
    df_sprint = df.copy()

    # S'assurer que les colonnes nécessaires existent
    required_cols = ['speed', 'distance']
    if not all(col in df_sprint.columns for col in required_cols):
        print("Colonnes 'speed' ou 'distance' manquantes pour détecter les sprints.")
        return []

    # Calculer delta_time et delta_speed si absents
    if 'delta_time' not in df_sprint.columns:
         if not isinstance(df_sprint.index, pd.DatetimeIndex):
             # Essayer de convertir si nécessaire
             try: df_sprint.index = pd.to_datetime(df_sprint.index)
             except Exception: raise ValueError("Index non DatetimeIndex pour calculer delta_time")
         df_sprint['delta_time'] = df_sprint.index.to_series().diff().dt.total_seconds().fillna(1.0).clip(lower=0.1)

    if 'delta_speed' not in df_sprint.columns:
        df_sprint['delta_speed'] = df_sprint['speed'].diff().fillna(0)

    # Calculer l'accélération
    df_sprint['acceleration'] = df_sprint['delta_speed'] / df_sprint['delta_time']
    # Lisser légèrement l'accélération pour éviter le bruit
    df_sprint['acceleration_smooth'] = df_sprint['acceleration'].rolling(window=3, center=True, min_periods=1).mean()

    # Identifier les moments potentiels de sprint (forte accélération)
    df_sprint['is_potential_sprint'] = (df_sprint['acceleration_smooth'] >= min_accel) & (df_sprint['speed'] * 3.6 > (min_peak_speed_kmh * 0.7)) # Vitesse déjà un peu élevée

    # Créer des blocs de sprint consécutifs
    df_sprint['sprint_block'] = (df_sprint['is_potential_sprint'] != df_sprint['is_potential_sprint'].shift()).cumsum()

    # Garder uniquement les blocs qui sont des sprints potentiels
    potential_sprint_segments = df_sprint[df_sprint['is_potential_sprint']]

    # Analyser chaque bloc
    for block_id, segment in potential_sprint_segments.groupby('sprint_block'):
        duration = (segment.index[-1] - segment.index[0]).total_seconds() + segment['delta_time'].iloc[-1] # Ajouter le dernier delta_time
        peak_speed_kmh = segment['speed'].max() * 3.6

        # Vérifier si le segment respecte les critères de durée et de vitesse de pointe
        if duration >= min_duration_sec and peak_speed_kmh >= min_peak_speed_kmh:
            start_time = segment.index[0]
            avg_speed_kmh = segment['speed'].mean() * 3.6
            max_accel = segment['acceleration'].max() # Prendre l'accel brute max
            distance_covered = segment['distance'].iloc[-1] - segment['distance'].iloc[0]

            # Ajouter puissance max si disponible
            max_power = segment['estimated_power'].max() if 'estimated_power' in segment.columns else np.nan

            sprints.append({
                'Début': start_time.strftime('%H:%M:%S'),
                'Durée (s)': f"{duration:.1f}",
                'Vitesse Max (km/h)': f"{peak_speed_kmh:.1f}",
                'Vitesse Moy (km/h)': f"{avg_speed_kmh:.1f}",
                'Accel Max (m/s²)': f"{max_accel:.2f}",
                'Distance (m)': f"{distance_covered:.0f}",
                'Puissance Max Est. (W)': f"{max_power:.0f}" if pd.notna(max_power) else "N/A"
            })

    return sprints