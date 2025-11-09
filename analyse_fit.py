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
    from map_plotter import create_map_figure # Importer la fonction de carte
except ImportError as e:
    st.error(f"Erreur d'importation: Assurez-vous que tous les fichiers .py sont présents. Détail: {e}")
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
    st.set_page_config(layout="wide", page_title="Analyseur FIT")
    st.title("Analyseur de Sortie FIT")
    
    if 'sprint_display_mode' not in st.session_state:
        st.session_state.sprint_display_mode = "courbes"

    def toggle_sprint_display_mode():
        if st.session_state.sprint_display_mode == "courbes":
            st.session_state.sprint_display_mode = "barres"
        else:
            st.session_state.sprint_display_mode = "courbes"

    # --- INPUT UTILISATEUR (Sidebar) ---
    with st.sidebar:
        st.header("1. Fichier")
        uploaded_file = st.file_uploader("Choisissez un fichier .fit", type="fit")
        with st.expander("2. Physique", expanded=True):
            cyclist_weight_kg = st.number_input("Poids du Cycliste (kg)", 30.0, 150.0, 68.0, 0.5)
            bike_weight_kg = st.number_input("Poids du Vélo + Équipement (kg)", 3.0, 25.0, 9.0, 0.1)
            total_weight_kg = cyclist_weight_kg + bike_weight_kg
            st.markdown(f"_(Poids total calculé : {total_weight_kg:.1f} kg)_")
            tire_width_mm = st.number_input("Largeur des Pneus (mm)", min_value=20, max_value=60, value=28, step=1)
            crr_value = estimate_crr_from_width(tire_width_mm)
            st.markdown(f"_(Crr estimé : {crr_value:.4f})_")
            wheel_size_options = ["700c (Route/Gravel)", "650b (Gravel/VTT)", "26\" (VTT ancien)", "29\" (VTT moderne)"]
            selected_wheel_size = st.selectbox("Taille des Roues", options=wheel_size_options)
            cda_value = 0.38; st.markdown(f"**Position :** Cocottes (CdA estimé : {cda_value} m²)")
        with st.expander("3. Montées", expanded=False):
            min_climb_distance = st.slider("Longueur min. (m)", 100, 1000, 400, 50, key="climb_dist")
            min_pente = st.slider("Pente min. (%)", 1.0, 5.0, 3.0, 0.5, key="climb_pente")
            max_gap_climb = st.slider("Fusion gap (m)", 50, 500, 200, 50, key="climb_gap")
            chunk_distance_m = st.select_slider("Fenêtre Analyse Pente (m)", options=[100, 200, 500, 1000, 1500, 2000], value=100, key="chunk_distance")
        with st.expander("4. Sprints", expanded=False):
            min_peak_speed_sprint = st.slider("Vitesse min. (km/h)", 25.0, 60.0, 40.0, 1.0, key="sprint_speed")
            min_sprint_duration = st.slider("Durée min. (s)", 3, 15, 5, 1, key="sprint_duration")
            slope_range_sprint = st.slider("Plage Pente (%)", -10.0, 10.0, (-5.0, 5.0), 0.5, key="sprint_slope_range")
            min_gradient_sprint, max_gradient_sprint = slope_range_sprint
            max_gap_distance_sprint = st.slider("Fusion gap (m)", 10, 200, 50, 10, key="sprint_gap_dist")
            sprint_rewind_sec = st.slider("Secondes 'Montée en Puissance'", 0, 20, 10, 1, key="sprint_rewind")

    # --- AFFICHAGE PRINCIPAL ---
    if uploaded_file is None:
        st.info("Veuillez charger un fichier .fit pour commencer l'analyse.")
        st.stop()

    # --- TRAITEMENT DES DONNÉES ---
    with st.spinner("Analyse du fichier en cours..."):
        df_analyzed = None; resultats_df = pd.DataFrame(); sprints_df_full = pd.DataFrame()
        analysis_error = None; sprint_error = None; montees_grouped = None; resultats_montées = []
        
        try:
            df, session_data, error_msg = load_and_clean_data(uploaded_file)
            if df is None: st.error(f"Erreur chargement : {error_msg}"); st.stop()
            
            df_power_est = estimate_power(df, total_weight_kg, crr_value, cda_value)
            df = df.join(df_power_est)
            df_analyzed = calculate_derivatives(df.copy())
            
            try:
                df_analyzed_climbs = identify_and_filter_initial_climbs(df_analyzed, min_pente)
                montees_grouped, df_blocs, bloc_map = group_and_merge_climbs(df_analyzed_climbs, max_gap_climb)
                resultats_montées = calculate_climb_summary(montees_grouped, min_climb_distance)
                resultats_df = pd.DataFrame(resultats_montées)
            except Exception as e:
                analysis_error = f"Erreur analyse montées : {e}"

            try:
                sprint_results = detect_sprints(
                    df_analyzed, min_peak_speed_sprint, min_gradient_sprint,
                    max_gradient_sprint, min_sprint_duration, max_gap_distance_sprint,
                    sprint_rewind_sec
                )
                sprints_df_full = pd.DataFrame(sprint_results)
            except Exception as e:
                sprint_error = f"Erreur détection sprints : {e}"
        
        except Exception as e:
            st.error(f"Une erreur critique est survenue lors du traitement : {e}")
            st.stop()

    alt_col_to_use = 'altitude'
    if df_analyzed is not None and 'altitude_lisse' in df_analyzed.columns and not df_analyzed['altitude_lisse'].isnull().all():
            alt_col_to_use = 'altitude_lisse'

    # --- STRUCTURE PAR ONGLETS (avec icônes) ---
    tab_summary, tab_climbs, tab_sprints = st.tabs(["📊", "⛰️", "💨"])

    # --- Onglet 1: Résumé ---
    with tab_summary:
        st.header("Résumé de la Sortie")
        
        if 'session_data' not in locals(): session_data = {}
            
        try:
            st.subheader("Statistiques Clés")
            dist_totale_km = session_data.get('total_distance', df['distance'].iloc[-1]) / 1000
            d_plus = session_data.get('total_ascent', df['altitude'].diff().clip(lower=0).sum())
            temps_deplacement_sec = session_data.get('total_moving_time', len(df[df['speed'] > 1.0]))
            temps_deplacement_str = str(pd.to_timedelta(temps_deplacement_sec, unit='s')).split(' ')[-1].split('.')[0]
            v_moy_session = session_data.get('avg_speed', 0) 
            vitesse_moy_kmh = (v_moy_session * 3.6) if v_moy_session > 0 else ((dist_totale_km * 1000 / temps_deplacement_sec) * 3.6 if temps_deplacement_sec > 0 else 0)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Distance Totale", f"{dist_totale_km:.2f} km")
            col2.metric("Dénivelé Positif", f"{d_plus:.0f} m")
            col3.metric("Temps de Déplacement", temps_deplacement_str)
            col4.metric("Vitesse Moyenne", f"{vitesse_moy_kmh:.2f} km/h")
            
            # --- MODIFIÉ : Ajout du sélecteur de style de carte ---
            st.subheader("Carte du Parcours")
            
            map_style_options = {
                "Épuré (Clair)": "carto-positron",
                "Rues": "open-street-map",
                "Terrain / Satellite": "stamen-terrain" # "Satellite" gratuit
            }
            selected_style_name = st.radio(
                "Style de la carte :", 
                options=list(map_style_options.keys()), 
                horizontal=True, 
                key="map_style"
            )
            map_style_id = map_style_options[selected_style_name]
            # --- FIN MODIFICATION ---
            
            if 'df_analyzed' in locals() and 'position_lat' in df_analyzed.columns:
                # On passe le style choisi à la fonction
                map_fig = create_map_figure(df_analyzed, map_style_id) 
                st.plotly_chart(map_fig, use_container_width=True)
            else:
                st.warning("Données GPS (position_lat/position_long) non trouvées. Impossible d'afficher la carte.")
            
            st.subheader("Statistiques Secondaires")
            v_max_kmh = session_data.get('max_speed', df['speed'].max()) * 3.6
            avg_hr = session_data.get('avg_heart_rate')
            max_hr = session_data.get('max_heart_rate')
            avg_cad = session_data.get('avg_cadence')
            max_cad = session_data.get('max_cadence')
            if 'cadence' in df.columns and not avg_cad and not df[df['cadence'] > 0].empty:
                avg_cad = df[df['cadence'] > 0]['cadence'].mean()
            if 'cadence' in df.columns and not max_cad:
                max_cad = df['cadence'].max()
            col1b, col2b, col3b = st.columns(3)
            col1b.metric("Vitesse Max", f"{v_max_kmh:.2f} km/h")
            col2b.metric("FC Moyenne", f"{avg_hr:.0f} bpm" if avg_hr else "N/A")
            col3b.metric("Cadence Moyenne", f"{avg_cad:.0f} rpm" if avg_cad and avg_cad > 0 else "N/A")
            col1c, col2c, col3c = st.columns(3)
            col1c.empty() 
            col2c.metric("FC Max", f"{max_hr:.0f} bpm" if max_hr else "N/A")
            col3c.metric("Cadence Max", f"{max_cad:.0f} rpm" if max_cad else "N/A")

            st.subheader("Analyse de Puissance (Estimée)")
            if 'estimated_power' in df.columns and not df['estimated_power'].isnull().all():
                power_avg_est = df['estimated_power'].mean()
                power_max_est = df['estimated_power'].max()
                col1d, col2d = st.columns(2)
                col1d.metric("Puissance Estimée Moyenne", f"{power_avg_est:.0f} W")
                col2d.metric("Puissance Estimée Max", f"{power_max_est:.0f} W")
            else:
                st.info("Aucune donnée de puissance estimée à afficher.")

        except Exception as e:
            st.warning(f"Impossible d'afficher le résumé : {e}")

    # --- Onglet 2: Montées ---
    with tab_climbs:
        st.header("Tableau de Bord des Montées")
        if analysis_error: st.error(analysis_error)
        elif resultats_df.empty:
            st.warning(f"Aucune ascension ({min_climb_distance}m+, {min_pente}%+) trouvée.")
        else:
            st.dataframe(resultats_df.drop(columns=['index'], errors='ignore'), use_container_width=True)

        st.header("Profils Détaillés des Montées")
        if montees_grouped is not None and not resultats_df.empty:
            processed_results_count = 0
            montee_ids = list(montees_grouped.groups.keys())
            valid_climb_data = []
            for nom_bloc in montee_ids:
                 segment = montees_grouped.get_group(nom_bloc)
                 if 'delta_distance' not in df_analyzed.columns: st.error("Colonne 'delta_distance' manquante."); break
                 distance_segment = df_analyzed.loc[segment.index, 'delta_distance'].sum()
                 if distance_segment >= min_climb_distance:
                     if processed_results_count < len(resultats_montées):
                        valid_climb_data.append((processed_results_count, segment))
                        processed_results_count += 1
                     else: st.warning(f"Incohérence détectée (montées)."); break
            
            for index_resultat, df_climb_original in valid_climb_data:
                try:
                    fig = create_climb_figure(df_climb_original.copy(), alt_col_to_use, chunk_distance_m, resultats_montées, index_resultat)
                    st.plotly_chart(fig, use_container_width=True, key=f"climb_chart_{index_resultat}")
                except Exception as e:
                    st.error(f"Erreur création graphique ascension {index_resultat+1}."); st.exception(e)
        elif not analysis_error:
                st.info("Aucun profil de montée à afficher.")

    # --- Onglet 3: Sprints ---
    with tab_sprints:
        st.header("Tableau Récapitulatif des Sprints")
        if sprint_error: st.error(sprint_error)
        elif sprints_df_full.empty:
            st.warning("Aucun sprint détecté avec ces paramètres.")
        else:
            cols_to_show = ['Début (km)', 'Fin (km)', 'Distance (m)', 'Durée (s)', 'Vitesse Max (km/h)', 'Vitesse Moy (km/h)', 'Pente Moy (%)', 'Puissance Max Est. (W)', 'Accel Max (m/s²)']
            cols_existantes = [col for col in cols_to_show if col in sprints_df_full.columns]
            st.dataframe(sprints_df_full[cols_existantes], use_container_width=True)

        st.header("Profils Détaillés des Sprints")
        
        current_mode_label = { "courbes": "Vue actuelle : Courbes", "barres": "Vue actuelle : Barres + Courbe" }
        st.caption(current_mode_label[st.session_state.sprint_display_mode])
        st.button("Inverser Barres / Courbe", on_click=toggle_sprint_display_mode, key="toggle_sprint_view")
        
        if not sprints_df_full.empty:
            for index, sprint_info in sprints_df_full.iterrows():
                try:
                    start_timestamp = sprint_info['Début']
                    if not isinstance(start_timestamp, pd.Timestamp): st.warning(f"Format début incorrect sprint {index+1}."); continue
                    try: duration_float = float(sprint_info['Durée (s)'])
                    except (ValueError, TypeError): st.warning(f"Format durée incorrect sprint {index+1}."); continue
                    
                    end_timestamp = start_timestamp + pd.Timedelta(seconds=duration_float)
                    
                    if start_timestamp in df_analyzed.index and end_timestamp <= df_analyzed.index[-1]:
                         df_sprint_segment = df_analyzed.loc[start_timestamp:end_timestamp]
                    elif start_timestamp in df_analyzed.index:
                         df_sprint_segment = df_analyzed.loc[start_timestamp:]
                    else: df_sprint_segment = pd.DataFrame()

                    if not df_sprint_segment.empty:
                         fig_sprint = create_sprint_figure(df_sprint_segment.copy(), sprint_info, index, st.session_state.sprint_display_mode)
                         st.plotly_chart(fig_sprint, use_container_width=True, key=f"sprint_chart_{index}")
                    else:
                         st.warning(f"Segment vide pour sprint {index+1}.")
                except KeyError as ke:
                     st.error(f"Erreur (KeyError) sprint {index+1}: Clé {ke}.")
                     st.exception(ke)
                except Exception as e:
                    st.error(f"Erreur création graphique sprint {index+1}.")
                    st.exception(e)
        elif not sprint_error:
            st.info("Aucun profil de sprint à afficher.")

# Point d'entrée
if __name__ == "__main__":
    main_app()
