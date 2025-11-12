import streamlit as st
import pydeck as pdk
import pandas as pd
import streamlit.components.v1 as components

st.set_page_config(layout="wide")
st.title("Test de la Carte 3D Satellite (TerrainLayer)")

# --- 1. Vérifier la clé API ---
if "MAPBOX_API_KEY" not in st.secrets:
    st.error("Clé API Mapbox non trouvée. Veuillez l'ajouter à vos Secrets.")
    st.stop()

MAPBOX_KEY = st.secrets["MAPBOX_API_KEY"]

# --- 2. Définir les couches (Layers) ---

# Couche 0: Le Terrain 3D (Fond de carte)
# Basé sur l'exemple officiel de Pydeck
TERRAIN_ELEVATION_TILE_URL = f"https://api.mapbox.com/v4/mapbox.terrain-rgb/{{z}}/{{x}}/{{y}}.png?access_token={MAPBOX_KEY}"
TERRAIN_TEXTURE_TILE_URL = f"https://api.mapbox.com/v4/mapbox.satellite/{{z}}/{{x}}/{{y}}@2x.png?access_token={MAPBOX_KEY}"

terrain_layer = pdk.Layer(
    "TerrainLayer",
    elevation_decoder={"r_scale": 6553.6, "g_scale": 25.6, "b_scale": 0.1, "offset": -10000},
    elevation_data=TERRAIN_ELEVATION_TILE_URL,
    texture=TERRAIN_TEXTURE_TILE_URL,
    min_zoom=0,
    max_zoom=15 # On garde une limite pour l'instant
)

# Couche 1: Une trace GPS (PathLayer) de test
# On simule une petite trace GPS (ex: près de Noisy-le-Grand)
trace_data = [
    {"path": [
        [2.586, 48.844, 100],
        [2.587, 48.845, 110],
        [2.588, 48.844, 120],
        [2.589, 48.845, 115],
        [2.590, 48.844, 130]
    ], "name": "Trace Test"}
]

path_layer = pdk.Layer(
    'PathLayer',
    data=trace_data,
    pickable=True,
    get_color=[255, 69, 0, 255], # Orange
    width_scale=1,
    width_min_pixels=3,
    get_path='path',
    get_width=5
)

# --- 3. Définir la Vue ---
view_state = pdk.ViewState(
    latitude=48.8445,
    longitude=2.588,
    zoom=14,
    pitch=60,
    bearing=0
)

# --- 4. Créer l'objet Deck ---
# On utilise la correction de ton rapport : map_style=None
# (ou map_provider=None)
r = pdk.Deck(
    layers=[terrain_layer, path_layer],
    initial_view_state=view_state,
    api_keys={'mapbox': MAPBOX_KEY},
    map_style=None # La correction clé pour éviter la "double carte"
)

# --- 5. Afficher la carte ---
st.header("Rendu via `components.html(deck.to_html())`")
st.write("C'est la solution de contournement officielle")

try:
    # On utilise la méthode de contournement simple et robuste
    # Pydeck injectera lui-même les bonnes versions de JS
    final_html = r.to_html(as_string=True)
    
    components.html(final_html, height=600, scrolling=False)
    
    st.success("Rendu HTML terminé.")

except Exception as e:
    st.error("Erreur lors de la génération de l'HTML de la carte :")
    st.exception(e)
