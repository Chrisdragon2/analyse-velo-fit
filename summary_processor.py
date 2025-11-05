# summary_processor.py
import pandas as pd
import numpy as np

def calculate_global_summary(df, session_data):
    """
    Calcule les métriques globales de la sortie à partir des données 'record' (df)
    et des données 'session' (résumé du compteur).
    """
    summary = {}

    try:
        # --- Données Principales ---
        summary['dist_totale_km'] = session_data.get('total_distance', df['distance'].iloc[-1]) / 1000
        summary['d_plus'] = session_data.get('total_ascent', df['altitude'].diff().clip(lower=0).sum())
        
        # Temps de déplacement (officiel ou calculé)
        temps_deplacement_sec = session_data.get('total_moving_time', len(df[df['speed'] > 1.0]))
        temps_deplacement_str = str(pd.to_timedelta(temps_deplacement_sec, unit='s')).split(' ')[-1].split('.')[0]
        summary['temps_deplacement_str'] = temps_deplacement_str
        
        # Vitesse moyenne (officielle ou calculée)
        v_moy_session = session_data.get('avg_speed', 0) 
        if v_moy_session > 0:
            summary['vitesse_moy_kmh'] = v_moy_session * 3.6 # Conversion m/s -> km/h
        else:
            summary['vitesse_moy_kmh'] = (summary['dist_totale_km'] * 1000 / temps_deplacement_sec) * 3.6 if temps_deplacement_sec > 0 else 0

        # --- Données Secondaires ---
        summary['v_max_kmh'] = session_data.get('max_speed', df['speed'].max()) * 3.6
        summary['avg_hr'] = session_data.get('avg_heart_rate')
        summary['max_hr'] = session_data.get('max_heart_rate')
        
        # Cadence (avec fallback)
        avg_cad = session_data.get('avg_cadence')
        max_cad = session_data.get('max_cadence')
        if 'cadence' in df.columns and not avg_cad and not df[df['cadence'] > 0].empty:
            avg_cad = df[df['cadence'] > 0]['cadence'].mean()
        if 'cadence' in df.columns and not max_cad:
            max_cad = df['cadence'].max()
        summary['avg_cad'] = avg_cad
        summary['max_cad'] = max_cad

        # --- Puissance Estimée ---
        if 'estimated_power' in df.columns and not df['estimated_power'].isnull().all():
            summary['power_avg_est'] = df['estimated_power'].mean()
            summary['power_max_est'] = df['estimated_power'].max()
        else:
            summary['power_avg_est'] = np.nan
            summary['power_max_est'] = np.nan
            
        return summary, None # Retourne le résumé, pas d'erreur

    except Exception as e:
        return {}, f"Impossible de calculer le résumé : {e}" # Retourne un dict vide et une erreur
