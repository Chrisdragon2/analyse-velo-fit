import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.colors
from fitparse import FitFile
import io

# --- 1. FONCTION DE LECTURE ET NETTOYAGE DES DONNÉES ---

@st.cache_data
def load_and_clean_data(file_buffer):
    """Lit le fichier FIT, nettoie les données et force les types."""
    
    data_list = []
    try:
        # Utiliser io.BytesIO pour lire le contenu binaire du buffer
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
        
        # Conversion globale et nettoyage (basé sur le diagnostic)
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
        
        # Colonnes essentielles
        cols_essentielles = ['distance', 'altitude', 'timestamp', 'speed']
        df = df.dropna(subset=[c for c in cols_essentielles if c in df.columns])
        
        if df.empty:
            return None, "Le fichier est vide après nettoyage des données essentielles."
        
        # Assurer que le timestamp est l'index
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
    SEUIL_VITESSE_MIN = 1.0 # Utilisé dans le résumé, pas dans la détection elle-même

    # Vérification des colonnes nécessaires
    if not all(col in df.columns for col in ['altitude', 'distance', 'speed']):
        return None, "Le fichier FIT ne contient pas les colonnes d'altitude ou de distance nécessaires."

    # Détection des segments (Logique complète de détection et fusion)
    df['altitude_lisse'] = df['altitude'].rolling(window=f'{FENETRE_LISSAGE_SEC}s').mean().ffill().bfill()
    df['delta_distance'] = df['distance'].diff().fillna(0)
    df['delta_altitude'] = df['altitude_lisse'].diff().fillna(0)
    
    df['pente'] = np.where(df['delta_distance'] == 0, 0, (df['delta_altitude'] / df['delta_distance']) * 100)
    df['pente'] = df['pente'].fillna(0)

    df['en_montee_brute'] = (df['pente'] > SEUIL_PENTE)
    df['bloc_initial'] = (df['en_montee_brute'] != df['en_montee_brute'].shift()).cumsum()
    
    bloc_distances = df.groupby('bloc_initial')['delta_distance'].sum()
    blocs_montée_courts = bloc_distances[
        (bloc_distances < 100) & (df.groupby('bloc_initial')['en_montee_brute'].first() == True)
    ].index
    df['en_montee_filtree'] = df['en_montee_brute']
    df.loc[df['bloc_initial'].isin(blocs_montée_courts), 'en_montee_filtree'] = False
    
    df['bloc_a_fusionner'] = (df['en_montee_filtree'] != df['en_montee_filtree'].shift()).cumsum()

    blocs_data = []
    for bloc_id, segment in df.groupby('bloc_a_fusionner'):
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

    df['bloc_fusionne'] = df['bloc_a_fusionner'].map(bloc_map)
    climb_merged_ids = df_blocs.loc[df_blocs['is_climb'] == True, 'bloc_id'].map(bloc_map).unique()
    df_segments_a_garder = df[df['bloc_fusionne'].isin(climb_merged_ids)]
    montees = df_segments_a_garder.groupby('bloc_fusionne')
    
    # Génération du tableau de bord
    resultats_montees = []
    for nom_bloc, segment in montees:
        distance_segment = segment['delta_distance'].sum()
        if distance_segment < SEUIL_DISTANCE_MIN_POUR_LISTER: continue
        altitude_debut, altitude_fin = segment['altitude'].iloc[0], segment['altitude'].iloc[-1]
        denivele = max(0, altitude_fin - altitude_debut)
        dist_debut_km = segment['distance'].iloc[0] / 1000
        pente_moyenne = np.where(distance_segment == 0, 0, (denivele / distance_segment) * 100)
        duree_secondes = (segment.index[-1] - segment.index[0]).total_seconds()
        if duree_secondes == 0: continue
        duree_formatted = pd.to_timedelta(duree_secondes, unit='s')
        vitesse_moyenne_kmh = (distance_segment / 1000) / (duree_secondes / 3600)
        
        # S'assurer que les colonnes existent avant de prendre la moyenne
        fc_moyenne = segment['heart_rate'].mean() if 'heart_rate' in segment.columns else np.nan
        cadence_moyenne = segment['cadence'].mean() if 'cadence' in segment.columns else np.nan

        resultats_montees.append({
            'Début (km)': f"{dist_debut_km:.1f}", 'Distance (m)': f"{distance_segment:.0f}",
            'Dénivelé (m)': f"{denivele:.0f}", 'Pente (%)': f"{pente_moyenne:.1f}",
            'Durée': str(duree_formatted).split('.')[0].replace('0 days ', ''),
            'Vitesse (km/h)': f"{vitesse_moyenne_kmh:.1f}",
            'FC Moy (bpm)': f"{fc_moyenne:.0f}", 'Cadence Moy': f"{cadence_moyenne:.0f}"
        })

    # Retourner les résultats pour le tableau et le dataframe pour le graphique
    return df, pd.DataFrame(resultats_montees), montees, df_blocs, bloc_map, resultats_montees


# --- 3. FONCTION DE CRÉATION DU GRAPHIQUE (Plotly) ---

def create_climb_figure(df_climb, alt_col_to_use, CHUNK_DISTANCE_DISPLAY, resultats_montees, index):
    """Crée la figure Plotly avec le remplissage synchronisé."""
    
    # Paramètres de couleur fixes
    PENTE_MAX_COULEUR = 15.0 
    CUSTOM_COLORSCALE = [[0.0, 'rgb(0,128,0)'], [0.25, 'rgb(255,255,0)'], [0.5, 'rgb(255,165,0)'], [0.75, 'rgb(255,0,0)'], [1.0, 'rgb(0,0,0)']]

    # Logique de préparation du graphique
    start_distance_abs = df_climb['distance'].iloc[0]
    start_altitude_abs = df_climb[alt_col_to_use].iloc[0]

    df_climb.loc[:, 'dist_relative'] = df_climb['distance'] - start_distance_abs
    df_climb.loc[:, 'speed_kmh'] = df_climb['speed'] * 3.6
    df_climb.loc[:, 'distance_bin'] = (df_climb['dist_relative'] // CHUNK_DISTANCE_DISPLAY) * CHUNK_DISTANCE_DISPLAY
    
    # Calcul des chunks pour les étiquettes
    df_climb_chunks = df_climb.groupby('distance_bin', observed=True).agg(
        start_dist=('dist_relative', 'first'), end_dist=('dist_relative', 'last'),
        start_alt=(alt_col_to_use, 'first'), end_alt=(alt_col_to_use, 'last'),
        mid_dist=('dist_relative', 'mean')
    ).reset_index()
    df_climb_chunks['delta_alt'] = df_climb_chunks['end_alt'] - df_climb_chunks['start_alt']
    df_climb_chunks['delta_dist'] = df_climb_chunks['end_dist'] - df_climb_chunks['start_dist']
    df_climb_chunks['pente_chunk'] = np.where(df_climb_chunks['delta_dist'] == 0, 0, (df_climb_chunks['delta_alt'] / df_climb_chunks['delta_dist']) * 100).round(1)

    fig = go.Figure()

    # Trace 1: Remplissage par BLOCS SYNCHRONISÉS (la solution anti-gap)
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
    df_climb['pente'] = df_climb['pente'].fillna(0) # Nettoyage final pour le customdata
    df_climb['heart_rate'] = df_climb['heart_rate'].fillna(0)
    df_climb['cadence'] = df_climb['cadence'].fillna(0)

    fig.add_trace(go.Scatter(
        x=df_climb['dist_relative'], y=df_climb[alt_col_to_use], mode='lines', line=dict(width=0, color='rgba(0,0,0,0)'),
        showlegend=False,
        customdata=np.stack((df_climb['pente'], df_climb['heart_rate'], df_climb['cadence'], df_climb['speed_kmh']), axis=-1),
        hovertemplate=('<b>Distance:</b> %{x:.0f} m<br>' + f'<b>Altitude:</b> %{{y:.1f}} m<br>' +
                       '<b>Pente:</b> %{customdata[0]:.1f} %<br>' + '<b>Vitesse:</b> %{customdata[3]:.1f} km/h<br>' +
                       '<b>Fréq. Cardiaque:</b> %{customdata[1]:.0f} bpm<br>' + '<b>Cadence:</b> %{customdata[2]:.0f} rpm' +
                       '<extra></extra>')
    ))

    # Trace 4: Étiquettes (Annotations)
    for _, row in df_climb_chunks.iterrows():
        if row['pente_chunk'] > 0.5:
            mask = (df_climb['dist_relative'] >= row['start_dist']) & (df_climb['dist_relative'] <= row['end_dist'])
            mean_alt_chunk = df_climb.loc[mask, alt_col_to_use].mean() if mask.any() else start_altitude_abs
            max_alt_climb = df_climb[alt_col_to_use].max() if not df_climb.empty else start_altitude_abs
            mid_y_altitude = mean_alt_chunk + (max_alt_climb - start_altitude_abs) * 0.05
            fig.add_annotation(
                x=row['mid_dist'], y=mid_y_altitude, text=f"<b>{row['pente_chunk']}%</b>",
                showarrow=False, font=dict(size=10, color="black", family="Arial Black"), yshift=8
            )

    # Mise en forme
    climb_info = pd.DataFrame(resultats_montees).iloc[index]
    titre = (f"Profil de l'Ascension n°{index + 1} (Début à {climb_info['Début (km)']} km)<br>"
             f"Distance: {climb_info['Distance (m)']} m | Dénivelé: {climb_info['Dénivelé (m)']} m "
             f"| Pente moy: {climb_info['Pente (%)']}%")

    fig.update_layout(
        title=dict(text=titre, x=0.5), height=500, width=800, plot_bgcolor='white', paper_bgcolor='white',
        xaxis_title='Distance (m)', yaxis_title='Altitude (m)', hovermode='x unified',
        xaxis=dict(range=[0, df_climb['dist_relative'].max()], gridcolor='#EAEAEA', tick0=0, dtick=200),
        yaxis=dict(gridcolor='#EAEAEA'), showlegend=False,
    )
    return fig


# --- 4. CORPS PRINCIPAL DE L'APPLICATION STREAMLIT ---

def main_app():
    st.set_page_config(layout="wide")
    st.title("🚴 Analyseur d'Ascensions FIT")
    st.markdown("Chargez votre fichier FIT pour analyser vos performances en côte. Le code utilise notre solution de gradient synchronisé pour une fidélité maximale.")

    # --- INPUT UTILISATEUR (Colonne de gauche) ---
    with st.sidebar:
        st.header("1. Charger le Fichier")
        uploaded_file = st.file_uploader("Choisissez un fichier .fit", type="fit")

        st.header("2. Paramètres de Détection")
        min_climb_distance = st.slider("Longueur minimale de la montée (m)", 100, 1000, 400, 50)
        min_pente = st.slider("Pente minimale pour la détection (%)", 1.0, 5.0, 3.0, 0.5)
        max_gap = st.slider("Distance max. entre deux montées à fusionner (m)", 50, 500, 200, 50)
        
        st.markdown("---")
        st.info("Le graphique des profils est affiché ci-dessous.")

    # --- TRAITEMENT DES DONNÉES ---
    if uploaded_file is not None:
        df, error_msg = load_and_clean_data(uploaded_file)

        if df is None:
            st.error(f"Erreur de chargement : {error_msg}")
            return

        # Lancement de l'analyse
        df, resultats_df, montees_grouped, df_blocs, bloc_map, resultats_montées = analyze_and_detect_climbs(
            df, min_climb_distance, min_pente, max_gap
        )

        # --- AFFICHAGE DU TABLEAU DE BORD ---
        st.header("📈 Tableau de Bord des Ascensions Détectées")
        if resultats_df.empty:
            st.warning(f"Aucune ascension de plus de {min_climb_distance}m et {min_pente}% n'a été trouvée avec ces paramètres.")
        else:
            st.dataframe(resultats_df, use_container_width=True)

            # --- AFFICHAGE DES GRAPHIQUES ---
            st.header("🗺️ Profils Détaillés (Gradient Synchronisé)")
            
            # Déterminer la colonne d'altitude utilisée
            alt_col_to_use = 'altitude'
            if 'altitude_lisse' in df.columns and not df['altitude_lisse'].isnull().all():
                 alt_col_to_use = 'altitude_lisse'

            montee_ids = list(montees_grouped.groups.keys())
            
            for index, nom_bloc in enumerate(montee_ids):
                df_climb_original = montees_grouped.get_group(nom_bloc)
                
                # Créer et afficher la figure
                fig = create_climb_figure(df_climb_original, alt_col_to_use, 100, resultats_montées, index)
                
                # Streamlit affiche directement les figures Plotly
                st.plotly_chart(fig, use_container_width=True)


    else:
        st.info("Veuillez charger un fichier .fit pour commencer l'analyse.")

# Pour lancer l'application, l'utilisateur doit enregistrer ce code sous un nom (ex: app.py)
# et l'exécuter dans son terminal avec : streamlit run app.py
if __name__ == "__main__":
    main_app()
