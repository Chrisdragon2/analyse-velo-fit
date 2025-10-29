import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.colors
import io

# --- Importations depuis les modules ---
try:
    from data_loader import load_and_clean_data
    from power_estimator import estimate_power
    from climb_processing import (
        calculate_derivatives,
        identify_and_filter_initial_climbs,
        group_and_merge_climbs,
        calculate_climb_summary
    )
    from plotting import create_climb_figure, create_sprint_figure
    from sprint_detector import detect_sprints
except ImportError as e:
    st.error(f"Erreur d'importation: Assurez-vous que tous les fichiers .py nécessaires sont présents. Détail: {e}")
    st.stop()

# --- Fonction simplifiée pour estimer Crr ---
def estimate_crr_from_width(width_mm):
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

        cda_value = 0.38
        st.markdown(f"**Position :** Cocottes (CdA estimé : {cda_value} m²)")

        st.header("3. Paramètres de Détection des Montées")
        min_climb_distance = st.slider("Longueur min. montée (m)", 100, 1000, 400, 50, key="climb_dist")
        min_pente = st.slider("Pente min. (%)", 1.0, 5.0, 3.0, 0.5, key="climb_pente")
        max_gap_climb = st.slider("Fusion max. gap (m)", 50, 500, 200, 50, key="climb_gap")
        
        # --- MODIFIÉ : Ajout du curseur pour la fenêtre d'analyse ---
        chunk_distance_m = st.select_slider(
            "Fenêtre d'Analyse Pente (m)",
            options=[100, 200, 500, 1000, 1500, 2000], # Options de fenêtre
            value=100, # Défaut à 100m
            key="chunk_distance"
        )
        # --- FIN MODIFICATION ---

        st.header("4. Paramètres de Détection des Sprints")
        min_peak_speed_sprint = st.slider("Vitesse de pointe minimale (km/h)", 25.0, 60.0, 40.0, 1.0, key="sprint_speed")
        min_sprint_duration = st.slider("Durée minimale du sprint (s)", 3, 15, 5, 1, key="sprint_duration")
        slope_range_sprint = st.slider(
            "Plage de pente moyenne autorisée (%)",
            min_value=-10.0, max_value=10.0, value=(-5.0, 5.0),
            step=0.5, key="sprint_slope_range"
        )
        min_gradient_sprint = slope_range_sprint[0]
        max_gradient_sprint = slope_range_sprint[1]
        max_gap_distance_sprint = st.slider(
            "Distance max. entre sprints à fusionner (m)",
            min_value=10, max_value=200, value=50, step=10, key="sprint_gap_dist"
        )

    # --- TRAITEMENT DES DONNÉES ---
    if uploaded_file is not None:
        df, error_msg = load_and_clean_data(uploaded_file)
        if df is None: st.error(f"Erreur chargement : {error_msg}"); return

        df_power_est = estimate_power(df, total_weight_kg, crr_value, cda_value)
        df = df.join(df_power_est)

        analysis_error = None
        montees_grouped = None; resultats_montées = []; df_analyzed = df
        try:
            df_analyzed = calculate_derivatives(df.copy())
            df_analyzed = identify_and_filter_initial_climbs(df_analyzed, min_pente)
            montees_grouped, df_blocs, bloc_map = group_and_merge_climbs(df_analyzed, max_gap_climb)
            resultats_montées = calculate_climb_summary(montees_grouped, min_climb_distance)
            resultats_df = pd.DataFrame(resultats_montées)
        except Exception as e:
            analysis_error = f"Erreur pendant l'analyse des montées : {e}"
            st.error(analysis_error); resultats_df = pd.DataFrame()

        sprint_error = None
        sprints_df_full = pd.DataFrame()
        try:
            if 'df_analyzed' in locals():
                sprint_results = detect_sprints(
                    df_analyzed, min_peak_speed_sprint, min_gradient_sprint,
                    max_gradient_sprint, min_sprint_duration, max_gap_distance_sprint
                )
                sprints_df_full = pd.DataFrame(sprint_results)
            else: raise ValueError("df_analyzed n'a pas été défini.")
        except Exception as e:
            sprint_error = f"Erreur pendant la détection des sprints : {e}"
            st.error(sprint_error)

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
                 if 'delta_distance' not in df_analyzed.columns:
                     st.error("Colonne 'delta_distance' manquante."); break
                 distance_segment = df_analyzed.loc[segment.index, 'delta_distance'].sum()
                 if distance_segment >= min_climb_distance:
                     if processed_results_count < len(resultats_montées):
                        valid_climb_data.append((processed_results_count, segment))
                        processed_results_count += 1
                     else: st.warning(f"Incohérence détectée (montées)."); break
            for index_resultat, df_climb_original in valid_climb_data:
                try:
                    # --- MODIFIÉ : On passe chunk_distance_m ---
                    fig = create_climb_figure(
                        df_climb_original.copy(), 
                        alt_col_to_use, 
                        chunk_distance_m, # Utilise la variable du slider
                        resultats_montées, 
                        index_resultat
                    )
                    st.plotly_chart(fig, use_container_width=True, key=f"climb_chart_{index_resultat}")
                except Exception as e:
                    st.error(f"Erreur création graphique ascension {index_resultat+1}.")
                    st.exception(e)
        elif not analysis_error:
             st.info("Aucun profil de montée à afficher.")

        # --- AFFICHAGE TABLEAU SPRINTS ---
        st.header("💨 Tableau Récapitulatif des Sprints")
        if sprints_df_full.empty and not sprint_error:
            st.warning("Aucun sprint détecté avec ces paramètres.")
        elif not sprints_df_full.empty:
            cols_to_show = ['Début (km)', 'Fin (km)', 'Distance (m)', 'Durée (s)', 'Vitesse Max (km/h)', 'Vitesse Moy (km/h)',
                            'Pente Moy (%)', 'Puissance Max Est. (W)', 'Accel Max (m/s²)']
            cols_existantes = [col for col in cols_to_show if col in sprints_df_full.columns]
            st.dataframe(sprints_df_full[cols_existantes], use_container_width=True)

        # --- AFFICHAGE GRAPHIQUES SPRINTS ---
        st.header("⚡ Profils Détaillés des Sprints")
        if not sprints_df_full.empty:
            for index, sprint_info in sprints_df_full.iterrows():
                try:
                    start_timestamp = sprint_info['Début']
                    if not isinstance(start_timestamp, pd.Timestamp):
                        st.warning(f"Format début incorrect sprint {index+1}. Skipping."); continue
                    try: duration_float = float(sprint_info['Durée (s)'])
                    except (ValueError, TypeError): st.warning(f"Format durée incorrect sprint {index+1}. Skipping."); continue
                    
                    end_timestamp = start_timestamp + pd.Timedelta(seconds=duration_float)
                    
                    if start_timestamp in df_analyzed.index and end_timestamp <= df_analyzed.index[-1]:
                         df_sprint_segment = df_analyzed.loc[start_timestamp:end_timestamp]
                    elif start_timestamp in df_analyzed.index:
                         df_sprint_segment = df_analyzed.loc[start_timestamp:]
                    else: df_sprint_segment = pd.DataFrame()

                    if not df_sprint_segment.empty:
                         fig_sprint = create_sprint_figure(df_sprint_segment.copy(), sprint_info, index)
                         st.plotly_chart(fig_sprint, use_container_width=True, key=f"sprint_chart_{index}")
                    else:
                         st.warning(f"Segment vide pour sprint {index+1}.")
                except KeyError as ke:
                     st.error(f"Erreur (KeyError) sprint {index+1}: Clé {ke}."); st.exception(ke)
                except Exception as e:
                    st.error(f"Erreur création graphique sprint {index+1}."); st.exception(e)
        elif not sprint_error:
            st.info("Aucun profil de sprint à afficher.")
    else:
        st.info("Veuillez charger un fichier .fit pour commencer l'analyse.")

# Point d'entrée
if __name__ == "__main__":
    main_app()
