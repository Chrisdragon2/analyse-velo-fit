# plotting.py
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import plotly.colors
import streamlit as st

# --- create_climb_figure (INCHANGÉE) ---
# (Colle ici ta fonction create_climb_figure complète et fonctionnelle)
def create_climb_figure(df_climb, alt_col_to_use, CHUNK_DISTANCE_DISPLAY, resultats_montées, index):
    PENTE_MAX_COULEUR = 15.0
    CUSTOM_COLORSCALE = [[0.0, 'rgb(0,128,0)'], [0.25, 'rgb(255,255,0)'], [0.5, 'rgb(255,165,0)'], [0.75, 'rgb(255,0,0)'], [1.0, 'rgb(0,0,0)']]
    cols_to_convert = ['distance', 'altitude', 'speed', 'pente', 'heart_rate', 'cadence', 'altitude_lisse', 'estimated_power']
    for col in cols_to_convert:
        if col in df_climb.columns: df_climb.loc[:, col] = pd.to_numeric(df_climb[col], errors='coerce')
    df_climb = df_climb.dropna(subset=['distance', alt_col_to_use, 'speed', 'pente']).copy()
    if df_climb.empty:
        st.warning(f"Aucune donnée valide pour tracer l'ascension {index+1}.")
        return go.Figure()
    start_distance_abs = df_climb['distance'].iloc[0]; start_altitude_abs = df_climb[alt_col_to_use].iloc[0]
    df_climb.loc[:, 'dist_relative'] = df_climb['distance'] - start_distance_abs
    df_climb.loc[:, 'speed_kmh'] = df_climb['speed'] * 3.6
    df_climb.loc[:, 'distance_bin'] = (df_climb['dist_relative'] // CHUNK_DISTANCE_DISPLAY) * CHUNK_DISTANCE_DISPLAY
    try:
        df_climb_chunks = df_climb.groupby('distance_bin', observed=True).agg(start_dist=('dist_relative', 'first'), end_dist=('dist_relative', 'last'), start_alt=(alt_col_to_use, 'first'), end_alt=(alt_col_to_use, 'last'), mid_dist=('dist_relative', 'mean')).reset_index()
    except TypeError:
         df_climb_chunks = df_climb.groupby('distance_bin').agg(start_dist=('dist_relative', 'first'), end_dist=('dist_relative', 'last'), start_alt=(alt_col_to_use, 'first'), end_alt=(alt_col_to_use, 'last'), mid_dist=('dist_relative', 'mean')).reset_index()
    df_climb_chunks['delta_alt'] = df_climb_chunks['end_alt'] - df_climb_chunks['start_alt']
    df_climb_chunks['delta_dist'] = df_climb_chunks['end_dist'] - df_climb_chunks['start_dist']
    df_climb_chunks['pente_chunk'] = np.where(df_climb_chunks['delta_dist'] == 0, 0, (df_climb_chunks['delta_alt'] / df_climb_chunks['delta_dist']) * 100).round(1)
    fig = go.Figure()
    for _, row in df_climb_chunks.iterrows():
        pente_norm = max(0, min(1, row['pente_chunk'] / PENTE_MAX_COULEUR))
        epsilon = 1e-9; pente_norm_clamped = max(epsilon, min(1.0 - epsilon, pente_norm))
        color_rgb_str = plotly.colors.sample_colorscale(CUSTOM_COLORSCALE, pente_norm_clamped)[0]
        fill_color_with_alpha = f'rgba({color_rgb_str[4:-1]}, 0.7)'
        mask_chunk = (df_climb['dist_relative'] >= row['start_dist']) & (df_climb['dist_relative'] <= row['end_dist'])
        df_fill_segment = df_climb.loc[mask_chunk]
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
            fig.add_trace(go.Scatter(x=df_fill_segment['dist_relative'], y=df_fill_segment[alt_col_to_use], mode='lines', line=dict(width=0), fill='tozeroy', fillcolor=fill_color_with_alpha, hoverinfo='none', showlegend=False))
    fig.add_trace(go.Scatter(x=df_climb['dist_relative'], y=df_climb[alt_col_to_use], mode='lines', line=dict(color='black', width=1.5), hoverinfo='none', showlegend=False))
    custom_data_cols = []
    hovertemplate_str = "<b>Distance:</b> %{x:.0f} m<br>" + f"<b>Altitude:</b> %{{y:.1f}} m<br>"
    df_climb['pente'] = df_climb['pente'].fillna(0)
    custom_data_cols.append(df_climb['pente'])
    hovertemplate_str += "<b>Pente:</b> %{customdata[0]:.1f} %<br>"
    df_climb['speed_kmh'] = df_climb['speed_kmh'].fillna(0)
    custom_data_cols.append(df_climb['speed_kmh'])
    hovertemplate_str += f"<b>Vitesse:</b> %{{customdata[{len(custom_data_cols)-1}]:.1f}} km/h<br>"
    if 'estimated_power' in df_climb.columns:
        df_climb['estimated_power'] = df_climb['estimated_power'].fillna(0)
        custom_data_cols.append(df_climb['estimated_power'])
        hovertemplate_str += f"<b>Puissance Est.:</b> %{{customdata[{len(custom_data_cols)-1}]:.0f}} W<br>"
    if 'heart_rate' in df_climb.columns:
        df_climb['heart_rate'] = df_climb['heart_rate'].fillna(0)
        custom_data_cols.append(df_climb['heart_rate'])
        hovertemplate_str += f"<b>Fréq. Cardiaque:</b> %{{customdata[{len(custom_data_cols)-1}]:.0f}} bpm<br>"
    if 'cadence' in df_climb.columns:
        df_climb['cadence'] = df_climb['cadence'].fillna(0)
        custom_data_cols.append(df_climb['cadence'])
        hovertemplate_str += f"<b>Cadence:</b> %{{customdata[{len(custom_data_cols)-1}]:.0f}} rpm"
    hovertemplate_str += "<extra></extra>"
    final_customdata = np.stack(custom_data_cols, axis=-1)
    fig.add_trace(go.Scatter(
        x=df_climb['dist_relative'], y=df_climb[alt_col_to_use], mode='lines', line=dict(width=0, color='rgba(0,0,0,0)'), showlegend=False,
        customdata=final_customdata, hovertemplate=hovertemplate_str
    ))
    for _, row in df_climb_chunks.iterrows():
        if row['pente_chunk'] > 0.5:
            mask = (df_climb['dist_relative'] >= row['start_dist']) & (df_climb['dist_relative'] <= row['end_dist'])
            mean_alt_chunk = df_climb.loc[mask, alt_col_to_use].mean() if mask.any() else start_altitude_abs
            max_alt_climb = df_climb[alt_col_to_use].max() if not df_climb.empty else start_altitude_abs
            if pd.notna(mean_alt_chunk):
                mid_y_altitude = mean_alt_chunk + (max_alt_climb - start_altitude_abs) * 0.05
                fig.add_annotation(x=row['mid_dist'], y=mid_y_altitude, text=f"<b>{row['pente_chunk']:.1f}%</b>", showarrow=False, font=dict(size=10, color="black", family="Arial Black"), yshift=8)
    if index < len(resultats_montées): climb_info = pd.DataFrame(resultats_montées).iloc[index]
    else: climb_info = {'Début (km)': 'N/A', 'Distance (m)': 'N/A', 'Dénivelé (m)': 'N/A', 'Pente (%)': 'N/A'}
    titre = (f"Profil de l'Ascension n°{index + 1} (Début à {climb_info['Début (km)']} km)<br>"
             f"Distance: {climb_info['Distance (m)']} m | Dénivelé: {climb_info['Dénivelé (m)']} m | Pente moy: {climb_info['Pente (%)']}%")
    fig.update_layout(
        title=dict(text=titre, x=0.5), height=500, width=800, plot_bgcolor='white', paper_bgcolor='white',
        xaxis_title='Distance (m)', yaxis_title='Altitude (m)', hovermode='closest', dragmode='pan',
        yaxis_fixedrange=False, xaxis_fixedrange=False,
        modebar=dict(orientation='v', activecolor='blue'),
        xaxis=dict(range=[0, df_climb['dist_relative'].max() if not df_climb.empty else 0], gridcolor='#EAEAEA', tick0=0, dtick=200),
        yaxis=dict(gridcolor='#EAEAEA'), showlegend=False,
    )
    return fig


# --- MODIFIÉ : create_sprint_figure (accepte 4 arguments et un display_mode) ---
def create_sprint_figure(df_sprint_segment, sprint_info, index, display_mode="courbes"):
    """
    Crée un graphique de profil pour un segment de sprint.
    display_mode: 'courbes' (Vitesse/Puissance courbes) ou 'barres' (Puissance barres / Vitesse courbe)
    """
    fig = go.Figure()
    df_sprint_segment = df_sprint_segment.copy()

    # Nettoyage colonnes
    cols_to_convert = ['speed', 'delta_time']
    for col in ['speed', 'estimated_power', 'delta_time']:
        if col in df_sprint_segment.columns:
            df_sprint_segment.loc[:, col] = pd.to_numeric(df_sprint_segment[col], errors='coerce')
        else:
            if col == 'delta_time':
                if isinstance(df_sprint_segment.index, pd.DatetimeIndex):
                    df_sprint_segment['delta_time'] = df_sprint_segment.index.to_series().diff().dt.total_seconds().fillna(1.0).clip(lower=0.1)
                else:
                    st.error("Index non DatetimeIndex."); return go.Figure()
            elif col != 'estimated_power':
                st.warning(f"Colonne '{col}' manquante."); return go.Figure()
    
    df_sprint_segment = df_sprint_segment.dropna(subset=['speed']).copy()
    if df_sprint_segment.empty:
        st.warning(f"Aucune donnée valide pour le sprint {index+1}.")
        return go.Figure()
        
    df_sprint_segment.loc[:, 'time_relative_sec'] = (df_sprint_segment.index - df_sprint_segment.index[0]).total_seconds()
    df_sprint_segment.loc[:, 'speed_kmh'] = df_sprint_segment['speed'] * 3.6
    if 'estimated_power' in df_sprint_segment.columns: df_sprint_segment['estimated_power'] = df_sprint_segment['estimated_power'].fillna(0)

    # Variables pour les axes
    yaxis_vitesse_config = dict(
        title='Vitesse (km/h)', color='blue', gridcolor='#EAEAEA', side='left',
        range=[0, df_sprint_segment['speed_kmh'].max()*1.1 + 5]
    )
    yaxis_puissance_config = dict(visible=False) # Caché par défaut

    # --- NOUVELLE LOGIQUE D'AFFICHAGE ---
    
    if 'estimated_power' in df_sprint_segment.columns:
        # Activer l'axe Y2 si la puissance existe
        yaxis_puissance_config = dict(
            title='Puissance Est. (W)', color='red', overlaying='y', side='right',
            gridcolor='#EAEAEA', showgrid=False,
            range=[0, df_sprint_segment['estimated_power'].max()*1.1 + 50]
        )

        if display_mode == "barres":
            # Mode "Barres" (comme ton image)
            # Trace 1: Barres de Puissance
            fig.add_trace(go.Bar(
                x=df_sprint_segment['time_relative_sec'], y=df_sprint_segment['estimated_power'],
                name='Puissance Est. (W)', marker_color='red', yaxis='y2',
                hovertemplate='<b>Temps:</b> %{x:.1f} s<br><b>Puissance:</b> %{y:.0f} W<extra></extra>',
                opacity=0.7
            ))
            # Trace 2: Courbe de Vitesse
            fig.add_trace(go.Scatter(
                x=df_sprint_segment['time_relative_sec'], y=df_sprint_segment['speed_kmh'],
                mode='lines', name='Vitesse (km/h)', line=dict(color='blue', width=2.5), yaxis='y1',
                hovertemplate='<b>Temps:</b> %{x:.1f} s<br><b>Vitesse:</b> %{y:.1f} km/h<extra></extra>'
            ))
        else:
            # Mode "Courbes" (notre ancienne vue)
            fig.add_trace(go.Scatter(
                x=df_sprint_segment['time_relative_sec'], y=df_sprint_segment['speed_kmh'],
                mode='lines', name='Vitesse (km/h)', line=dict(color='blue', width=2), yaxis='y1',
                hovertemplate='<b>Temps:</b> %{x:.1f} s<br><b>Vitesse:</b> %{y:.1f} km/h<extra></extra>'
            ))
            fig.add_trace(go.Scatter(
                x=df_sprint_segment['time_relative_sec'], y=df_sprint_segment['estimated_power'],
                mode='lines', name='Puissance Est. (W)', line=dict(color='red', width=2, dash='dot'), yaxis='y2',
                hovertemplate='<b>Temps:</b> %{x:.1f} s<br><b>Puissance:</b> %{y:.0f} W<extra></extra>'
            ))
    
    else: # Si pas de puissance, afficher seulement la vitesse (en barres ou courbe)
        if display_mode == "barres":
             fig.add_trace(go.Bar(
                x=df_sprint_segment['time_relative_sec'], y=df_sprint_segment['speed_kmh'],
                name='Vitesse (km/h)', marker_color='blue', yaxis='y1',
                hovertemplate='<b>Temps:</b> %{x:.1f} s<br><b>Vitesse:</b> %{y:.1f} km/h<extra></extra>'
             ))
        else: # Mode "courbes"
             fig.add_trace(go.Scatter(
                x=df_sprint_segment['time_relative_sec'], y=df_sprint_segment['speed_kmh'],
                mode='lines', name='Vitesse (km/h)', line=dict(color='blue', width=2), yaxis='y1',
                hovertemplate='<b>Temps:</b> %{x:.1f} s<br><b>Vitesse:</b> %{y:.1f} km/h<extra></extra>'
             ))

    # --- FIN NOUVELLE LOGIQUE ---


    # Configuration des axes et du titre
    title_text = f"Profil du Sprint n°{index + 1}<br>" \
                 f"Vmax: {sprint_info.get('Vitesse Max (km/h)', 'N/A')} km/h | " \
                 f"Pmax Est: {sprint_info.get('Puissance Max Est. (W)', 'N/A')} W | " \
                 f"Durée: {sprint_info.get('Durée (s)', 'N/A')} s"

    fig.update_layout(
        title=dict(text=title_text, x=0.5), height=400, width=800, plot_bgcolor='white',
        xaxis_title='Temps Relatif (s)', xaxis=dict(gridcolor='#EAEAEA'),
        yaxis=yaxis_vitesse_config,   # Applique la config Y1
        yaxis2=yaxis_puissance_config, # Applique la config Y2
        hovermode='x unified', 
        legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.8)'),
        margin=dict(l=50, r=50, t=80, b=50), 
        dragmode='pan', yaxis_fixedrange=False, xaxis_fixedrange=False,
        modebar=dict(orientation='v', activecolor='blue'),
        barmode='overlay' # Assure que les barres et la ligne se superposent bien
    )
    
    return fig
