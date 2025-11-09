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
    from map_plotter import create_map_figure
    from map_3d_plotter import create_3d_map_figure # <-- NOUVEL IMPORT
except ImportError as e:
    st.error(f"Erreur d'importation: Assurez-vous que tous les fichiers .py nécessaires sont présents. Détail: {e}")
    st.stop()

# --- NOUVELLE FONCTION : Style CSS (Minimaliste) ---
# (On garde le CSS minimaliste pour l'instant)
def load_custom_css():
    st.markdown("""<style> footer {visibility: hidden;} </style>""", unsafe_allow_html=True)

# --- Fonction simplifiée pour estimer Crr ---
def estimate_crr_from_width(width_mm):
    base_crr = 0.004
    additional_crr_per_mm = 0.0001
    if width_mm > 25: return base_crr + (width_mm - 25) * additional_crr_per_mm
    else: return base_crr

# --- CORPS PRINCIPAL DE L'APPLICATION STREAMLIT ---
def main_app():
    st.set_page_config(layout="wide", page_title="Analyseur FIT")
    # load_custom_css() # On peut le désactiver si on préfère le look 100% natif
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
            total_weight_kg = cyclist_weight_kg + bike_weight_kg; st.caption(f"Poids total : {total_weight_kg:.1f} kg")
            tire_width_mm = st.number_input("Largeur des Pneus (mm)", 20, 60, 28, 1)
            crr_value = estimate_crr_from_width(tire_width_mm); st.caption(f"Crr estimé : {crr_value:.4f}")
            wheel_size_options = ["700c", "650b", "26\"", "29\""]; st.selectbox("Taille des Roues", options=wheel_size_options)
            cda_value = 0.38; st.markdown(f"**Position :** Cocottes (CdA estimé : {cda_value} m²)")
        with st.expander("3. Montées", expanded=False):
            min_climb_distance = st.slider("Longueur min. (m)", 100, 1000, 400, 50, key="climb_dist")
            min_pente = st.slider("Pente min. (%)", 1.0, 5.0, 3.0, 0.5, key="climb_pente")
            max_gap_climb = st.slider("Fusion gap (m)", 50, 500, 200, 50, key="climb_gap")
            chunk_distance_m = st.select_slider("Fenêtre Pente (m)", options=[100, 200, 500, 1000], value=100, key="chunk_distance")
        with st.expander("4. Sprints", expanded=False):
            min_peak_speed_sprint = st.slider("Vitesse min. (km/h)", 25.0, 60.0, 40.0, 1.0, key="sprint_speed")
            min_sprint_duration = st.slider("Durée min. (s)", 3, 15, 5, 1, key="sprint_duration")
            slope_range_sprint = st.slider("Plage Pente (%)", -10.0, 10.0, (-5.0, 5.0), 0.5, key="sprint_slope_range")
            min_gradient_sprint, max_gradient_sprint = slope_range_sprint
            max_gap_distance_sprint = st.slider("Fusion gap (m)", 10, 200, 50, 10, key="sprint_gap_dist")
            sprint_rewind_sec = st.slider("Secondes 'Montée en Puissance'", 0, 20, 10, 1, key="sprint_rewind")

    # --- AFFICHAGE PRINCIPAL ---
    if uploaded_file is None:
        st.info("Veuillez charger un fichier .fit pour commencer l'analyse."); st.stop()

    # --- TRAITEMENT DES DONNÉES ---
    with st.spinner("Analyse du fichier en cours..."):
        df_analyzed = None; resultats_df = pd.DataFrame(); sprints_df_full = pd.DataFrame()
        analysis_error = None; sprint_error = None; montees_grouped = None; resultats_montées = []
        df, session_data, error_msg = load_and_clean_data(uploaded_file)
        if df is None: st.error(f"Erreur chargement : {error_msg}"); st.stop()
        
        df_power_est = estimate_power(df, total_weight_kg, crr_value, cda_value)
        df = df.join(df_power_est)
        
        try:
            df_analyzed = calculate_derivatives(df.copy())
            df_analyzed_climbs = identify_and_filter_initial_climbs(df_analyzed, min_pente)
            montees_grouped, df_blocs, bloc_map = group_and_merge_climbs(df_analyzed_climbs, max_gap_climb)
            resultats_montées = calculate_climb_summary(montees_grouped, min_climb_distance)
            resultats_df = pd.DataFrame(resultats_montées)
        except Exception as e:
            analysis_error = f"Erreur analyse montées : {e}"
        try:
            sprint_results = detect_sprints(df_analyzed, min_peak_speed_sprint, min_gradient_sprint, max_gradient_sprint, min_sprint_duration, max_gap_distance_sprint, sprint_rewind_sec)
            sprints_df_full = pd.DataFrame(sprint_results)
        except Exception as e:
            sprint_error = f"Erreur détection sprints : {e}"
    
    alt_col_to_use = 'altitude'
    if df_analyzed is not None and 'altitude_lisse' in df_analyzed.columns and not df_analyzed['altitude_lisse'].isnull().all():
            alt_col_to_use = 'altitude_lisse'

    # --- STRUCTURE PAR ONGLETS (AVEC CARTE 3D) ---
    tab_summary, tab_climbs, tab_sprints, tab_3d_map = st.tabs(["Résumé", "Montées", "Sprints", "Carte 3D"])

    # --- Onglet 1: Résumé ---
    with tab_summary:
        st.header("Résumé de la Sortie")
        # ... (code de l'onglet résumé, avec la carte 2D) ...
        # (Copie-colle le code de l'onglet résumé de ma réponse précédente ici)
        # ... (il est long, donc je le saute pour la clarté) ...
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
            selected_style_name = st.radio("Style de la carte 2D :", options=list(map_style_options.keys()), horizontal=True, key="map_style")
            map_style_id = map_style_options[selected_style_name]
            
            if 'df_analyzed' in locals() and 'position_lat' in df_analyzed.columns:
                map_fig = create_map_figure(df_analyzed, map_style_id) 
                st.plotly_chart(map_fig, use_container_width=True)
            else:
                st.warning("Données GPS (position_lat/long) non trouvées.")
            
            st.subheader("Statistiques Secondaires")
            # ... (code des stats secondaires) ...
        except Exception as e:
            st.warning(f"Impossible d'afficher le résumé : {e}")


    # --- Onglet 2: Montées ---
    with tab_climbs:
        st.header("Tableau de Bord des Montées")
        # ... (code de l'onglet montées) ...
        if analysis_error: st.error(analysis_error)
        elif resultats_df.empty: st.warning(f"Aucune ascension ({min_climb_distance}m+, {min_pente}%+) trouvée.")
        else: st.dataframe(resultats_df.drop(columns=['index'], errors='ignore'), use_container_width=True)
        st.header("Profils Détaillés des Montées")
        if montees_grouped is not None and not resultats_df.empty:
            # ... (logique d'affichage des graphiques de montée) ...
            pass # (Garde ton code existant ici)


    # --- Onglet 3: Sprints ---
    with tab_sprints:
        st.header("Tableau Récapitulatif des Sprints")
        # ... (code de l'onglet sprints) ...
        if sprint_error: st.error(sprint_error)
        elif sprints_df_full.empty: st.warning("Aucun sprint détecté.")
        else: # ... (affichage dataframe sprints) ...
            pass # (Garde ton code existant ici)
        st.header("Profils Détaillés des Sprints")
        # ... (bouton de bascule et affichage graphiques sprints) ...
        pass # (Garde ton code existant ici)

    # --- NOUVEL ONGLET : Carte 3D (avec les 3 fonctionnalités) ---
    with tab_3d_map:
        st.header("Visualisation 3D du Parcours")
        
        if 'df_analyzed' not in locals() or 'position_lat' not in df_analyzed.columns:
            st.warning("Données GPS et d'altitude requises pour la carte 3D.")
            st.stop() # Arrêter si pas de données GPS
            
        st.info("Utilisez la souris pour pivoter, zoomer et déplacer. Les contrôles ci-dessous ajoutent des superpositions.")

        # --- Préparation des données pour les contrôles ---
        # Échantillonner pour le slider d'animation (plus léger)
        df_sampled_for_3d = df_analyzed.iloc[::10, :].copy() # 1 pt toutes les 10s
        
        # --- 1. Contrôles de l'interface ---
        col1, col2 = st.columns([1, 2]) # Colonne de contrôle plus petite
        
        with col1:
            st.subheader("Contrôles d'Affichage")
            
            # Fonctionnalité 1: Sélecteur de Couleur
            color_metric = st.selectbox(
                "Colorer la trace par :", 
                ["Puissance", "Vitesse", "Fréquence Cardiaque", "Altitude"], 
                key="3d_color",
                help="Change la couleur du tracé principal."
            )
            
            # Fonctionnalité 2: Mise en Surbrillance
            st.subheader("Superpositions")
            show_climbs = st.checkbox("Afficher les Montées (Rouge)", key="3d_climbs")
            show_sprints = st.checkbox("Afficher les Sprints (Cyan)", key="3d_sprints")

        with col2:
            st.subheader("Animation (Bêta)")
            # Fonctionnalité 3: Slider d'animation (caméra)
            animation_pos = st.slider(
                "Position sur le parcours (0 = Vue d'ensemble)", 
                0, len(df_sampled_for_3d) - 1, 0, 
                key="3d_anim_slider"
            )

        # --- 2. Préparation des données pour les highlights ---
        climb_segments_to_plot = []
        if show_climbs and montees_grouped is not None:
            for index, (nom_bloc, segment_data) in enumerate(montees_grouped):
                 # On prend que les segments valides (assez longs)
                 if index < len(resultats_montées):
                    climb_segments_to_plot.append(segment_data.iloc[::2, :]) # Échantillonner un peu

        sprint_segments_to_plot = []
        if show_sprints and not sprints_df_full.empty:
            for index, sprint_info in sprints_df_full.iterrows():
                start_time = sprint_info['Début']
                duration = float(sprint_info['Durée (s)'])
                end_time = start_time + pd.Timedelta(seconds=duration)
                segment_data = df_analyzed.loc[start_time:end_time]
                sprint_segments_to_plot.append(segment_data.iloc[::2, :]) # Échantillonner un peu

        # --- 3. Appel de la fonction de traçage ---
        try:
            fig_3d = create_3d_map_figure(
                df_sampled=df_sampled_for_3d, # Données principales (échantillonnées)
                color_metric=color_metric,
                climb_segments=climb_segments_to_plot,
                sprint_segments=sprint_segments_to_plot,
                camera_index=animation_pos
            )
            st.plotly_chart(fig_3d, use_container_width=True)
        except Exception as e:
            st.error(f"Erreur lors de la création de la carte 3D : {e}")
            st.exception(e)
            
# Point d'entrée
if __name__ == "__main__":
    main_app()
