import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go 
import plotly.colors            
import io 
import pydeck as pdk 
import streamlit.components.v1 as components 
import time

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
    # --- CORRECTION ICI : Ajout de create_map_figure ---
    from plotting import create_climb_figure, create_sprint_figure, create_map_figure
    from profile_plotter import create_full_ride_profile
    from map_3d_engine import create_pydeck_chart 
    
    # Importation du composant d'animation
    from anim_slider.anim_slider import anim_slider 
except ImportError as e:
    st.error(f"Erreur d'importation: Assurez-vous que tous les fichiers .py nécessaires sont présents. Détail: {e}")
    st.stop()

# --- Fonction simplifiée pour estimer Crr ---
def estimate_crr_from_width(width_mm):
    base_crr = 0.004
    additional_crr_per_mm = 0.0001
    if width_mm > 25: return base_crr + (width_mm - 25) * additional_crr_per_mm
    else: return base_crr

# --- CORPS PRINCIPAL DE L'APPLICATION STREAMLIT ---
def main_app():
    st.set_page_config(layout="wide", page_title="Analyseur FIT")
    st.title("Analyseur de Sortie FIT")
    
    if 'sprint_display_mode' not in st.session_state:
        st.session_state.sprint_display_mode = "courbes"

    def toggle_sprint_display_mode():
        if st.session_state.sprint_display_mode == "courbes": st.session_state.sprint_display_mode = "barres"
        else: st.session_state.sprint_display_mode = "courbes"

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
        except Exception as e: analysis_error = f"Erreur analyse montées : {e}"; resultats_df = pd.DataFrame()
        try:
            # Note: Si vous n'avez pas de fichier sprint_processing.py, commentez les 3 lignes suivantes
            from sprint_processing import detect_sprints 
            sprint_results = detect_sprints(df_analyzed, min_peak_speed_sprint, min_gradient_sprint, max_gradient_sprint, min_sprint_duration, max_gap_distance_sprint, sprint_rewind_sec)
            sprints_df_full = pd.DataFrame(sprint_results)
        except ImportError: pass 
        except Exception as e: sprint_error = f"Erreur détection sprints : {e}"
    
    alt_col_to_use = 'altitude'
    if df_analyzed is not None and 'altitude_lisse' in df_analyzed.columns and not df_analyzed['altitude_lisse'].isnull().all():
            alt_col_to_use = 'altitude_lisse'

    # --- STRUCTURE PAR ONGLETS ---
    tab_summary, tab_profile, tab_climbs, tab_sprints, tab_3d_map = st.tabs(["Résumé", "Profil 2D", "Montées", "Sprints", "Carte 3D"])
    
    with tab_summary:
        st.header("Résumé de la Sortie")
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
            
            st.subheader("Carte du Parcours 2D")
            map_style_options = {"Épuré": "carto-positron", "Rues": "open-street-map", "Sombre": "carto-darkmatter"}
            selected_style_name = st.radio("Style de la carte :", options=list(map_style_options.keys()), horizontal=True, key="map_style")
            map_style_id = map_style_options[selected_style_name]
            if 'df_analyzed' in locals() and 'position_lat' in df_analyzed.columns:
                # create_map_figure est maintenant bien importé
                map_fig = create_map_figure(df_analyzed, map_style_id) 
                st.plotly_chart(map_fig, use_container_width=True)
            
            # Stats secondaires...
            st.subheader("Statistiques Secondaires")
            # ... (code stats secondaires standard) ...
            
        except Exception as e:
            st.warning(f"Impossible d'afficher le résumé complet : {e}")
            
    with tab_profile:
        st.header("Profil Complet de la Sortie")
        if 'df_analyzed' in locals() and not df_analyzed.empty:
            try:
                fig_profile = create_full_ride_profile(df_analyzed)
                st.plotly_chart(fig_profile, use_container_width=True)
            except Exception as e: st.error(f"Erreur profil : {e}")
            
    with tab_climbs:
        st.header("Tableau de Bord des Montées")
        if analysis_error: st.error(analysis_error)
        elif resultats_df.empty: st.warning(f"Aucune ascension trouvée.")
        else: st.dataframe(resultats_df.drop(columns=['index'], errors='ignore'), use_container_width=True)
        st.header("Profils Détaillés des Montées")
        if montees_grouped is not None and not resultats_df.empty:
            processed_results_count = 0; montee_ids = list(montees_grouped.groups.keys()); valid_climb_data = []
            for nom_bloc in montee_ids:
                segment = montees_grouped.get_group(nom_bloc)
                distance_segment = df_analyzed.loc[segment.index, 'delta_distance'].sum()
                if distance_segment >= min_climb_distance:
                    if processed_results_count < len(resultats_montées):
                        valid_climb_data.append((processed_results_count, segment)); processed_results_count += 1
            for index_resultat, df_climb_original in valid_climb_data:
                try:
                    fig = create_climb_figure(df_climb_original.copy(), alt_col_to_use, chunk_distance_m, resultats_montées, index_resultat)
                    st.plotly_chart(fig, use_container_width=True, key=f"climb_chart_{index_resultat}")
                except Exception: pass

    with tab_sprints:
        st.header("Tableau Récapitulatif des Sprints")
        if not sprints_df_full.empty:
            st.dataframe(sprints_df_full, use_container_width=True)
            for index, sprint_info in sprints_df_full.iterrows():
                try:
                    end = sprint_info['Début'] + pd.Timedelta(seconds=float(sprint_info['Durée (s)']))
                    df_seg = df_analyzed.loc[sprint_info['Début']:end] if sprint_info['Début'] in df_analyzed.index else pd.DataFrame()
                    if not df_seg.empty:
                        fig_sprint = create_sprint_figure(df_seg.copy(), sprint_info, index, st.session_state.sprint_display_mode)
                        st.plotly_chart(fig_sprint, use_container_width=True, key=f"sprint_chart_{index}")
                except: pass
        else: st.info("Aucun sprint.")


    # --- Onglet 5: Carte 3D (Pydeck) ---
    with tab_3d_map:
        st.header("Carte 3D (Vue Satellite)")

        if "MAPBOX_API_KEY" not in st.secrets:
            st.error("Clé API Mapbox non configurée.")

        elif 'df_analyzed' in locals() and 'position_lat' in df_analyzed.columns:
            
            # --- LE FRAGMENT EST ICI ---
            @st.fragment 
            def afficher_carte_interactive():
                # 1. Préparation
                if 'distance' not in df_analyzed.columns:
                    st.error("Colonne 'distance' manquante.")
                    return
                max_distance = int(df_analyzed['distance'].max())

                # 2. Le Slider (Input)
                # Si anim_slider est importé correctement, le bouton apparaîtra
                selected_distance = anim_slider(
                    max_dist=max_distance,
                    key="animation_player"
                )
                
                # 3. Calculs
                closest_index = (df_analyzed['distance'] - selected_distance).abs().idxmin()
                selected_point_data = df_analyzed.loc[closest_index]

                col1, col2 = st.columns(2)
                with col1:
                    show_climbs = st.checkbox("Afficher les Montées (Rose)", value=True, key="3d_climbs")
                with col2:
                    show_sprints = st.checkbox("Afficher les Sprints (Cyan)", value=True, key="3d_sprints")
                
                st.info(f"Position : {selected_distance:.0f} m")

                # 4. Affichage Carte
                climb_segments_to_plot = []
                if show_climbs and montees_grouped is not None:
                      processed_results_count = 0
                      for nom_bloc in list(montees_grouped.groups.keys()):
                        segment = montees_grouped.get_group(nom_bloc)
                        dist_seg = df_analyzed.loc[segment.index, 'delta_distance'].sum()
                        if dist_seg >= min_climb_distance:
                            if processed_results_count < len(resultats_montées):
                                climb_segments_to_plot.append(segment)
                                processed_results_count += 1
                
                sprint_segments_to_plot = []
                if show_sprints and not sprints_df_full.empty:
                    for _, s_info in sprints_df_full.iterrows():
                        try:
                            end = s_info['Début'] + pd.Timedelta(seconds=float(s_info['Durée (s)']))
                            sprint_segments_to_plot.append(df_analyzed.loc[s_info['Début']:end])
                        except: pass

                # --- Création et affichage Pydeck (METHODE FLUIDE) ---
                try:
                    deck = create_pydeck_chart(
                        df_analyzed, 
                        climb_segments_to_plot, 
                        sprint_segments_to_plot, 
                        selected_point_data=selected_point_data
                    )
                    
                    if deck:
                        # Utilisation de st.pydeck_chart pour éviter le rechargement
                        st.pydeck_chart(deck, use_container_width=True)
                        
                except Exception as e:
                    st.error(f"Erreur Pydeck : {e}")

                # 5. Profil 2D sous la carte
                try:
                    fig_2d = create_full_ride_profile(df_analyzed, selected_distance=selected_distance)
                    st.plotly_chart(fig_2d, use_container_width=True, key="profile_3d_view")
                except: pass

            # --- APPEL DE LA FONCTION ISOLEE ---
            afficher_carte_interactive()
            
        else:
            st.warning("Données GPS non trouvées.")

# Point d'entrée
if __name__ == "__main__":
    main_app()
