import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.colors
from fitparse import FitFile
# Importe la fonction depuis l'autre fichier
from power_estimator import estimate_power
import io

# --- 1. FONCTION DE LECTURE ET NETTOYAGE DES DONNÉES ---

@st.cache_data
def load_and_clean_data(file_buffer):
    """Lit le fichier FIT, nettoie les données et force les types."""

    data_list = []
    try:
        # Lire le fichier à partir du buffer Streamlit
        fitfile = FitFile(io.BytesIO(file_buffer.read()))
        for record in fitfile.get_messages('record'):
            data_row = {}
            for field in record:
                if field.value is not None:
                    data_row[field.name] = field.value
            if data_row:
                data_list.append(data_row)

        if not data_list:
            return None, "Aucun message de type 'record' trouvé dans le fichier."

        df = pd.DataFrame(data_list)

        # Conversion et nettoyage
        cols_to_convert = ['altitude', 'distance', 'enhanced_altitude', 'enhanced_speed',
                           'heart_rate', 'position_lat', 'position_long', 'speed',
                           'temperature', 'cadence']

        for col in df.columns:
            if col in cols_to_convert:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            elif col == 'timestamp':
                 df[col] = pd.to_datetime(df[col], errors='coerce')

        if 'cadence' in df.columns:
            df['cadence'] = df['cadence'].ffill().bfill()

        cols_essentielles = ['distance', 'altitude', 'timestamp', 'speed']
        df = df.dropna(subset=[c for c in cols_essentielles if c in df.columns])

        if df.empty:
            return None, "Le fichier est vide après nettoyage des données essentielles."

        df = df.set_index('timestamp').sort_index()

        return df, None

    except Exception as e:
        return None, f"Erreur lors du traitement du fichier : {e}"


# --- 2. FONCTION D'ANALYSE ET DE DÉTECTION DES ASCENSIONS ---

@st.cache_data
def analyze_and_detect_climbs(df, min_climb_distance, min_pente, max_gap):
    """Détecte les ascensions, les fusionne et génère le tableau de bord."""

    # Paramètres de détection
    SEUIL_PENTE = min_pente
    SEUIL_DISTANCE_MIN_POUR_LISTER = min_climb_distance
    SEUIL_DISTANCE_REPLAT = max_gap
    FENETRE_LISSAGE_SEC = 20

    if not all(col in df.columns for col in ['altitude', 'distance', 'speed']):
        return None, None, None, None, None, None, "Le fichier FIT ne contient pas les colonnes d'altitude ou de distance nécessaires."

    # Détection des segments
    # Utiliser .copy() pour éviter les SettingWithCopyWarning sur le DataFrame en cache
    df_analysis = df.copy()
    df_analysis['altitude_lisse'] = df_analysis['altitude'].rolling(window=f'{FENETRE_LISSAGE_SEC}s').mean().ffill().bfill()
    df_analysis['delta_distance'] = df_analysis['distance'].diff().fillna(0)
    df_analysis['delta_altitude'] = df_analysis['altitude_lisse'].diff().fillna(0)

    df_analysis['pente'] = np.where(df_analysis['delta_distance'] == 0, 0, (df_analysis['delta_altitude'] / df_analysis['delta_distance']) * 100)
    df_analysis['pente'] = df_analysis['pente'].fillna(0)

    df_analysis['en_montee_brute'] = (df_analysis['pente'] > SEUIL_PENTE)
    df_analysis['bloc_initial'] = (df_analysis['en_montee_brute'] != df_analysis['en_montee_brute'].shift()).cumsum()

    bloc_distances = df_analysis.groupby('bloc_initial')['delta_distance'].sum()
    # Utiliser .loc pour l'indexation booléenne pour la clarté
    is_climb_first = df_analysis.groupby('bloc_initial')['en_montee_brute'].first()
    blocs_montée_courts = bloc_distances.loc[(bloc_distances < 100) & (is_climb_first == True)].index

    df_analysis['en_montee_filtree'] = df_analysis['en_montee_brute']
    # Utiliser .loc pour l'assignation pour éviter SettingWithCopyWarning
    df_analysis.loc[df_analysis['bloc_initial'].isin(blocs_montée_courts), 'en_montee_filtree'] = False

    df_analysis['bloc_a_fusionner'] = (df_analysis['en_montee_filtree'] != df_analysis['en_montee_filtree'].shift()).cumsum()

    blocs_data = []
    for bloc_id, segment in df_analysis.groupby('bloc_a_fusionner'):
        blocs_data.append({
            'bloc_id': bloc_id,
            'is_climb': segment['en_montee_filtree'].iloc[0],
            'distance': segment['delta_distance'].sum()
        })
    df_blocs = pd.DataFrame(blocs_data)

    merged_bloc_id = 0
    bloc_map = {}
    for i in range(len(df_blocs)):
        current_bloc = df_blocs.iloc[i]
        if current_bloc['bloc_id'] in bloc_map: continue
        bloc_map[current_bloc['bloc_id']] = merged_bloc_id
        if not current_bloc['is_climb']:
            merged_bloc_id += 1; continue
        j = i + 1
        while j < len(df_blocs) - 1:
            replat_bloc, next_climb_bloc = df_blocs.iloc[j], df_blocs.iloc[j+1]
            if not replat_bloc['is_climb'] and next_climb_bloc['is_climb']:
                if replat_bloc['distance'] < SEUIL_DISTANCE_REPLAT:
                    bloc_map[replat_bloc['bloc_id']] = merged_bloc_id
                    bloc_map[next_climb_bloc['bloc_id']] = merged_bloc_id
                    j += 2
                else: break
            else: break
        merged_bloc_id += 1

    df_analysis['bloc_fusionne'] = df_analysis['bloc_a_fusionner'].map(bloc_map)
    climb_merged_ids = df_blocs.loc[df_blocs['is_climb'] == True, 'bloc_id'].map(bloc_map).unique()
    df_segments_a_garder = df_analysis[df_analysis['bloc_fusionne'].isin(climb_merged_ids)]
    # Utiliser observed=True si possible pour groupby pour éviter les warnings futurs
    try:
        montees = df_segments_a_garder.groupby('bloc_fusionne', observed=True)
    except TypeError:
        montees = df_segments_a_garder.groupby('bloc_fusionne')


    # Génération du tableau de bord
    resultats_montees = []
    for nom_bloc, segment in montees:
        # Utiliser .loc pour éviter SettingWithCopyWarning sur segment
        segment = segment.copy()
        distance_segment = segment['delta_distance'].sum()
        if distance_segment < SEUIL_DISTANCE_MIN_POUR_LISTER: continue
        altitude_debut, altitude_fin = segment['altitude'].iloc[0], segment['altitude'].iloc[-1]
        denivele = max(0, altitude_fin - altitude_debut)
        dist_debut_km = segment['distance'].iloc[0] / 1000
        pente_moyenne = np.where(distance_segment == 0, 0, (denivele / distance_segment) * 100)
        duree_secondes = (segment.index[-1] - segment.index[0]).total_seconds()
        if duree_secondes <= 0: continue # Ajouter une vérification pour durée non positive
        duree_formatted = pd.to_timedelta(duree_secondes, unit='s')
        vitesse_moyenne_kmh = (distance_segment / 1000) / (duree_secondes / 3600)

        fc_moyenne = segment['heart_rate'].mean() if 'heart_rate' in segment.columns else np.nan
        cadence_moyenne = segment['cadence'].mean() if 'cadence' in segment.columns else np.nan
        power_moyenne = segment['estimated_power'].mean() if 'estimated_power' in segment.columns else np.nan

        resultats_montees.append({
            'Début (km)': f"{dist_debut_km:.1f}", 'Distance (m)': f"{distance_segment:.0f}",
            'Dénivelé (m)': f"{denivele:.0f}", 'Pente (%)': f"{pente_moyenne:.1f}",
            'Durée': str(duree_formatted).split('.')[0].replace('0 days ', ''),
            'Vitesse (km/h)': f"{vitesse_moyenne_kmh:.1f}",
            'FC Moy (bpm)': f"{fc_moyenne:.0f}" if pd.notna(fc_moyenne) else "N/A", # Gérer NaN
            'Cadence Moy': f"{cadence_moyenne:.0f}" if pd.notna(cadence_moyenne) else "N/A", # Gérer NaN
            'Puissance Est. (W)': f"{power_moyenne:.0f}" if pd.notna(power_moyenne) else "N/A" # Gérer NaN
        })

    return df_analysis, pd.DataFrame(resultats_montees), montees, df_blocs, bloc_map, resultats_montees, None


# --- 3. FONCTION DE CRÉATION DU GRAPHIQUE (Plotly) ---

def create_climb_figure(df_climb, alt_col_to_use, CHUNK_DISTANCE_DISPLAY, resultats_montées, index):
    """Crée la figure Plotly avec remplissage synchronisé et modebar."""

    # Paramètres de couleur et correction de bug
    PENTE_MAX_COULEUR = 15.0
    CUSTOM_COLORSCALE = [[0.0, 'rgb(0,128,0)'], [0.25, 'rgb(255,255,0)'], [0.5, 'rgb(255,165,0)'], [0.75, 'rgb(255,0,0)'], [1.0, 'rgb(0,0,0)']]

    # Conversion/Nettoyage local
    cols_to_convert = ['distance', 'altitude', 'speed', 'pente', 'heart_rate', 'cadence', 'altitude_lisse', 'estimated_power']
    for col in cols_to_convert:
        if col in df_climb.columns: df_climb.loc[:, col] = pd.to_numeric(df_climb[col], errors='coerce')

    # Utiliser une copie après dropna pour éviter SettingWithCopyWarning
    df_climb = df_climb.dropna(subset=['distance', alt_col_to_use, 'speed', 'pente']).copy()

    # Vérifier si df_climb est vide après dropna
    if df_climb.empty:
        st.warning(f"Aucune donnée valide pour tracer l'ascension {index+1}.")
        return go.Figure() # Retourner une figure vide

    start_distance_abs = df_climb['distance'].iloc[0]
    start_altitude_abs = df_climb[alt_col_to_use].iloc[0]

    # Utiliser .loc pour toutes les assignations pour éviter SettingWithCopyWarning
    df_climb.loc[:, 'dist_relative'] = df_climb['distance'] - start_distance_abs
    df_climb.loc[:, 'speed_kmh'] = df_climb['speed'] * 3.6

    # Calcul des chunks pour étiquettes
    df_climb.loc[:, 'distance_bin'] = (df_climb['dist_relative'] // CHUNK_DISTANCE_DISPLAY) * CHUNK_DISTANCE_DISPLAY
    try:
        df_climb_chunks = df_climb.groupby('distance_bin', observed=True).agg(
            start_dist=('dist_relative', 'first'), end_dist=('dist_relative', 'last'),
            start_alt=(alt_col_to_use, 'first'), end_alt=(alt_col_to_use, 'last'),
            mid_dist=('dist_relative', 'mean')
        ).reset_index()
    except TypeError:
         df_climb_chunks = df_climb.groupby('distance_bin').agg(
             start_dist=('dist_relative', 'first'), end_dist=('dist_relative', 'last'),
             start_alt=(alt_col_to_use, 'first'), end_alt=(alt_col_to_use, 'last'),
             mid_dist=('dist_relative', 'mean')
         ).reset_index()

    df_climb_chunks['delta_alt'] = df_climb_chunks['end_alt'] - df_climb_chunks['start_alt']
    df_climb_chunks['delta_dist'] = df_climb_chunks['end_dist'] - df_climb_chunks['start_dist']
    df_climb_chunks['pente_chunk'] = np.where(df_climb_chunks['delta_dist'] == 0, 0, (df_climb_chunks['delta_alt'] / df_climb_chunks['delta_dist']) * 100).round(1)

    fig = go.Figure()

    # Trace 1: Remplissage par BLOCS SYNCHRONISÉS (anti-gap)
    for _, row in df_climb_chunks.iterrows():
        pente_norm = max(0, min(1, row['pente_chunk'] / PENTE_MAX_COULEUR))
        epsilon = 1e-9
        pente_norm_clamped = max(epsilon, min(1.0 - epsilon, pente_norm))
        color_rgb_str = plotly.colors.sample_colorscale(CUSTOM_COLORSCALE, pente_norm_clamped)[0]
        fill_color_with_alpha = f'rgba({color_rgb_str[4:-1]}, 0.7)'

        mask_chunk = (df_climb['dist_relative'] >= row['start_dist']) & (df_climb['dist_relative'] <= row['end_dist'])
        df_fill_segment = df_climb.loc[mask_chunk]

        # Ajout du point suivant pour la jointure
        if not df_fill_segment.empty:
            last_index_label = df_fill_segment.index[-1]
            try:
                last_iloc_position = df_climb.index.get_loc(last_index_label)
                next_iloc_position = last_iloc_position + 1
                if next_iloc_position < len(df_climb):
                    next_index_label = df_climb.index[next_iloc_position]
                    next_point = df_climb.loc[[next_index_label]]
                    df_fill_segment = pd.concat([df_fill_segment, next_point])
            except (KeyError, IndexError): pass

        if not df_fill_segment.empty:
            fig.add_trace(go.Scatter(
                x=df_fill_segment['dist_relative'], y=df_fill_segment[alt_col_to_use],
                mode='lines', line=dict(width=0), fill='tozeroy',
                fillcolor=fill_color_with_alpha, hoverinfo='none', showlegend=False
            ))

    # Trace 2: Ligne de profil noire (par-dessus)
    fig.add_trace(go.Scatter(
        x=df_climb['dist_relative'], y=df_climb[alt_col_to_use],
        mode='lines', line=dict(color='black', width=1.5), hoverinfo='none', showlegend=False
    ))

    # Trace 3: Tooltip (Couche invisible)
    # Assurer que les colonnes existent et remplir NaN avant np.stack
    df_climb['pente'] = df_climb['pente'].fillna(0)
    df_climb['heart_rate'] = df_climb['heart_rate'].fillna(0)
    df_climb['cadence'] = df_climb['cadence'].fillna(0)
    df_climb['estimated_power'] = df_climb['estimated_power'].fillna(0)
    df_climb['speed_kmh'] = df_climb['speed_kmh'].fillna(0)


    fig.add_trace(go.Scatter(
        x=df_climb['dist_relative'], y=df_climb[alt_col_to_use], mode='lines', line=dict(width=0, color='rgba(0,0,0,0)'),
        showlegend=False,
        customdata=np.stack((df_climb['pente'], df_climb['heart_rate'], df_climb['cadence'], df_climb['speed_kmh'], df_climb['estimated_power']), axis=-1),
        hovertemplate=('<b>Distance:</b> %{x:.0f} m<br>' + f'<b>Altitude:</b> %{{y:.1f}} m<br>' +
                       '<b>Pente:</b> %{customdata[0]:.1f} %<br>' + '<b>Vitesse:</b> %{customdata[3]:.1f} km/h<br>' +
                       '<b>Puissance Est.:</b> %{customdata[4]:.0f} W<br>' +
                       '<b>Fréq. Cardiaque:</b> %{customdata[1]:.0f} bpm<br>' + '<b>Cadence:</b> %{customdata[2]:.0f} rpm' +
                       '<extra></extra>')
    ))

    # Trace 4: Étiquettes (Annotations)
    for _, row in df_climb_chunks.iterrows():
        if row['pente_chunk'] > 0.5:
            mask = (df_climb['dist_relative'] >= row['start_dist']) & (df_climb['dist_relative'] <= row['end_dist'])
            mean_alt_chunk = df_climb.loc[mask, alt_col_to_use].mean() if mask.any() else start_altitude_abs
            max_alt_climb = df_climb[alt_col_to_use].max() if not df_climb.empty else start_altitude_abs
            # Vérifier si mean_alt_chunk est NaN avant de calculer mid_y_altitude
            if pd.notna(mean_alt_chunk):
                mid_y_altitude = mean_alt_chunk + (max_alt_climb - start_altitude_abs) * 0.05
                fig.add_annotation(
                    x=row['mid_dist'], y=mid_y_altitude, text=f"<b>{row['pente_chunk']}%</b>",
                    showarrow=False, font=dict(size=10, color="black", family="Arial Black"), yshift=8
                )

    # Mise en forme (Panoramique activé, Zoom via Modebar/Shift)
    # Vérifier si resultats_montées a assez d'éléments
    if index < len(resultats_montées):
        climb_info = pd.DataFrame(resultats_montées).iloc[index]
    else:
        # Gérer le cas où l'index est hors limites (ne devrait plus arriver avec la correction IndexError)
        st.warning(f"Données de résumé manquantes pour l'ascension {index+1}.")
        climb_info = {'Début (km)': 'N/A', 'Distance (m)': 'N/A', 'Dénivelé (m)': 'N/A', 'Pente (%)': 'N/A'} # Fallback

    titre = (f"Profil de l'Ascension n°{index + 1} (Début à {climb_info['Début (km)']} km)<br>"
             f"Distance: {climb_info['Distance (m)']} m | Dénivelé: {climb_info['Dénivelé (m)']} m "
             f"| Pente moy: {climb_info['Pente (%)']}%")

    fig.update_layout(
        title=dict(text=titre, x=0.5),
        height=500, width=800,
        plot_bgcolor='white', paper_bgcolor='white',
        xaxis_title='Distance (m)', yaxis_title='Altitude (m)',
        hovermode='closest',     # Garder 'closest' pour le tooltip
        dragmode='pan',          # Le glisser déplace (pan) par défaut
        yaxis_fixedrange=False,  # Permet la manipulation des axes
        xaxis_fixedrange=False,  # Permet la manipulation des axes

        # Configurer la Modebar pour qu'elle soit présente
        modebar=dict(
            orientation='v',
            activecolor='blue',
            # On laisse les boutons par défaut
        ),

        xaxis=dict(
            range=[0, df_climb['dist_relative'].max() if not df_climb.empty else 0], # Gérer df_climb vide
            gridcolor='#EAEAEA', tick0=0, dtick=200
        ),
        yaxis=dict(gridcolor='#EAEAEA'),
        showlegend=False,
    )
    return fig


# --- 4. CORPS PRINCIPAL DE L'APPLICATION STREAMLIT (CORRIGÉ POUR INDEXERROR) ---

def main_app():
    st.set_page_config(layout="wide")
    st.title("🚴 Analyseur d'Ascensions FIT")
    st.markdown("Chargez votre fichier FIT pour analyser vos performances en côte, y compris une estimation de la puissance. Utilisez la barre d'outils sur le graphique pour zoomer.")

    # --- INPUT UTILISATEUR (Colonne de gauche) ---
    with st.sidebar:
        st.header("1. Charger le Fichier")
        uploaded_file = st.file_uploader("Choisissez un fichier .fit", type="fit")

        st.header("2. Paramètres Physiques (pour Puissance Estimée)")
        total_weight_kg = st.number_input("Poids Total (Cycliste + Vélo + Équipement) (kg)", min_value=30.0, max_value=200.0, value=75.0, step=0.5)

        tire_options = {
            "Route (23-25mm) - Asphalte lisse": 0.004,
            "Route (28-32mm) - Asphalte variable": 0.005,
            "Gravel (35-40mm) - Mixte": 0.007,
            "VTT (2.1\"+) - Off-road": 0.012
        }
        selected_tire = st.selectbox("Type de Pneus/Surface Principal", options=list(tire_options.keys()))
        crr_value = tire_options[selected_tire]

        cda_value = 0.38
        st.markdown(f"**Position :** Cocottes (CdA estimé : {cda_value} m²)")

        st.header("3. Paramètres de Détection des Montées")
        min_climb_distance = st.slider("Longueur minimale de la montée (m)", 100, 1000, 400, 50)
        min_pente = st.slider("Pente minimale pour la détection (%)", 1.0, 5.0, 3.0, 0.5)
        max_gap = st.slider("Distance max. entre deux montées à fusionner (m)", 50, 500, 200, 50)

    # --- TRAITEMENT DES DONNÉES ---
    if uploaded_file is not None:
        df, error_msg = load_and_clean_data(uploaded_file)
        if df is None: st.error(f"Erreur chargement : {error_msg}"); return

        # Calculer la puissance estimée
        df_power_est = estimate_power(df, total_weight_kg, crr_value, cda_value)
        # Utiliser .loc pour éviter SettingWithCopyWarning potentiel si df est une vue
        df = df.join(df_power_est)

        # Lancement de l'analyse des montées
        # Passer df.copy() pour être sûr que la fonction cache travaille sur une copie
        df_analyzed, resultats_df, montees_grouped, df_blocs, bloc_map, resultats_montées, analysis_error = analyze_and_detect_climbs(
            df.copy(), min_climb_distance, min_pente, max_gap
        )
        if analysis_error: st.error(f"Erreur analyse : {analysis_error}"); return

        # Déterminer la colonne d'altitude utilisée
        alt_col_to_use = 'altitude'
        # Utiliser df_analyzed (qui sort de analyze_and_detect_climbs)
        if 'altitude_lisse' in df_analyzed.columns and not df_analyzed['altitude_lisse'].isnull().all():
             alt_col_to_use = 'altitude_lisse'

        # --- AFFICHAGE DU TABLEAU DE BORD ---
        st.header("📈 Tableau de Bord des Ascensions Détectées")
        if resultats_df.empty:
            st.warning(f"Aucune ascension ({min_climb_distance}m+, {min_pente}%+) trouvée.")
        else:
            if 'index' in resultats_df.columns:
                 st.dataframe(resultats_df.drop(columns=['index']), use_container_width=True)
            else:
                 st.dataframe(resultats_df, use_container_width=True)

            # --- AFFICHAGE DES GRAPHIQUES (CORRIGÉ POUR INDEXERROR) ---
            st.header("🗺️ Profils Détaillés (Gradient Synchronisé)")
            processed_results_count = 0
            if montees_grouped is not None:
                montee_ids = list(montees_grouped.groups.keys())
                valid_climb_data = []
                for nom_bloc in montee_ids:
                     # Utiliser df_analyzed ici aussi pour avoir les colonnes créées par l'analyse
                     segment = montees_grouped.get_group(nom_bloc)
                     if 'delta_distance' not in segment.columns:
                         # Recalculer si manquant (ne devrait pas arriver si df_analyzed est utilisé)
                          segment = segment.copy() # Travailler sur une copie
                          segment['delta_distance'] = segment['distance'].diff().fillna(0)

                     distance_segment = segment['delta_distance'].sum()
                     if distance_segment >= min_climb_distance:
                         if processed_results_count < len(resultats_montées):
                            valid_climb_data.append((processed_results_count, segment))
                            processed_results_count += 1
                         else: st.warning(f"Incohérence détectée."); break

                for index_resultat, df_climb_original in valid_climb_data:
                    try:
                        # Passer resultats_montées (la liste) et index_resultat
                        fig = create_climb_figure(df_climb_original.copy(), alt_col_to_use, 100, resultats_montées, index_resultat)
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.error(f"Erreur création graphique ascension {index_resultat+1}.")
                        st.exception(e)
            else: st.warning("Aucun groupe de montées traité.")
    else:
        st.info("Veuillez charger un fichier .fit pour commencer.")

if __name__ == "__main__":
    main_app()
