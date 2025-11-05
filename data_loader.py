# data_loader.py
import pandas as pd
from fitparse import FitFile
import io
import streamlit as st

@st.cache_data
def load_and_clean_data(file_buffer):
    """
    Lit le fichier FIT, nettoie les données 'record' (seconde par seconde)
    ET extrait les données de résumé 'session'.
    """
    
    # --- 1. Lire les données 'record' (seconde par seconde) ---
    data_list = []
    # Nous devons utiliser .seek(0) si nous lisons le buffer plusieurs fois
    file_buffer.seek(0) 
    
    try:
        fitfile = FitFile(io.BytesIO(file_buffer.read()))
        for record in fitfile.get_messages('record'):
            data_row = {}
            for field in record:
                if field.value is not None: data_row[field.name] = field.value
            if data_row: data_list.append(data_row)

        if not data_list: 
            return None, None, "Aucun message 'record' trouvé."

        df = pd.DataFrame(data_list)
        
        # Conversion et nettoyage du DataFrame principal
        cols_to_convert = ['altitude', 'distance', 'enhanced_altitude', 'enhanced_speed',
                           'heart_rate', 'position_lat', 'position_long', 'speed',
                           'temperature', 'cadence']
        for col in df.columns:
            if col in cols_to_convert: df[col] = pd.to_numeric(df[col], errors='coerce')
            elif col == 'timestamp': df[col] = pd.to_datetime(df[col], errors='coerce')
        if 'cadence' in df.columns: df['cadence'] = df['cadence'].ffill().bfill()
        cols_essentielles = ['distance', 'altitude', 'timestamp', 'speed']
        df = df.dropna(subset=[c for c in cols_essentielles if c in df.columns])
        if df.empty: return None, None, "Fichier vide après nettoyage."
        df = df.set_index('timestamp').sort_index()

        # --- 2. NOUVEAU : Lire les données 'session' (Résumé) ---
        session_data = {}
        file_buffer.seek(0) # Rembobiner le buffer pour le relire
        fitfile_session = FitFile(io.BytesIO(file_buffer.read()))
        
        session_messages = list(fitfile_session.get_messages('session'))
        if session_messages:
            # On prend la première session trouvée
            session = session_messages[0]
            # Extraire les champs de résumé dont on a besoin
            for field in session:
                if field.name in ('total_moving_time', 'total_elapsed_time', 'total_distance', 'total_ascent'):
                    session_data[field.name] = field.value
        else:
            return df, None, "Aucun message 'session' de résumé trouvé."

        return df, session_data, None # Retourne le df ET le résumé

    except Exception as e: 
        return None, None, f"Erreur traitement : {e}"
