# plotting.py
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import plotly.colors
import streamlit as st # Nécessaire pour st.warning

def create_climb_figure(df_climb, alt_col_to_use, CHUNK_DISTANCE_DISPLAY, resultats_montées, index):
    """Crée la figure Plotly avec remplissage synchronisé et modebar."""
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
    df_climb['pente'] = df_climb['pente'].fillna(0); df_climb['heart_rate'] = df_climb['heart_rate'].fillna(0)
    df_climb['cadence'] = df_climb['cadence'].fillna(0); df_climb['estimated_power'] = df_climb['estimated_power'].fillna(0)
    df_climb['speed_kmh'] = df_climb['speed_kmh'].fillna(0)
    fig.add_trace(go.Scatter(
        x=df_climb['dist_relative'], y=df_climb[alt_col_to_use], mode='lines', line=dict(width=0, color='rgba(0,0,0,0)'), showlegend=False,
        customdata=np.stack((df_climb['pente'], df_climb['heart_rate'], df_climb['cadence'], df_climb['speed_kmh'], df_climb['estimated_power']), axis=-1),
        hovertemplate=('<b>Distance:</b> %{x:.0f} m<br>' + f'<b>Altitude:</b> %{{y:.1f}} m<br>' +
                       '<b>Pente:</b> %{customdata[0]:.1f} %<br>' + '<b>Vitesse:</b> %{customdata[3]:.1f} km/h<br>' +
                       '<b>Puissance Est.:</b> %{customdata[4]:.0f} W<br>' +
                       '<b>Fréq. Cardiaque:</b> %{customdata[1]:.0f} bpm<br>' + '<b>Cadence:</b> %{customdata[2]:.0f} rpm' +
                       '<extra></extra>')
    ))
    for _, row in df_climb_chunks.iterrows():
        if row['pente_chunk'] > 0.5:
            mask = (df_climb['dist_relative'] >= row['start_dist']) & (df_climb['dist_relative'] <= row['end_dist'])
            mean_alt_chunk = df_climb.loc[mask, alt_col_to_use].mean() if mask.any() else start_altitude_abs
            max_alt_climb = df_climb[alt_col_to_use].max() if not df_climb.empty else start_altitude_abs
            if pd.notna(mean_alt_chunk):
                mid_y_altitude = mean_alt_chunk + (max_alt_climb - start_altitude_abs) * 0.05
                fig.add_annotation(x=row['mid_dist'], y=mid_y_altitude, text=f"<b>{row['pente_chunk']}%</b>", showarrow=False, font=dict(size=10, color="black", family="Arial Black"), yshift=8)
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