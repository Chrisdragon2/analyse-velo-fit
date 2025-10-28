import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.colors
from fitparse import FitFile
import io

# --- Importations depuis les modules ---
from data_loader import load_and_clean_data
from power_estimator import estimate_power
from climb_processing import (
    calculate_derivatives,
    identify_and_filter_initial_climbs,
    group_and_merge_climbs,
    calculate_climb_summary
)
from plotting import create_climb_figure

# --- Fonction simplifiée pour estimer Crr (à mettre ici ou dans un autre module) ---
def estimate_crr_from_width(width_mm):
    """Estimation TRES simplifiée du Crr basée sur la largeur du pneu."""
    # Exemple de logique: Plus large = plus de résistance (simplification)
    # Route lisse = base 0.004
    # Ajoute un peu pour chaque mm au-dessus de 25mm
    base_crr = 0.004
    additional_crr_per_mm = 0.0001
    if width_mm > 25:
        return base_crr + (width_mm - 25) * additional_crr_per_mm
    else:
        return base_crr # Ou ajuster pour pneus très fins

# --- CORPS PRINCIPAL DE L'APPLICATION STREAMLIT ---
def main_app():
    st.set_page_config(layout="wide")
    st.title("🚴 Analyseur d'Ascensions FIT")
    st.markdown("Chargez votre fichier FIT pour analyser vos performances en côte, y compris une estimation de la puissance. Utilisez la barre d'outils sur le graphique pour zoomer.")

    # --- INPUT UTILISATEUR ---
    with st.sidebar:
        st.header("1. Charger le Fichier")
        uploaded_file = st.file_uploader("Choisissez un fichier .fit", type="fit")

        st.header("2. Paramètres Physiques")
        cyclist_weight_kg = st.number_input("Poids du Cycliste (kg)", 30.0, 150.0, 68.0, 0.5)
        bike_weight_kg = st.number_input("Poids du Vélo + Équipement (kg)", 3.0, 25.0, 9.0, 0.1)
        total_weight_kg = cyclist_weight_kg + bike_weight_kg
        st.markdown(f"_(Poids total calculé : {total_weight_kg:.1f} kg)_")

        # --- MODIFIÉ : Largeur du pneu manuelle ---
        tire_width_mm = st.number_input("Largeur des Pneus (mm)", min_value=20, max_value=60, value=28, step=1)
        # Estimation du Crr basée sur la largeur entrée
        crr_value = estimate_crr_from_width(tire_width_mm)
        st.markdown(f"_(Crr estimé : {crr_value:.4f})_")
        # --- FIN MODIFICATION ---

        # Taille des roues (reste informatif)
        wheel_size_options = ["700c (Route/Gravel)", "650b (Gravel/VTT)", "26\" (VTT ancien)", "29\" (VTT moderne)"]
        selected_wheel_size = st.selectbox("Taille des Roues (approximative)", options=wheel_size_options)

        cda_value = 0.38 # Pour position cocottes
        st.markdown(f"**Position :** Cocottes (CdA estimé : {cda_value} m²)")

        st.header("3. Paramètres de Détection")
        min_climb_distance = st.slider("Longueur min. montée (m)", 100, 1000, 400, 50)
        min_pente = st.slider("Pente min. (%)", 1.0, 5.0, 3.0, 0.5)
        max_gap = st.slider("Fusion max. gap (m)", 50, 500, 200, 50)

    # --- TRAITEMENT DES DONNÉES ---
    if uploaded_file is not None:
        df, error_msg = load_and_clean_data(uploaded_file)
        if df is None: st.error(f"Erreur chargement : {error_msg}"); return

        # Calculer puissance (utilise le crr_value estimé à partir de la largeur)
        df_power_est = estimate_power(df, total_weight_kg, crr_value, cda_value)
        df = df.join(df_power_est)

        # Enchaînement des fonctions d'analyse
        analysis_error = None
        try:
            df_analyzed = calculate_derivatives(df.copy())
            df_analyzed = identify_and_filter_initial_climbs(df_analyzed, min_pente)
            montees_grouped, df_blocs, bloc_map = group_and_merge_climbs(df_analyzed, max_gap)
            resultats_montées = calculate_climb_summary(montees_grouped, min_climb_distance)
            resultats_df = pd.DataFrame(resultats_montées)
        except Exception as e:
            analysis_error = f"Erreur pendant l'analyse des montées : {e}"
            st.error(analysis_error)
            resultats_df = pd.DataFrame(); montees_grouped = None; resultats_montées = []; df_analyzed = df

        # Déterminer alt_col_to_use
        alt_col_to_use = 'altitude'
        if 'altitude_lisse' in df_analyzed.columns and not df_analyzed['altitude_lisse'].isnull().all():
             alt_col_to_use = 'altitude_lisse'

        # --- AFFICHAGE TABLEAU ---
        st.header("📈 Tableau de Bord")
        if resultats_df.empty and not analysis_error:
            st.warning(f"Aucune ascension ({min_climb_distance}m+, {min_pente}%+) trouvée.")
        elif not resultats_df.empty:
            st.dataframe(resultats_df.drop(columns=['index'], errors='ignore'), use_container_width=True)

            # --- AFFICHAGE GRAPHIQUES ---
            st.header("🗺️ Profils Détaillés")
            if montees_grouped is not None:
                processed_results_count = 0
                montee_ids = list(montees_grouped.groups.keys())
                valid_climb_data = []
                for nom_bloc in montee_ids:
                     segment = montees_grouped.get_group(nom_bloc)
                     if 'delta_distance' not in segment.columns:
                          segment = segment.copy(); segment['delta_distance'] = segment['distance'].diff().fillna(0)
                     distance_segment = segment['delta_distance'].sum()
                     if distance_segment >= min_climb_distance:
                         if processed_results_count < len(resultats_montées):
                            valid_climb_data.append((processed_results_count, segment))
                            processed_results_count += 1
                         else: st.warning(f"Incohérence détectée."); break
                for index_resultat, df_climb_original in valid_climb_data:
                    try:
                        fig = create_climb_figure(df_climb_original.copy(), alt_col_to_use, 100, resultats_montées, index_resultat)
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.error(f"Erreur création graphique ascension {index_resultat+1}.")
                        st.exception(e)
            else:
                 st.warning("Aucun groupe de montées traité.")
    else:
        st.info("Veuillez charger un fichier .fit pour commencer.")

# Point d'entrée
if __name__ == "__main__":
    main_app()
