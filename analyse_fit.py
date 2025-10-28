import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go # Importation spécifique ajoutée si besoin
import plotly.colors              # Importation spécifique ajoutée si besoin

# --- Importations depuis les modules ---
from data_loader import load_and_clean_data
from power_estimator import estimate_power
from climb_processing import (
    calculate_derivatives,
    identify_and_filter_initial_climbs,
    group_and_merge_climbs,
    calculate_climb_summary
)
# Importer les deux fonctions de plotting
from plotting import create_climb_figure, create_sprint_figure
# Importer la fonction de détection de sprint mise à jour
from sprint_detector import detect_sprints

# --- Fonction simplifiée pour estimer Crr ---
def estimate_crr_from_width(width_mm):
    """Estimation TRES simplifiée du Crr basée sur la largeur du pneu."""
    base_crr = 0.004
    additional_crr_per_mm = 0.0001
    if width_mm > 25:
        return base_crr + (width_mm - 25) * additional_crr_per_mm
    else:
        return base_crr

# --- CORPS PRINCIPAL DE L'APPLICATION STREAMLIT ---
def main_app():
    st.set_page_config(layout="wide")
    st.title("🚴 Analyseur d'Ascensions et Sprints FIT")
    st.markdown("Chargez votre fichier FIT pour analyser vos performances. Utilisez la barre d'outils sur les graphiques pour zoomer.")

    # --- INPUT UTILISATEUR ---
    with st.sidebar:
        st.header("1. Charger le Fichier")
        uploaded_file = st.file_uploader("Choisissez un fichier .fit", type="fit")

        st.header("2. Paramètres Physiques")
        cyclist_weight_kg = st.number_input("Poids du Cycliste (kg)", 30.0, 150.0, 68.0, 0.5)
        bike_weight_kg = st.number_input("Poids du Vélo + Équipement (kg)", 3.0, 25.0, 9.0, 0.1)
        total_weight_kg = cyclist_weight_kg + bike_weight_kg
        st.markdown(f"_(Poids total calculé : {total_weight_kg:.1f} kg)_")

        tire_width_mm = st.number_input("Largeur des Pneus (mm)", min_value=20, max_value=60, value=28, step=1)
        crr_value = estimate_crr_from_width(tire_width_mm)
        st.markdown(f"_(Crr estimé : {crr_value:.4f})_")

        wheel_size_options = ["700c (Route/Gravel)", "650b (Gravel/VTT)", "26\" (VTT ancien)", "29\" (VTT moderne)"]
        selected_wheel_size = st.selectbox("Taille des Roues (approximative)", options=wheel_size_options)

        cda_value = 0.38 # Pour position cocottes
        st.markdown(f"**Position :** Cocottes (CdA estimé : {cda_value} m²)")

        st.header("3. Paramètres de Détection des Montées")
        min_climb_distance = st.slider("Longueur min. montée (m)", 100, 1000, 400, 50, key="climb_dist")
        min_pente = st.slider("Pente min. (%)", 1.0, 5.0, 3.0, 0.5, key="climb_pente")
        max_gap = st.slider("Fusion max. gap (m)", 50, 500, 200, 50, key="climb_gap")

        # --- MODIFIÉ : Nouveaux Paramètres de Détection des Sprints ---
        st.header("4. Paramètres de Détection des Sprints")
        min_peak_speed_sprint = st.slider("Vitesse de pointe minimale (km/h)", 25.0, 60.0, 40.0, 1.0, key="sprint_speed")
        min_sprint_duration = st.slider("Durée minimale du sprint (s)", 3, 15, 5, 1, key="sprint_duration")
        slope_range_sprint = st.slider(
            "Plage de pente moyenne autorisée (%)",
            min_value=-10.0, max_value=10.0, value=(-5.0, 5.0), # Défaut -5% à +5%
            step=0.5, key="sprint_slope_range"
        )
        min_gradient_sprint = slope_range_sprint[0]
        max_gradient_sprint = slope_range_sprint[1]
        # --- FIN MODIFICATION ---

    # --- TRAITEMENT DES DONNÉES ---
    if uploaded_file is not None:
        df, error_msg = load_and_clean_data(uploaded_file)
        if df is None: st.error(f"Erreur chargement : {error_msg}"); return

        # Calculer puissance
        df_power_est = estimate_power(df, total_weight_kg, crr_value, cda_value)
        df = df.join(df_power_est)

        # Enchaînement des fonctions d'analyse des montées
        analysis_error = None
        montees_grouped = None # Initialiser
        resultats_montées = [] # Initialiser
        try:
            df_analyzed = calculate_derivatives(df.copy())
            df_analyzed = identify_and_filter_initial_climbs(df_analyzed, min_pente)
            montees_grouped, df_blocs, bloc_map = group_and_merge_climbs(df_analyzed, max_gap)
            resultats_montées = calculate_climb_summary(montees_grouped, min_climb_distance)
            resultats_df = pd.DataFrame(resultats_montées)
        except Exception as e:
            analysis_error = f"Erreur pendant l'analyse des montées : {e}"
            st.error(analysis_error)
            resultats_df = pd.DataFrame()
            df_analyzed = df # Revenir au df de base

        # --- MODIFIÉ : Détection des Sprints avec les nouveaux paramètres ---
        sprint_error = None
        try:
            # Passe df_analyzed (contient pente, deltas...) et les nouveaux seuils
            sprint_results = detect_sprints(
                df_analyzed,
                min_peak_speed_sprint, # Nouveau paramètre
                min_gradient_sprint, # Nouveau paramètre
                max_gradient_sprint, # Nouveau paramètre
                min_sprint_duration
            )
            sprints_df = pd.DataFrame(sprint_results)
        except Exception as e:
            sprint_error = f"Erreur pendant la détection des sprints : {e}"
            st.error(sprint_error)
            sprints_df = pd.DataFrame()
        # --- FIN MODIFICATION ---


        # Déterminer alt_col_to_use
        alt_col_to_use = 'altitude'
        if 'altitude_lisse' in df_analyzed.columns and not df_analyzed['altitude_lisse'].isnull().all():
             alt_col_to_use = 'altitude_lisse'

        # --- AFFICHAGE TABLEAU MONTÉES ---
        st.header("📈 Tableau de Bord des Montées")
        if resultats_df.empty and not analysis_error:
            st.warning(f"Aucune ascension ({min_climb_distance}m+, {min_pente}%+) trouvée.")
        elif not resultats_df.empty:
            st.dataframe(resultats_df.drop(columns=['index'], errors='ignore'), use_container_width=True)

        # --- AFFICHAGE GRAPHIQUES MONTÉES ---
        st.header("🗺️ Profils Détaillés des Montées")
        if montees_grouped is not None and not resultats_df.empty:
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
                     else: st.warning(f"Incohérence détectée (montées)."); break
            for index_resultat, df_climb_original in valid_climb_data:
                try:
                    fig = create_climb_figure(df_climb_original.copy(), alt_col_to_use, 100, resultats_montées, index_resultat)
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Erreur création graphique ascension {index_resultat+1}.")
                    st.exception(e)
        elif not analysis_error:
             st.info("Aucun profil de montée à afficher.")

        # --- NOUVEAU : AFFICHAGE TABLEAU SPRINTS ---
        st.header("💨 Tableau Récapitulatif des Sprints")
        if sprints_df.empty and not sprint_error:
            st.warning("Aucun sprint détecté avec ces paramètres.")
        elif not sprints_df.empty:
            st.dataframe(sprints_df, use_container_width=True)
        # --- FIN TABLEAU SPRINTS ---

        # --- NOUVEAU : AFFICHAGE GRAPHIQUES SPRINTS ---
        st.header("⚡ Profils Détaillés des Sprints")
        if not sprints_df.empty:
            for index, sprint_info in sprints_df.iterrows():
                try:
                    start_time_sprint_str = sprint_info['Début']
                    start_time_obj = pd.to_datetime(start_time_sprint_str, format='%H:%M:%S').time()
                    # Utiliser df_analyzed pour la sélection
                    matching_indices = df_analyzed.index.indexer_at_time(start_time_obj)

                    if len(matching_indices) > 0:
                        start_index_iloc = matching_indices[0]
                        start_timestamp = df_analyzed.index[start_index_iloc]
                        duration_float = float(sprint_info['Durée (s)'])
                        end_timestamp = start_timestamp + pd.Timedelta(seconds=duration_float)

                        # Sélectionner le segment dans df_analyzed (qui a toutes les colonnes)
                        df_sprint_segment = df_analyzed.loc[start_timestamp:end_timestamp]

                        if not df_sprint_segment.empty:
                             # Appeler la fonction de création de graphique pour le sprint
                             fig_sprint = create_sprint_figure(df_sprint_segment, sprint_info, index)
                             st.plotly_chart(fig_sprint, use_container_width=True)
                        else:
                             st.warning(f"Impossible d'extraire les données pour le sprint {index+1} (segment vide).")
                    else:
                        st.warning(f"Impossible de trouver l'heure de début ({start_time_sprint_str}) pour le sprint {index+1}.")

                except Exception as e:
                    st.error(f"Erreur création graphique sprint {index+1}.")
                    st.exception(e)
        elif not sprint_error:
            st.info("Aucun profil de sprint à afficher.")
        # --- FIN GRAPHIQUES SPRINTS ---

    else:
        st.info("Veuillez charger un fichier .fit pour commencer l'analyse.")

# Point d'entrée
if __name__ == "__main__":
    main_app()
