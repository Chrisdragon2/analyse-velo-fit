# power_estimator.py
import pandas as pd
import numpy as np
import streamlit as st # Nécessaire pour st.warning

# --- CONSTANTES PHYSIQUES ---
GRAVITY = 9.80665

# --- FONCTION D'ESTIMATION DE PUISSANCE ---
def estimate_power(df, total_weight_kg, crr, cda):
    """Estime la puissance en Watts seconde par seconde."""

    # S'assurer que les colonnes nécessaires sont numériques
    required_cols = ['altitude', 'speed', 'distance', 'temperature']
    missing_cols = [col for col in required_cols if col not in df.columns or not pd.api.types.is_numeric_dtype(df[col])]
    if missing_cols:
        st.warning(f"Colonnes manquantes ou non numériques pour l'estimation de puissance : {', '.join(missing_cols)}. Estimation annulée.")
        # Retourner un DataFrame avec une colonne vide pour éviter les erreurs
        return pd.DataFrame(index=df.index, data={'estimated_power': np.nan})

    df_power = df.copy()

    # Calculer les deltas
    # Assurer que l'index est bien un DatetimeIndex pour .diff().dt.total_seconds()
    if not isinstance(df_power.index, pd.DatetimeIndex):
         st.error("L'index du DataFrame n'est pas un DatetimeIndex. Impossible de calculer delta_time.")
         return pd.DataFrame(index=df.index, data={'estimated_power': np.nan})

    df_power['delta_time'] = df_power.index.to_series().diff().dt.total_seconds().fillna(1.0).clip(lower=0.1)
    df_power['delta_altitude'] = df_power['altitude'].diff().fillna(0)
    df_power['delta_distance'] = df_power['distance'].diff().fillna(0)
    df_power['delta_speed'] = df_power['speed'].diff().fillna(0)

    # Gradient (pente)
    window_size = 5
    rolling_dist = df_power['delta_distance'].rolling(window=window_size, min_periods=1).sum()
    rolling_alt = df_power['delta_altitude'].rolling(window=window_size, min_periods=1).sum()
    df_power['gradient'] = np.where(rolling_dist == 0, 0, rolling_alt / rolling_dist)
    df_power['gradient'] = df_power['gradient'].clip(-0.5, 0.5)

    # Accélération
    df_power['acceleration'] = df_power['delta_speed'] / df_power['delta_time']

    # Densité de l'air
    temp_kelvin = df_power['temperature'].fillna(15) + 273.15
    altitude_m = df_power['altitude'].fillna(df_power['altitude'].mean())
    df_power['air_density'] = (1.225 * np.exp(-0.0001185 * altitude_m) * (288.15 / temp_kelvin))

    # Calcul des Forces
    mass = total_weight_kg
    speed_ms = df_power['speed']
    F_rr = crr * mass * GRAVITY
    F_ad = 0.5 * cda * df_power['air_density'] * (speed_ms ** 2)
    F_g = mass * GRAVITY * df_power['gradient']
    F_a = mass * df_power['acceleration']

    # Puissance
    power_gross = (F_rr + F_ad + F_g + F_a) * speed_ms
    df_power['estimated_power'] = np.maximum(0, power_gross)
    df_power['estimated_power'] = df_power['estimated_power'].rolling(window=3, min_periods=1, center=True).mean().fillna(0)

    return df_power[['estimated_power']] # Retourne seulement la nouvelle colonne