import plotly.graph_objects as go
import numpy as np
import pandas as pd
import plotly.colors
import streamlit as st

# Palette (Vert -> Jaune -> Rouge -> Noir)
PROFILE_COLORSCALE = [
    [0.0, 'rgb(0,128,0)'],     # 0% (Vert)
    [0.25, 'rgb(255,255,0)'], # 5% (Jaune)
    [0.5, 'rgb(255,0,0)'],     # 10% (Rouge)
    [1.0, 'rgb(0,0,0)']        # 20% (Noir)
]
PENTE_ECHELLE_MAX = 20.0 

# --- MODIFICATION 1 : Accepter la distance sélectionnée ---
def create_full_ride_profile(df, selected_distance=None):
    """
    Crée un profil d'altitude 2D de toute la sortie, "Strava-style"
    AVEC un remplissage opaque et une ligne de suivi.
    """
    
    df_profile = df.copy()
    
    # ... (toute la vérification des données, échantillonnage, etc. est INCHANGÉE) ...
    required_cols = ['distance', 'altitude', 'pente', 'speed']
    if not all(col in df_profile.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df_profile.columns]
        st.warning(f"Données manquantes ({', '.join(missing)}) pour le profil.")
    df_profile = df_profile.dropna(subset=['distance', 'altitude', 'pente', 'speed'])
    if df_profile.empty:
        st.warning("Données invalides pour le profil."); return go.Figure()
    sampling_rate = max(1, len(df_profile) // 4000) 
    df_sampled = df_profile.iloc[::sampling_rate, :].copy()
    if df_sampled.empty:
        st.warning("Pas assez de données pour le profil."); return go.Figure()
    if 'speed_kmh' not in df_sampled.columns and 'speed' in df_sampled.columns:
         df_sampled['speed_kmh'] = df_sampled['speed'] * 3.6

    fig = go.Figure()

    # --- Trace 1: Remplissage OPAQUE (Votre Couleur) ---
    fig.add_trace(go.Scatter(
        x=df_sampled['distance'],
        y=df_sampled['altitude'],
        mode='lines',
        line=dict(width=0, color='rgba(0,0,0,0)'),
        fill='tozeroy', 
        fillcolor='rgb(186, 190, 216)', # Votre couleur
        hoverinfo='none',
        showlegend=False
    ))

    # --- Trace 2: La Ligne de Profil (Chunks "cousus") ---
    # ... (toute la boucle 'groupby' est INCHANGÉE) ...
    CHUNK_DISTANCE_PROFILE = 50 
    df_sampled['distance_bin'] = (df_sampled['distance'] // CHUNK_DISTANCE_PROFILE) * CHUNK_DISTANCE_PROFILE
    try: grouped = df_sampled.groupby('distance_bin', observed=True)
    except TypeError: grouped = df_sampled.groupby('distance_bin')
    plotly_colorscale = PROFILE_COLORSCALE
    last_point = None 
    for name, group in grouped:
        if group.empty: continue
        avg_pente = group['pente'].mean()
        pente_norm_pos = max(0, avg_pente) 
        pente_norm = max(0.00001, min(0.99999, (pente_norm_pos / PENTE_ECHELLE_MAX)))
        segment_color_rgb_str = plotly.colors.sample_colorscale(plotly_colorscale, pente_norm)[0]
        x_chunk = group['distance'].tolist()
        y_chunk = group['altitude'].tolist()
        if last_point is not None:
            x_chunk = [last_point[0]] + x_chunk
            y_chunk = [last_point[1]] + y_chunk
        fig.add_trace(go.Scatter(
            x=x_chunk,
            y=y_chunk,
            mode='lines',
            line=dict(width=3, color=segment_color_rgb_str), 
            hoverinfo='none',
            showlegend=False
        ))
        last_point = (group['distance'].iloc[-1], group['altitude'].iloc[-1])


    # --- Trace 5: La Couche Tooltip (Invisible) ---
    # ... (toute la section 'custom_data' est INCHANGÉE) ...
    custom_data_cols = [
        df_sampled['pente'].fillna(0),
        df_sampled['speed_kmh'].fillna(0)
    ]
    hovertemplate_str = "<b>Distance:</b> %{x:,.0f} m<br>" + \
                        "<b>Altitude:</b> %{y:.0f} m<br>" + \
                        "<b>Pente:</b> %{customdata[0]:.1f} %<br>" + \
                        "<b>Vitesse:</b> %{customdata[1]:.1f} km/h<br>"
    if 'estimated_power' in df_sampled.columns:
        df_sampled['estimated_power'] = df_sampled['estimated_power'].fillna(0)
        custom_data_cols.append(df_sampled['estimated_power'])
        hovertemplate_str += f"<b>Puissance Est.:</b> %{{customdata[{len(custom_data_cols)-1}]:.0f}} W<br>"
    if 'heart_rate' in df_sampled.columns:
        df_sampled['heart_rate'] = df_sampled['heart_rate'].fillna(0)
        custom_data_cols.append(df_sampled['heart_rate'])
        hovertemplate_str += f"<b>Fréq. Cardiaque:</b> %{{customdata[{len(custom_data_cols)-1}]:.0f}} bpm"
    hovertemplate_str += "<extra></extra>"
    final_customdata = np.stack(custom_data_cols, axis=-1)
    fig.add_trace(go.Scatter(
        x=df_sampled['distance'],
        y=df_sampled['altitude'],
        mode='lines',
        line=dict(width=0, color='rgba(0,0,0,0)'),
        showlegend=False,
        customdata=final_customdata,
        hovertemplate=hovertemplate_str
    ))

    # --- 6. Mise en Forme ---
    fig.update_layout(
        # ... (mise en forme inchangée) ...
        title="Profil Complet de la Sortie",
        template="plotly_white", 
        xaxis_title="Distance (m)",
        yaxis_title="Altitude (m)",
        hovermode='x unified',
        height=400,
        margin={"r":20, "t":40, "l":20, "b":20},
        xaxis=dict(gridcolor='#EAEAEA'),
        yaxis=dict(gridcolor='#EAEAEA'),
        hoverlabel=dict(bgcolor="white", bordercolor="#E0E0E0", font=dict(color="#333333"))
    )
    
    # --- MODIFICATION 2 : Ajouter la ligne verticale ---
    if selected_distance is not None:
        fig.add_vline(
            x=selected_distance, 
            line_width=2, 
            line_dash="dash", 
            line_color="red"
        )
    
    return fig
