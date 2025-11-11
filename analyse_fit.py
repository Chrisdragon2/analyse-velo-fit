import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go 
import plotly.colors              
import io 
import pydeck as pdk # Importe pydeck
import streamlit.components.v1 as components
import json # Importé pour la sérialisation (bonne pratique)

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
    from map_plotter import create_map_figure 
    from profile_plotter import create_full_ride_profile
    from map_3d_engine import create_pydeck_chart # Importe depuis ton moteur 3D
    from pydeck_html_wrapper import generate_deck_html # <-- NOUVEL IMPORT
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
        # ... (Tout ton code de sidebar reste inchangé) ...
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
        # ... (Tout ton code de traitement de données reste inchangé) ...
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
            sprint_results = detect_sprints(df_analyzed, min_peak_speed_sprint, min_gradient_sprint, max_gradient_sprint, min_sprint_duration, max_gap_distance_sprint, sprint_rewind_sec)
            sprints_df_full = pd.DataFrame(sprint_results)
        except Exception as e: sprint_error = f"Erreur détection sprints : {e}"
    
    alt_col_to_use = 'altitude'
    if df_analyzed is not None and 'altitude_lisse' in df_analyzed.columns and not df_analyzed['altitude_lisse'].isnull().all():
            alt_col_to_use = 'altitude_lisse'

    # --- STRUCTURE PAR ONGLETS (avec Carte 3D) ---
    tab_summary, tab_profile, tab_climbs, tab_sprints, tab_3d_map = st.tabs(["Résumé", "Profil 2D", "Montées", "Sprints", "Carte 3D"])

    # --- Onglet 1: Résumé ---
    with tab_summary:
        # ... (Tout ton code pour l'onglet Résumé reste inchangé) ...
        st.header("Résumé de la Sortie")
        # ...
        
    # --- Onglet 2: Profil 2D Complet ---
    with tab_profile:
        # ... (Tout ton code pour l'onglet Profil 2D reste inchangé) ...
        st.header("Profil Complet de la Sortie")
        # ...

    # --- Onglet 3: Montées ---
    with tab_climbs:
        # ... (Tout ton code pour l'onglet Montées reste inchangé) ...
        st.header("Tableau de Bord des Montées")
        # ...

    # --- Onglet 4: Sprints ---
    with tab_sprints:
        # ... (Tout ton code pour l'onglet Sprints reste inchangé) ...
        st.header("Tableau Récapitulatif des Sprints")
        # ...

    # --- Onglet 5: Carte 3D (Pydeck) ---
    with tab_3d_map:
        st.header("Carte 3D (Vue Satellite)")
        
        # Vérifier si le token Mapbox est configuré
        if "MAPBOX_API_KEY" not in st.secrets:
            st.error("Clé API Mapbox non configurée. Ajoute 'MAPBOX_API_KEY = \"ta_clé\"' dans les Secrets de ton application Streamlit.")
        
        elif 'df_analyzed' in locals() and 'position_lat' in df_analyzed.columns:
            
            # Cases à cocher pour les highlights
            col1, col2 = st.columns(2)
            with col1:
                show_climbs = st.checkbox("Afficher les Montées (Rose)", value=True, key="3d_climbs")
            with col2:
                show_sprints = st.checkbox("Afficher les Sprints (Cyan)", value=True, key="3d_sprints")
            st.info("Utilisez Maj + Glisser (ou deux doigts sur mobile) pour incliner/pivoter la vue 3D.")
            
            # Préparation des données pour les highlights
            climb_segments_to_plot = []
            if show_climbs and montees_grouped is not None:
                processed_results_count = 0
                montee_ids = list(montees_grouped.groups.keys())
                for nom_bloc in montee_ids:
                     segment = montees_grouped.get_group(nom_bloc) 
                     if 'delta_distance' not in df_analyzed.columns: st.error("Colonne 'delta_distance' manquante."); break
                     distance_segment = df_analyzed.loc[segment.index, 'delta_distance'].sum()
                     if distance_segment >= min_climb_distance:
                         if processed_results_count < len(resultats_montées):
                            climb_segments_to_plot.append(segment)
                            processed_results_count += 1
                         else: break

            sprint_segments_to_plot = []
            if show_sprints and not sprints_df_full.empty:
                for index, sprint_info in sprints_df_full.iterrows():
                    try:
                        start_time = sprint_info['Début']
                        duration = float(sprint_info['Durée (s)'])
                        end_time = start_time + pd.Timedelta(seconds=duration)
                        segment_data = df_analyzed.loc[start_time:end_time]
                        sprint_segments_to_plot.append(segment_data)
                    except Exception:
                        pass
            
            # --- BLOC DE RENDU 3D MIS À JOUR (selon Sec 4.2) ---
            try:
                # 1. Récupérer la clé API (pour la passer au template HTML)
                MAPBOX_API_KEY = st.secrets["MAPBOX_API_KEY"]
                
                # 2. Créer l'objet Pydeck (comme avant)
                pydeck_deck_object = create_pydeck_chart(df_analyzed, climb_segments_to_plot, sprint_segments_to_plot)
                
                if pydeck_deck_object:
                    
                    # 3. Générer le HTML final à l'aide du wrapper
                    final_html = generate_deck_html(pydeck_deck_object, MAPBOX_API_KEY)
                    
                    # 4. Rendre le HTML dans le composant Streamlit
                    components.html(final_html, height=600, scrolling=False)
                    
                else:
                    st.warning("Impossible de générer la carte 3D.")
            
            except Exception as e:
                st.error(f"Erreur Pydeck : {e}")
                
        else:
            st.warning("Données GPS (position_lat/long) non trouvées.")

# Point d'entrée
if __name__ == "__main__":
    main_app()
