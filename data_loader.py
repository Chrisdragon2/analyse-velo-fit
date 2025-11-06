# data_loader.py
import pandas as pd
from fitparse import FitFile
import io
import streamlit as st

@st.cache_data
def load_and_clean_data(file_buffer):
    """
    Lit le .fit, nettoie les 'record', convertit le GPS (s'il existe),
    et extrait les 'session'.
    """
    
    # --- 1. Lire les données 'record' (seconde par seconde) ---
    data_list = []
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
        
        # Conversion et nettoyage
        cols_to_convert = ['altitude', 'distance', 'enhanced_altitude', 'enhanced_speed',
                           'heart_rate', 'speed', 'temperature', 'cadence']
        cols_gps = ['position_lat', 'position_long']

        for col in df.columns:
            if col in cols_to_convert: 
                df[col] = pd.to_numeric(df[col], errors='coerce')
            elif col == 'timestamp': 
                 df[col] = pd.to_datetime(df[col], errors='coerce')
            # Conversion GPS (Seulement si la colonne existe)
            elif col in cols_gps:
                df[col] = pd.to_numeric(df[col], errors='coerce') * (180 / 2**31)

        if 'cadence' in df.columns: df['cadence'] = df['cadence'].ffill().bfill()
        
        # --- MODIFIÉ : Colonnes GPS retirées des essentielles ---
        cols_essentielles = ['distance', 'altitude', 'timestamp', 'speed']
        # On ne supprime les lignes que si les données ESSENTIELLES manquent
        df = df.dropna(subset=[c for c in cols_essentielles if c in df.columns])
        
        if df.empty: 
            return None, None, "Fichier vide après nettoyage (données essentielles manquantes)."
        # --- FIN MODIFICATION ---
            
        df = df.set_index('timestamp').sort_index()

        # --- 2. Lire les données 'session' ---
        session_data = {}
        file_buffer.seek(0)
        fitfile_session = FitFile(io.BytesIO(file_buffer.read()))
        
        session_messages = list(fitfile_session.get_messages('session'))
        if session_messages:
            session = session_messages[0]
            for field in session:
                if field.value is not None:
                    session_data[field.name] = field.value
        else:
            st.warning("Aucun message 'session' de résumé trouvé.")
            session_data = {}

        return df, session_data, None

    except Exception as e: 
        return None, None, f"Erreur traitement : {e}"
