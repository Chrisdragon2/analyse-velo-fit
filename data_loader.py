# data_loader.py
import pandas as pd
from fitparse import FitFile
import io
import streamlit as st # Nécessaire pour @st.cache_data

@st.cache_data
def load_and_clean_data(file_buffer):
    """Lit le fichier FIT, nettoie les données et force les types."""
    data_list = []
    try:
        fitfile = FitFile(io.BytesIO(file_buffer.read()))
        for record in fitfile.get_messages('record'):
            data_row = {}
            for field in record:
                if field.value is not None: data_row[field.name] = field.value
            if data_row: data_list.append(data_row)
        if not data_list: return None, "Aucun message 'record' trouvé."

        df = pd.DataFrame(data_list)
        cols_to_convert = ['altitude', 'distance', 'enhanced_altitude', 'enhanced_speed',
                           'heart_rate', 'position_lat', 'position_long', 'speed',
                           'temperature', 'cadence']
        for col in df.columns:
            if col in cols_to_convert: df[col] = pd.to_numeric(df[col], errors='coerce')
            elif col == 'timestamp': df[col] = pd.to_datetime(df[col], errors='coerce')
        if 'cadence' in df.columns: df['cadence'] = df['cadence'].ffill().bfill()
        cols_essentielles = ['distance', 'altitude', 'timestamp', 'speed']
        df = df.dropna(subset=[c for c in cols_essentielles if c in df.columns])
        if df.empty: return None, "Fichier vide après nettoyage."
        df = df.set_index('timestamp').sort_index()
        return df, None
    except Exception as e: return None, f"Erreur traitement : {e}"