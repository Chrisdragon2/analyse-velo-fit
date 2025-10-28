import streamlit as st
import pandas as pd
import numpy as np

# --- Importations depuis les nouveaux modules ---
from data_loader import load_and_clean_data
from power_estimator import estimate_power
from climb_processing import (
    calculate_derivatives,
    identify_and_filter_initial_climbs,
    group_and_merge_climbs,
    calculate_climb_summary
)
from plotting import create_climb_figure

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
        total_weight_kg = st.number_input("Poids Total (kg)", 30.0, 200.0, 75.0, 0.5)
        tire_options = {"Route (23-25mm) - Asphalte lisse": 0.004, "Route (28-32mm) - Asphalte variable": 0.005, "Gravel (35-40mm) - Mixte": 0.007, "VTT (2.1\"+) - Off-road": 0.012}
        selected_tire = st.selectbox("Type de Pneus/Surface", list(tire_options.keys()))
        crr_value = tire_options[selected_tire]; cda_value = 0.38
        st.markdown(f"**Position :** Cocottes (CdA estimé : {cda_value} m²)")
        st.header("3. Paramètres de Détection")
        min_climb_distance = st.slider("Longueur min. montée (m)", 100, 1000, 400, 50)
        min_pente = st.slider("Pente min. (%)", 1.0, 5.0, 3.0, 0.5)
        max_gap = st.slider("Fusion max. gap (m)", 50, 500, 200, 50)

    # --- TRAITEMENT DES DONNÉES ---
    if uploaded_file is not None:
        df, error_msg = load_and_clean_data(uploaded_file)
        if df is None: st.error(f"Erreur chargement : {error_msg}"); return

        # Calculer puissance
        df_power_est = estimate_power(df, total_weight_kg, crr_value, cda_value)
        df = df.join(df_power_est)

        # Enchaînement des fonctions d'analyse
        analysis_error = None
        try:
            df_analyzed = calculate_derivatives(df.copy())
            df_analyzed = identify_and_filter_initial_climbs(df_analyzed, min_pente)
            # Attention: group_and_merge_climbs retourne 3 valeurs maintenant
            montees_grouped, df_blocs, bloc_map = group_and_merge_climbs(df_analyzed, max_gap)
            resultats_montées = calculate_climb_summary(montees_grouped, min_climb_distance)
            resultats_df = pd.DataFrame(resultats_montées)
        except Exception as e:
            analysis_error = f"Erreur pendant l'analyse des montées : {e}"
            st.error(analysis_error)
            resultats_df = pd.DataFrame(); montees_grouped = None; resultats_montées = []
            df_analyzed = df # Revenir au df de base en cas d'erreur

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
                        # Utilise la fonction importée depuis plotting.py
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
